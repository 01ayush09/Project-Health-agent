"""
dashboard/app.py
A local live dashboard for the project health agent.

How "live" works here: this does NOT keep a background watcher process.
Instead, on every request from the browser (polled automatically every few
seconds — see static/app.js), the server checks the file-modified time of:
  1. the source .xlsx (if you edit that), and
  2. the derived task/update CSVs (if you edit those directly)
and only re-runs the scoring pipeline when something has actually changed
since the last check. If nothing changed, it serves the last computed
result instantly from memory — so most polls do zero work.

If the .xlsx was edited more recently than its derived CSVs, this
regenerates the CSVs first (via convert_real_data.py) before scoring, so
BOTH editing the raw Excel export and editing the CSVs directly work.

This intentionally does NOT write to outputs/weekly/ — that folder holds
your official dated weekly snapshots (produced by
agent/run_current_projects.py) and this live view shouldn't overwrite them
just because you're looking at the dashboard. The live computation here is
in-memory only.

Run:
    pip install -r ../requirements-dashboard.txt
    python3 app.py
Then open http://127.0.0.1:5000
"""
import os
import sys
import time
from datetime import datetime

from flask import Flask, jsonify, render_template

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
AGENT_DIR = os.path.join(PROJECT_ROOT, "agent")
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "project_plans")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, AGENT_DIR)
import convert_real_data  # noqa: E402
import ingest  # noqa: E402
import metrics  # noqa: E402
import rag_engine  # noqa: E402
import reasoning  # noqa: E402
import report_generator  # noqa: E402

app = Flask(__name__)

# In-memory cache: slug -> {"key": (...mtimes...), "report": {...}, "row_count": int, "computed_at": float}
_CACHE = {}


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _csv_paths(slug):
    return (
        os.path.join(DATA_DIR, f"{slug}_tasks_current.csv"),
        os.path.join(DATA_DIR, f"{slug}_current_update.csv"),
    )


def _compute_report(project_name, tasks_path, update_path):
    """Mirrors agent/run_weekly.py's run_one(), but computes in-memory only
    (no file writes) since this runs on every poll and shouldn't spam disk
    or clobber the official dated weekly reports."""
    as_of = datetime.now()
    tasks_df = ingest.load_tasks(tasks_path)
    weekly_update = ingest.load_weekly_update(update_path)

    data_quality_notes = []
    for flag in tasks_df["data_quality_flags"].unique():
        if flag:
            data_quality_notes.append(f"Task list: {flag}")

    sched = metrics.schedule_metrics(tasks_df, as_of=as_of)
    ms = metrics.milestone_metrics(tasks_df, as_of=as_of)
    budget = metrics.budget_metrics(weekly_update)
    blk = metrics.blocker_metrics(weekly_update, as_of=as_of)
    sentiment = reasoning.classify_sentiment(weekly_update["stakeholder_notes"], None)

    for m, name in [(sched, "schedule"), (ms, "milestones"), (budget, "budget"), (blk, "blockers")]:
        if m.get("flags"):
            data_quality_notes.extend([f"{name}: {f}" for f in m["flags"]])

    scores, reasons = {}, {}
    scores["schedule"], reasons["schedule"] = rag_engine.score_schedule(sched)
    scores["budget"], reasons["budget"] = rag_engine.score_budget(budget)
    scores["milestones"], reasons["milestones"] = rag_engine.score_milestones(ms)
    scores["blockers"], reasons["blockers"] = rag_engine.score_blockers(blk)
    scores["sentiment"], reasons["sentiment"] = rag_engine.score_sentiment(sentiment)

    raw_metrics = {"schedule": sched, "budget": budget, "milestones": ms, "blockers": blk, "sentiment": sentiment}
    rag_result = rag_engine.compute_overall_rag(scores, reasons, raw_metrics)
    narrative, narrative_source = reasoning.generate_narrative(project_name, rag_result, raw_metrics)

    week_ending = weekly_update.get("week_ending") or as_of.strftime("%Y-%m-%d")
    report = report_generator.build_report(project_name, week_ending, rag_result, narrative, raw_metrics,
                                            data_quality_notes, narrative_source)
    report["row_count"] = len(tasks_df)
    return report


def get_project_status(slug):
    cfg = convert_real_data.PROJECTS[slug]
    tasks_path, update_path = _csv_paths(slug)
    xlsx_path = cfg["xlsx"]

    xlsx_mtime = _mtime(xlsx_path)
    tasks_mtime = _mtime(tasks_path)
    update_mtime = _mtime(update_path)

    # If the source Excel file is newer than what it was last converted to
    # (or the CSVs don't exist yet), regenerate the CSVs from it first.
    if xlsx_mtime is not None and (tasks_mtime is None or xlsx_mtime > tasks_mtime):
        cfg["convert_fn"](xlsx_path, out_dir=DATA_DIR)
        tasks_mtime = _mtime(tasks_path)
        update_mtime = _mtime(update_path)

    key = (xlsx_mtime, tasks_mtime, update_mtime)
    cached = _CACHE.get(slug)
    if cached and cached["key"] == key:
        return cached["report"], cached["computed_at"], False

    report = _compute_report(cfg["name"], tasks_path, update_path)
    computed_at = time.time()
    _CACHE[slug] = {"key": key, "report": report, "computed_at": computed_at}
    return report, computed_at, True


@app.route("/")
def index():
    return render_template("index.html", projects=list(convert_real_data.PROJECTS.keys()))


@app.route("/api/status")
def api_status():
    results = []
    for slug in convert_real_data.PROJECTS:
        report, computed_at, recomputed = get_project_status(slug)
        dimensions = {
            dim: {"status": status, "reason": report["dimension_reasons"].get(dim, "")}
            for dim, status in report["dimension_status"].items()
        }
        results.append({
            "slug": slug,
            "project_name": report["project_name"],
            "overall_label": report["overall_status"],
            "row_count": report.get("row_count"),
            "dimensions": dimensions,
            "override_reasons": report.get("override_reasons", []),
            "narrative": report["narrative"],
            "data_quality_notes": report.get("data_quality_notes", []),
            "computed_at": datetime.fromtimestamp(computed_at).strftime("%H:%M:%S"),
            "just_recomputed": recomputed,
        })
    return jsonify({"projects": results, "server_time": datetime.now().strftime("%H:%M:%S")})


if __name__ == "__main__":
    # use_reloader=False is intentional: Flask's debug reloader watches every
    # file in the project directory, including data/project_plans/*.csv —
    # so editing the very CSV this dashboard is meant to watch live would
    # otherwise restart the server and drop in-flight requests.
    app.run(debug=True, use_reloader=False, port=5000)
