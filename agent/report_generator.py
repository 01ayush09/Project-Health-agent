"""
report_generator.py
Assembles the final weekly report (Markdown for humans, JSON for the
monthly synthesis step to consume) from the RAG result + narrative.
"""
import json
from datetime import datetime


def build_report(project_name, week_ending, rag_result, narrative, raw_metrics, data_quality_notes,
                  narrative_source="unknown"):
    report = {
        "project_name": project_name,
        "week_ending": week_ending,
        "generated_at": datetime.now().isoformat(),
        "overall_status": rag_result["overall_label"],
        "weighted_score": rag_result["weighted_score"],
        "dimension_status": rag_result["dimension_labels"],
        "dimension_reasons": rag_result["dimension_reasons"],
        "override_reasons": rag_result["override_reasons"],
        "narrative": narrative,
        "narrative_source": narrative_source,
        "data_quality_notes": data_quality_notes,
        "raw_metrics": raw_metrics,
    }
    return report


def to_markdown(report):
    badge = {"Green": "🟢", "Amber": "🟠", "Red": "🔴"}[report["overall_status"]]
    md = [
        f"# Weekly Project Health Report — {report['project_name']}",
        f"**Week ending:** {report['week_ending']}  ",
        f"**Overall status:** {badge} **{report['overall_status']}**  ",
        f"**Weighted score:** {report['weighted_score']} / 2.0\n",
        "## Dimension Breakdown\n",
        "| Dimension | Status | Why |",
        "|---|---|---|",
    ]
    for dim, status in report["dimension_status"].items():
        b = {"Green": "🟢", "Amber": "🟠", "Red": "🔴"}[status]
        reason = report["dimension_reasons"].get(dim, "")
        md.append(f"| {dim.capitalize()} | {b} {status} | {reason} |")

    if report["override_reasons"]:
        md.append("\n## Escalation Flags")
        for r in report["override_reasons"]:
            md.append(f"- ⚠️ {r}")

    md.append("\n## Executive Narrative\n")
    md.append(report["narrative"])

    if report["data_quality_notes"]:
        md.append("\n## Data Quality Notes")
        for note in report["data_quality_notes"]:
            md.append(f"- {note}")

    md.append(f"\n---\n*Narrative source: {report.get('narrative_source', 'unknown')}*")

    return "\n".join(md)


def save_report(report, out_dir):
    import os
    os.makedirs(out_dir, exist_ok=True)
    base = f"{report['project_name'].replace(' ', '_')}_{report['week_ending']}"
    json_path = os.path.join(out_dir, base + ".json")
    md_path = os.path.join(out_dir, base + ".md")
    # encoding="utf-8" is required here: the emoji badges in to_markdown()
    # otherwise fail to write on Windows, where open() defaults to the
    # system's cp1252 encoding instead of UTF-8 (Mac/Linux default to UTF-8,
    # which is why this only surfaced when running on Windows).
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))
    return json_path, md_path
