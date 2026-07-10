"""
ingest.py
Reads a project's task list + weekly PM update and normalizes them,
tolerating messy/incomplete real-world data (missing columns, odd date
formats, blank cells, free text where a number was expected).
"""
import pandas as pd
import re
from datetime import datetime


def _parse_date(val):
    """Best-effort date parser. Returns None (not an exception) on failure."""
    if pd.isna(val) or str(val).strip() == "":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%B %d, %Y", "%m-%d-%y"):
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(val, errors="coerce")
    except Exception:
        return None


def _parse_number(val, default=None):
    if pd.isna(val):
        return default
    s = re.sub(r"[^0-9.\-]", "", str(val))
    try:
        return float(s) if s not in ("", "-", ".") else default
    except ValueError:
        return default


def load_tasks(path):
    """Load the task list CSV. Tolerates missing/renamed columns."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    col_aliases = {
        "task_name": ["task_name", "task", "name", "activity"],
        "planned_end": ["planned_end", "planned_finish", "due_date", "plan_end"],
        "actual_end": ["actual_end", "actual_finish", "completed_date", "actual_completion"],
        "percent_complete": ["percent_complete", "%_complete", "pct_complete", "complete"],
        "milestone": ["milestone", "is_milestone", "milestone_flag"],
        "owner": ["owner", "assignee", "responsible"],
    }

    def find_col(names):
        for n in names:
            if n in df.columns:
                return n
        return None

    normalized = pd.DataFrame()
    normalized["task_name"] = df[find_col(col_aliases["task_name"])] if find_col(col_aliases["task_name"]) else "Unnamed task"
    planned_col = find_col(col_aliases["planned_end"])
    actual_col = find_col(col_aliases["actual_end"])
    pct_col = find_col(col_aliases["percent_complete"])
    milestone_col = find_col(col_aliases["milestone"])
    owner_col = find_col(col_aliases["owner"])

    normalized["planned_end"] = df[planned_col].apply(_parse_date) if planned_col else None
    normalized["actual_end"] = df[actual_col].apply(_parse_date) if actual_col else None
    normalized["percent_complete"] = (
        df[pct_col].apply(lambda v: _parse_number(v, default=0)) if pct_col else 0
    )
    normalized["milestone"] = (
        df[milestone_col].astype(str).str.strip().str.lower().isin(["y", "yes", "true", "1"])
        if milestone_col else False
    )
    normalized["owner"] = df[owner_col] if owner_col else "Unassigned"

    normalized["data_quality_flags"] = ""
    if not planned_col:
        normalized["data_quality_flags"] += "missing_planned_dates;"
    if not pct_col:
        normalized["data_quality_flags"] += "missing_percent_complete;"

    return normalized


def load_weekly_update(path):
    """Load the free-text weekly PM update CSV (one row expected, but tolerant of more)."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    row = df.iloc[-1] if len(df) > 0 else pd.Series(dtype=object)  # most recent row

    def g(key, default=""):
        return row[key] if key in row.index and not pd.isna(row[key]) else default

    # Sanity check: week_ending should look like a date. If a PM's free-text
    # field had an unescaped comma and shifted columns, this catches it
    # rather than silently mis-reporting a budget number as the week date.
    week_ending_val = g("week_ending", None)
    if week_ending_val is not None and _parse_date(week_ending_val) is None:
        week_ending_val = None  # treat as missing/unparseable rather than trust a corrupted value

    blockers_raw = str(g("open_blockers", ""))
    blockers = [b.strip() for b in re.split(r"[;\n]", blockers_raw) if b.strip()]

    return {
        "week_ending": week_ending_val,
        "total_budget": _parse_number(g("total_budget"), default=None),
        "budget_planned_to_date": _parse_number(g("budget_planned_to_date"), default=None),
        "budget_actual_to_date": _parse_number(g("budget_actual_to_date"), default=None),
        "open_blockers": blockers,
        "stakeholder_notes": str(g("stakeholder_notes", "")),
        "pm_comments": str(g("pm_comments", "")),
    }
