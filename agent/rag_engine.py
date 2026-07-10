"""
rag_engine.py
Implements the scoring rules from RAG_METHODOLOGY.md:
- Score each dimension 0/1/2 (Red/Amber/Green), flagging missing data as Amber.
- Weighted roll-up.
- Escalation overrides that can force Red regardless of the weighted score.
"""

RED, AMBER, GREEN = 0, 1, 2
LABELS = {RED: "Red", AMBER: "Amber", GREEN: "Green"}
WEIGHTS = {"schedule": 0.25, "budget": 0.20, "milestones": 0.25, "blockers": 0.20, "sentiment": 0.10}


def score_schedule(sched):
    if sched.get("pct_late") is None:
        return AMBER, "No planned dates available to assess schedule — flagged for follow-up."
    pct = sched["pct_late"]
    if sched.get("critical_milestone_late"):
        return RED, f"Critical milestone(s) late: {', '.join(sched['critical_milestone_late'])}."
    if pct <= 5:
        return GREEN, f"Only {pct}% of tasks are behind schedule."
    if pct <= 20:
        return AMBER, f"{pct}% of tasks are behind schedule — worth watching."
    return RED, f"{pct}% of tasks are behind schedule — significant slippage."


def score_budget(budget):
    if budget.get("burn_ratio") is None:
        return AMBER, "Budget actuals/planned-to-date not provided — flagged for follow-up."
    r = budget["burn_ratio"]
    if 0.9 <= r <= 1.1:
        return GREEN, f"Spend is on track ({round(r*100)}% of planned burn)."
    if (1.1 < r <= 1.3) or (0.7 <= r < 0.9):
        note = "overspending" if r > 1 else "underspending (possible stalled work)"
        return AMBER, f"Spend is {round(r*100)}% of planned — {note}."
    note = "significantly overspending" if r > 1.3 else "significantly underspending, suggesting delayed work"
    return RED, f"Spend is {round(r*100)}% of planned — {note}."


def score_milestones(ms):
    overdue = ms.get("overdue", [])
    at_risk = ms.get("at_risk_soon", [])
    if ms.get("flags") == ["no_milestones_found"]:
        return AMBER, "No milestones defined in the plan — flagged for follow-up."
    if len(overdue) >= 2:
        return RED, f"{len(overdue)} milestones are overdue: {', '.join(overdue)}."
    if len(overdue) == 1:
        return AMBER, f"1 milestone is overdue: {overdue[0]}."
    if at_risk:
        return AMBER, f"Milestone(s) due within 2 weeks at risk: {', '.join(at_risk)}."
    return GREEN, "All milestones on track."


def score_blockers(blk):
    critical = blk.get("critical", [])
    count = blk.get("count", 0)
    if critical:
        return RED, f"Critical blocker(s) open: {', '.join(critical)}."
    if count == 0:
        return GREEN, "No open blockers."
    if count <= 2:
        return AMBER, f"{count} open blocker(s): {', '.join(blk.get('items', []))}."
    return RED, f"{count} open blockers — escalating volume of unresolved issues."


def score_sentiment(sentiment_result):
    """sentiment_result: dict with 'label' (positive/neutral/negative) and 'trend' (improving/stable/worsening),
    produced by the reasoning layer (LLM or fallback classifier)."""
    label = sentiment_result.get("label", "unknown")
    trend = sentiment_result.get("trend", "stable")
    if label == "unknown":
        return AMBER, "No stakeholder commentary provided — flagged for follow-up."
    if label == "positive":
        return GREEN, "Stakeholder tone is positive."
    if label == "negative" and trend == "worsening":
        return RED, "Stakeholder tone is negative and worsening."
    if label == "negative":
        return AMBER, "Stakeholder tone is negative but not escalating."
    return AMBER, "Stakeholder tone is neutral."


def compute_overall_rag(dimension_scores, dimension_reasons, raw_metrics):
    """dimension_scores: dict of dimension -> 0/1/2. Applies weighting then overrides."""
    weighted = sum(dimension_scores[d] * WEIGHTS[d] for d in WEIGHTS)

    if weighted >= 1.5:
        overall = GREEN
    elif weighted >= 0.8:
        overall = AMBER
    else:
        overall = RED

    override_reasons = []
    blk = raw_metrics.get("blockers", {})
    red_dims = [d for d, s in dimension_scores.items() if s == RED]

    # Fix (caught in review): a weighted average can land in Green territory
    # even when one dimension is explicitly Red (e.g. Gamma week 4: schedule
    # Red at "significant slippage," but budget/milestones/blockers/sentiment
    # all Green averages out to exactly 1.5). Reporting "Green" while a
    # dimension reason says "significant slippage" destroys trust in the
    # tool faster than any false alarm would — so any Red dimension caps the
    # overall status at Amber, full stop, regardless of the weighted score.
    if red_dims and overall == GREEN:
        overall = AMBER
        override_reasons.append(
            f"Override: {', '.join(red_dims)} scored Red — overall cannot be Green even though the weighted average cleared the Green threshold."
        )

    if blk.get("critical"):
        overall = RED
        override_reasons.append("Override: critical blocker open.")

    ms = raw_metrics.get("milestones", {})
    if len(ms.get("overdue", [])) >= 2:
        overall = RED
        override_reasons.append("Override: 2+ milestones overdue.")

    # Fix (caught in review, same class of bug as the one above): this used to
    # check `if red_dims and sentiment == RED`, but red_dims includes sentiment
    # itself — so a project with ONLY sentiment scoring Red (nothing else red)
    # satisfied both halves of that condition trivially and got force-escalated
    # to overall Red off a dimension that's just 10% of the weighted score.
    # "Compounding" requires a *second, independent* Red signal alongside
    # sentiment, not sentiment counted against itself.
    other_red_dims = [d for d in red_dims if d != "sentiment"]
    if other_red_dims and dimension_scores.get("sentiment") == RED:
        overall = RED
        override_reasons.append(
            f"Override: {', '.join(other_red_dims)} scored Red, compounded by negative, worsening sentiment."
        )

    return {
        "overall_label": LABELS[overall],
        "weighted_score": round(weighted, 2),
        "dimension_labels": {d: LABELS[s] for d, s in dimension_scores.items()},
        "dimension_reasons": dimension_reasons,
        "override_reasons": override_reasons,
    }
