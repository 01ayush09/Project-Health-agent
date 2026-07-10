"""
reasoning.py
Two jobs that benefit from an LLM rather than pure rules:
  1. Classify stakeholder sentiment from free text (label + trend).
  2. Turn the computed metrics + dimension reasons into a short, plain-English
     narrative a VP or PM could read without translation.

Pluggable backend:
  - If ANTHROPIC_API_KEY is set, calls the real Claude API (model: claude-sonnet-4-6).
  - Otherwise, falls back to a deterministic template-based generator so the
    agent is runnable end-to-end without network access (useful for demos,
    CI, and offline dev).
"""
import os
import json

USE_LIVE_API = bool(os.environ.get("ANTHROPIC_API_KEY"))

if USE_LIVE_API:
    import anthropic
    _client = anthropic.Anthropic()


def _call_claude(system, user_prompt, max_tokens=500):
    resp = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


# ---------- Sentiment ----------

NEGATIVE_WORDS = ["concerned", "frustrated", "unhappy", "escalate", "risk", "delay", "disappointed",
                   "unclear", "pushback", "confused", "slipping", "behind", "worried"]
POSITIVE_WORDS = ["pleased", "happy", "great", "on track", "smooth", "confident", "satisfied", "excited"]


def classify_sentiment(current_notes, prior_notes=None):
    text = f"{current_notes or ''}"
    if not text.strip():
        return {"label": "unknown", "trend": "stable", "rationale": "No stakeholder notes provided."}

    if USE_LIVE_API:
        prompt = (
            "Classify the sentiment of these project stakeholder notes as positive, neutral, or negative, "
            "and note whether it seems to be improving, stable, or worsening compared to the prior week's notes "
            "if provided. Respond ONLY as JSON: {\"label\": \"...\", \"trend\": \"...\", \"rationale\": \"...\"}.\n\n"
            f"Current week notes: {current_notes}\n"
            f"Prior week notes: {prior_notes or 'N/A'}"
        )
        raw = _call_claude("You are a precise, concise project analyst.", prompt, max_tokens=200)
        try:
            return json.loads(raw.strip().strip("`").replace("json\n", ""))
        except Exception:
            pass  # fall through to heuristic fallback below

    # Offline / fallback heuristic
    lower = text.lower()
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in lower)
    pos_hits = sum(1 for w in POSITIVE_WORDS if w in lower)
    if neg_hits > pos_hits:
        label = "negative"
    elif pos_hits > neg_hits:
        label = "positive"
    else:
        label = "neutral"

    trend = "stable"
    if prior_notes:
        prior_lower = prior_notes.lower()
        prior_neg = sum(1 for w in NEGATIVE_WORDS if w in prior_lower)
        if label == "negative" and neg_hits > prior_neg:
            trend = "worsening"
        elif label == "negative" and neg_hits <= prior_neg:
            trend = "stable"
        elif label == "positive":
            trend = "improving" if neg_hits < prior_neg else "stable"

    return {"label": label, "trend": trend, "rationale": f"Heuristic keyword match ({neg_hits} negative, {pos_hits} positive cues)."}


# ---------- Narrative ----------

def generate_narrative(project_name, rag_result, raw_metrics):
    """Returns (narrative_text, source) where source is 'llm' or 'template'.

    Scaling note: in a real Professional Services portfolio, most projects
    in most weeks are Green with nothing unusual to say. Calling the LLM for
    a nuanced paragraph on those adds cost and latency without adding much —
    the template below already says everything a Green report needs to say.
    Skipping the LLM call here specifically (not for sentiment classification,
    which happens earlier and actually feeds the RAG computation itself) is
    the single biggest lever for handling a larger portfolio: it cuts LLM
    calls per run roughly in proportion to how healthy the portfolio is,
    which is exactly when you can most afford to cut them.
    """
    is_clean_green = rag_result["overall_label"] == "Green" and not rag_result["override_reasons"]

    if USE_LIVE_API and not is_clean_green:
        prompt = (
            f"Write a 4-6 sentence plain-English executive summary of this project's health for a status report. "
            f"Project: {project_name}. Overall status: {rag_result['overall_label']}. "
            f"Dimension statuses and reasons: {json.dumps(rag_result['dimension_reasons'], indent=2)}. "
            f"Override reasons (if any): {rag_result['override_reasons']}. "
            "Be direct and specific (name the actual tasks/blockers), avoid jargon, and end with one recommended action."
        )
        try:
            return _call_claude("You are a professional services program manager writing for executives.", prompt, max_tokens=400), "llm"
        except Exception:
            pass  # fall through to template

    # Offline / fallback / clean-Green template-based narrative
    lines = [f"**{project_name} — Overall status: {rag_result['overall_label']}**"]
    for dim, reason in rag_result["dimension_reasons"].items():
        lines.append(f"- {dim.capitalize()} ({rag_result['dimension_labels'][dim]}): {reason}")
    if rag_result["override_reasons"]:
        lines.append("**Escalation flags:** " + " ".join(rag_result["override_reasons"]))

    action = _recommend_action(rag_result)
    lines.append(f"\n**Recommended action:** {action}")
    source = "template (clean Green — LLM call skipped)" if is_clean_green else "template (offline fallback)"
    return "\n".join(lines), source


def _recommend_action(rag_result):
    labels = rag_result["dimension_labels"]
    if labels.get("blockers") == "Red":
        return "Escalate the open blocker(s) to the steering committee this week; they are the primary driver of risk."
    if labels.get("schedule") == "Red" or labels.get("milestones") == "Red":
        return "Re-baseline the schedule with the client and confirm recovery plan for the at-risk milestone(s)."
    if labels.get("budget") == "Red":
        return "Review burn rate with finance and confirm whether a change order or scope adjustment is needed."
    if rag_result["overall_label"] == "Amber":
        return "Monitor closely next week; no client-facing escalation needed yet, but flag internally."
    return "No action needed — maintain current cadence."


# ---------- Portfolio-level narrative (monthly synthesis / deck content) ----------

def generate_portfolio_narrative(facts):
    """Turns the structured facts detected by synthesize.py into the prose
    used on the deck's trend/risk/spotlight/recommendation slides. Same
    pluggable pattern as generate_narrative(): real Claude API call if a key
    is set, deterministic templating off the same facts otherwise — so the
    deck's story is always derived from whatever data was actually fed in,
    never hardcoded to a specific project name or number."""
    if USE_LIVE_API:
        prompt = (
            "You are writing content for a monthly executive project-portfolio deck. "
            "Given these detected facts (JSON), write: "
            "(1) one 2-sentence trend note per project, "
            "(2) 1-3 cross-project risk call-outs (only for patterns that are actually present in the facts — "
            "do not invent a risk category with no supporting facts), "
            "(3) a 2-3 sentence 'bottom line' for the spotlight project, "
            "(4) 3-4 prioritized executive recommendations. "
            "Respond ONLY as JSON with keys: trend_notes (list of {project, title, body}), "
            "risks (list of {title, body}), spotlight_bottom_line (string), "
            "recommendations (list of {title, body}).\n\n"
            f"FACTS: {json.dumps(facts, indent=2, default=str)}"
        )
        try:
            raw = _call_claude("You are a precise, concise PMO analyst who never states a risk the facts don't support.", prompt, max_tokens=1200)
            parsed = json.loads(raw.strip().strip("`").replace("json\n", "", 1))
            parsed["spotlight_project"] = facts["spotlight_project"]
            return parsed
        except Exception:
            pass  # fall through to template-based generation below

    return _template_portfolio_narrative(facts)


def _template_portfolio_narrative(facts):
    pf = facts["project_facts"]

    trend_label = {"declining": "Declining", "improving": "Recovering", "stable": "Stable"}
    status_color_key = {"Red": "red", "Amber": "amber", "Green": "green"}

    trend_notes = []
    for proj, f in pf.items():
        traj = " → ".join(f["trajectory"])
        if f["trend"] == "declining":
            worst_dims = [d for d, s in f["latest_dimension_labels"].items() if s == "Red"]
            reason = f["latest_reasons"].get(worst_dims[0], "") if worst_dims else ""
            body = f"Trajectory: {traj}. {reason}".strip()
        elif f["trend"] == "improving":
            body = f"Trajectory: {traj}. Recovered after corrective action; now {f['latest_status']}."
        else:
            body = f"Trajectory: {traj}. Held steady across all {len(f['trajectory'])} reporting weeks at {f['latest_status']}."
        trend_notes.append({
            "project": proj,
            "title": f"{proj} — {trend_label[f['trend']]}",
            "body": body,
            # Color reflects where the project actually sits today, not just
            # which direction it moved — "stable" at Amber is not the same
            # color story as "stable" at Green (fixed after review: these
            # used to both render green just because neither was trending).
            "color_key": status_color_key[f["latest_status"]],
        })

    # Risks — only generated when the underlying facts actually support them.
    risks = []
    category_projects = facts.get("category_projects", {})
    touched = sorted({p for projs in category_projects.values() for p in projs})
    if len(touched) >= 2:
        cat_summaries = [f"{cat} ({', '.join(projs)})" for cat, projs in category_projects.items()]
        risks.append({
            "title": "Third-Party / Resourcing Dependency Risk",
            "body": f"{len(touched)} of {facts['total_projects']} active projects hit a dependency-related blocker this month — {'; '.join(cat_summaries)}. Different root causes, same pattern: this is a portfolio-level delivery risk, not a one-off, and worth a standing vendor/resourcing escalation path rather than per-project firefighting.",
        })

    if facts["overspend_events"]:
        worst = max(facts["overspend_events"], key=lambda e: e["burn_ratio"])
        risks.append({
            "title": "Overspend Correlates With Schedule Slip",
            "body": f"{worst['project']}'s budget burn reached {round(worst['burn_ratio']*100)}% of plan in the week ending {worst['week_ending']}, the same week its overall status was {worst['status_that_week']} — spend accelerating to chase a slipping date typically front-loads cost without recovering time.",
        })

    if facts["sentiment_lead_events"]:
        ev = facts["sentiment_lead_events"][0]
        risks.append({
            "title": "Sentiment Is a Leading Indicator, Not a Lagging One",
            "body": f"On {ev['project']}, client sentiment turned negative in the week ending {ev['negative_week']}, {ev['lead_weeks']} week(s) before the status flipped to Red on {ev['red_week']}. Treating sentiment dips as an early-warning trigger — not just a symptom — would buy real lead time portfolio-wide.",
        })

    if not risks:
        risks.append({
            "title": "No Significant Cross-Project Risk Patterns Detected",
            "body": "No recurring blockers, correlated overspend, or leading-sentiment patterns were detected across the portfolio this period.",
        })

    # Spotlight
    spotlight_name = facts["spotlight_project"]
    spot = pf.get(spotlight_name, {})
    worst_dims = [d for d, s in spot.get("latest_dimension_labels", {}).items() if s == "Red"]
    if worst_dims:
        primary_reason = spot["latest_reasons"].get(worst_dims[0], "")
        bottom_line = (
            f"{primary_reason} This requires executive-level attention this cycle — "
            f"{spot.get('recommended_action', 'follow up directly with the project team')}"
        )
    else:
        bottom_line = spot.get("recommended_action", "Monitor next week; no immediate escalation required.")

    # Recommendations — built from whichever risks/spotlight actually fired.
    recommendations = []
    if worst_dims:
        recommendations.append({
            "title": f"Address the {spotlight_name} {worst_dims[0]} issue this week",
            "body": spot["latest_reasons"].get(worst_dims[0], ""),
        })
    for r in risks:
        if r["title"] != "No Significant Cross-Project Risk Patterns Detected":
            recommendations.append({"title": f"Act on: {r['title']}", "body": r["body"]})
    if facts["projects_improving"]:
        recommendations.append({
            "title": f"Use {facts['projects_improving'][0]}'s recovery as an internal playbook",
            "body": "Document what specifically reversed the decline so other PMs facing similar risk patterns can apply it faster.",
        })
    if not recommendations:
        recommendations.append({
            "title": "Maintain current cadence",
            "body": "No portfolio-level risks or declining projects were detected this period.",
        })

    return {
        "trend_notes": trend_notes,
        "risks": risks,
        "spotlight_project": spotlight_name,
        "spotlight_bottom_line": bottom_line,
        "recommendations": recommendations,
    }
