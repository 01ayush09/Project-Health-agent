"""
run_trend_demo.py

Runs the same weekly agent (ingest -> metrics -> rag_engine -> reasoning ->
report_generator) used for the real UniSan/Titan snapshot, but against the
synthetic 3-project x 4-week dataset in data/project_plans_demo/ (see
generate_demo_data.py for what's in it and why).

Purpose: the real client exports are single snapshots, so they can't
exercise Phase 3's trend/pattern detection (declining vs. improving
trajectories, recurring cross-project blockers, sentiment-leads-status lag,
overspend correlated with slip). This produces a week-over-week series that
can, feeding outputs/weekly_demo/week{1..4} instead of outputs/weekly/week1
so it never overwrites the real official snapshot.

Usage (from the agent/ folder):
    python3 run_trend_demo.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from run_weekly import run_one
import ingest

WEEK_ENDINGS = ["2026-06-05", "2026-06-12", "2026-06-19", "2026-06-26"]
PROJECTS = [
    ("meridian", "Meridian Data Migration"),
    ("helix", "Helix ERP Rollout"),
    ("cascade", "Cascade Vendor Onboarding"),
]

DEMO_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "project_plans_demo")
DEMO_OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "weekly_demo")


def main():
    for slug, name in PROJECTS:
        prior_notes = None
        for i, week_ending in enumerate(WEEK_ENDINGS):
            tasks_path = os.path.join(DEMO_DATA_DIR, f"tasks_{slug}_w{i+1}.csv")
            update_path = os.path.join(DEMO_DATA_DIR, f"update_{slug}_w{i+1}.csv")
            out_dir = os.path.join(DEMO_OUT_DIR, f"week{i+1}")
            as_of = datetime.strptime(week_ending, "%Y-%m-%d")
            run_one(name, tasks_path, update_path, as_of, prior_notes, out_dir)
            # Feed this week's stakeholder notes forward as "prior_notes" for
            # next week's sentiment trend comparison, same as a real weekly
            # cadence would. report_generator doesn't retain the raw free
            # text in its output, so read it back from the source file.
            prior_notes = ingest.load_weekly_update(update_path)["stakeholder_notes"]
    print(f"\nDone. Weekly reports written under {DEMO_OUT_DIR}")
    print("Next: cd ../monthly_synthesis && python3 synthesize.py --demo && "
          "node build_deck.js demo_summary.json Trend_Demo_Presentation.pptx")


if __name__ == "__main__":
    main()
