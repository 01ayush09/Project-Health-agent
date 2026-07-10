"""
run_weekly.py
Main entrypoint. Runs the full pipeline for one project (task file + weekly
update file) and saves a report. Also supports looping over every project
in data/project_plans/ for a full weekly batch run.

Usage:
    python run_weekly.py --tasks data/project_plans/alpha_tasks.csv \
                          --update data/project_plans/alpha_week1_update.csv \
                          --project "Project Alpha" \
                          --as-of 2026-06-08 \
                          --prior-notes ""

    python run_weekly.py --batch data/project_plans/batch_manifest.csv
"""
import argparse
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import ingest
import metrics
import rag_engine
import reasoning
import report_generator


def run_one(project_name, tasks_path, update_path, as_of, prior_notes, out_dir):
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
    sentiment = reasoning.classify_sentiment(weekly_update["stakeholder_notes"], prior_notes)

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
    json_path, md_path = report_generator.save_report(report, out_dir)
    print(f"[OK] {project_name}: {rag_result['overall_label']} (narrative: {narrative_source})  -> {md_path}")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", help="path to task list CSV")
    parser.add_argument("--update", help="path to weekly update CSV")
    parser.add_argument("--project", help="project display name")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD, defaults to today")
    parser.add_argument("--prior-notes", default=None, help="prior week's stakeholder notes, for sentiment trend")
    parser.add_argument("--out", default="../outputs/weekly", help="output directory")
    args = parser.parse_args()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d") if args.as_of else datetime.now()
    run_one(args.project, args.tasks, args.update, as_of, args.prior_notes, args.out)


if __name__ == "__main__":
    main()
