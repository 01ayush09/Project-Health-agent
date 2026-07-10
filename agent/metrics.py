"""
metrics.py
Deterministic, auditable calculations from normalized data.
Every function degrades gracefully and reports what it couldn't compute,
rather than throwing or silently guessing.
"""
import re
from datetime import datetime
import pandas as pd


def schedule_metrics(tasks_df, as_of=None):
    as_of = as_of or datetime.now()
    flags = []
    dated = tasks_df.dropna(subset=["planned_end"])
    if dated.empty:
        return {"pct_late": None, "late_tasks": [], "flags": ["no_planned_dates_available"]}

    def is_late(row):
        if row["percent_complete"] >= 100:
            return False  # done, doesn't matter if actual_end is missing
        return row["planned_end"] < as_of

    dated = dated.copy()
    dated["is_late"] = dated.apply(is_late, axis=1)
    late_tasks = dated[dated["is_late"]]["task_name"].tolist()
    pct_late = round(100 * len(late_tasks) / len(dated), 1)

    critical_milestone_late = dated[(dated["is_late"]) & (dated["milestone"])]["task_name"].tolist()

    return {
        "pct_late": pct_late,
        "late_tasks": late_tasks,
        "critical_milestone_late": critical_milestone_late,
        "flags": flags,
    }


def milestone_metrics(tasks_df, as_of=None, lookahead_days=14):
    as_of = as_of or datetime.now()
    milestones = tasks_df[tasks_df["milestone"] == True].dropna(subset=["planned_end"])
    if milestones.empty:
        return {"overdue": [], "at_risk_soon": [], "flags": ["no_milestones_found"]}

    overdue = milestones[
        (milestones["planned_end"] < as_of) & (milestones["percent_complete"] < 100)
    ]["task_name"].tolist()

    upcoming = milestones[
        (milestones["planned_end"] >= as_of)
        & (milestones["planned_end"] <= as_of + pd.Timedelta(days=lookahead_days))
        & (milestones["percent_complete"] < 100)
    ]["task_name"].tolist()

    return {"overdue": overdue, "at_risk_soon": upcoming, "flags": []}


def budget_metrics(weekly_update):
    planned = weekly_update.get("budget_planned_to_date")
    actual = weekly_update.get("budget_actual_to_date")
    if planned is None or actual is None or planned == 0:
        return {"burn_ratio": None, "flags": ["insufficient_budget_data"]}
    ratio = round(actual / planned, 2)
    return {"burn_ratio": ratio, "planned": planned, "actual": actual, "flags": []}


def blocker_metrics(weekly_update, as_of=None):
    blockers = weekly_update.get("open_blockers", [])
    if not blockers:
        return {"count": 0, "critical": [], "flags": []}
    critical = [b for b in blockers if re.search(r"critical|urgent|severe", b, re.IGNORECASE)]
    return {"count": len(blockers), "items": blockers, "critical": critical, "flags": []}
