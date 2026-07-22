"""
generate_demo_data.py

Why this exists: the two real client exports (UniSan, Titan) are each a
single one-time snapshot, not a week-over-week series — so they can prove
the agent handles messy real data, but they can't exercise the Phase 3
trend/pattern-detection logic (declining vs. improving trajectories,
recurring cross-project blockers, sentiment-leads-status lag, overspend
correlated with slip). This script generates a clearly-labeled SYNTHETIC
3-project x 4-week dataset whose sole purpose is to exercise that logic
end-to-end, the same way a script would generate test fixtures.

Nothing here is real client data or a real client name. Written explicitly
(not randomized) so every number below is traceable to the RAG status it's
meant to produce — see the inline comments per week.

Run: python3 generate_demo_data.py
Writes tasks_<slug>_w<N>.csv and update_<slug>_w<N>.csv into this folder.
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WEEK_ENDINGS = ["2026-06-05", "2026-06-12", "2026-06-19", "2026-06-26"]

def write_tasks(slug, week_idx, rows):
    path = os.path.join(HERE, f"tasks_{slug}_w{week_idx+1}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_name", "planned_end", "actual_end", "percent_complete", "milestone", "owner"])
        w.writerows(rows)

def write_update(slug, week_idx, total_budget, planned, actual, blockers, notes, comments):
    path = os.path.join(HERE, f"update_{slug}_w{week_idx+1}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["week_ending", "total_budget", "budget_planned_to_date", "budget_actual_to_date",
                     "open_blockers", "stakeholder_notes", "pm_comments"])
        w.writerow([WEEK_ENDINGS[week_idx], total_budget, planned, actual, blockers, notes, comments])


# ---------------------------------------------------------------------------
# Meridian Data Migration — DECLINING: Green -> Amber -> Amber -> Red
# Story: a vendor dependency (weeks 2-4) quietly erodes schedule and
# sentiment before finally tripping two milestone/critical-blocker overrides
# in week 4. Demonstrates: declining trajectory, sentiment-leads-status lag,
# vendor/third-party category risk (shared with Cascade), overspend at the
# point of failure.
# ---------------------------------------------------------------------------
MERIDIAN = "meridian"

# Week 1 — clean. Milestone "Data Mapping Sign-off" done on time.
write_tasks(MERIDIAN, 0, [
    ["Data Mapping Sign-off", "2026-06-01", "2026-06-01", 100, "yes", "P. Rao"],
    ["Source System Access Provisioning", "2026-06-03", "2026-06-03", 100, "no", "P. Rao"],
    *[[f"Legacy field extraction task {i}", "2026-06-30", "", 40, "no", "A. Iyer"] for i in range(1, 9)],
])
write_update(MERIDIAN, 0, 500000, 60000, 58000, "",
             "Kickoff went smoothly, client stakeholders engaged and confident in the plan.",
             "No issues to flag this week.")

# Week 2 — vendor blocker appears, mild schedule slip, sentiment turns negative
# (this is the first "negative" sentiment week — feeds sentiment-lead detection).
write_tasks(MERIDIAN, 1, [
    ["Data Mapping Sign-off", "2026-06-01", "2026-06-01", 100, "yes", "P. Rao"],
    ["Environment Build", "2026-06-25", "", 60, "yes", "P. Rao"],  # not yet due, still on track
    ["Source System Access Provisioning", "2026-06-03", "2026-06-03", 100, "no", "P. Rao"],
    *[[f"Legacy field extraction task {i}", "2026-06-08" if i <= 1 else "2026-06-30", "", 40, "no", "A. Iyer"] for i in range(1, 9)],
])
write_update(MERIDIAN, 1, 500000, 130000, 149500, "Vendor API access delayed for legacy system connector",
             "Team is concerned about the vendor delay pushing the connector work out.",
             "Escalated to vendor account manager, awaiting response.")

# Week 3 — vendor blocker persists + a second minor blocker; sentiment worsens
# (more negative language than week 2 -> classifies as worsening).
write_tasks(MERIDIAN, 2, [
    ["Data Mapping Sign-off", "2026-06-01", "2026-06-01", 100, "yes", "P. Rao"],
    ["Environment Build", "2026-06-25", "", 70, "yes", "P. Rao"],  # still not overdue yet
    ["Source System Access Provisioning", "2026-06-03", "2026-06-03", 100, "no", "P. Rao"],
    *[[f"Legacy field extraction task {i}", "2026-06-15" if i <= 2 else "2026-06-30", "", 45, "no", "A. Iyer"] for i in range(1, 9)],
])
write_update(MERIDIAN, 2, 500000, 200000, 236000,
             "Vendor API access delayed for legacy system connector; Legacy extraction owner unclear for two tasks",
             "Client is frustrated with the continued vendor delay and worried about downstream slippage; risk of missing the connector milestone is rising.",
             "Raised to steering committee informally; formal escalation planned if unresolved by next week.")

# Week 4 — Environment Build milestone now overdue, a second milestone also
# slips, vendor blocker is re-tagged critical, budget burn spikes. Multiple
# overrides fire simultaneously (critical blocker, 2+ overdue milestones,
# Red dimension + Red sentiment compounding).
write_tasks(MERIDIAN, 3, [
    ["Data Mapping Sign-off", "2026-06-01", "2026-06-01", 100, "yes", "P. Rao"],
    ["Environment Build", "2026-06-25", "", 75, "yes", "P. Rao"],          # overdue milestone #1
    ["Connector Cutover Readiness Review", "2026-06-20", "", 50, "yes", "A. Iyer"],  # overdue milestone #2
    ["Source System Access Provisioning", "2026-06-03", "2026-06-03", 100, "no", "P. Rao"],
    *[[f"Legacy field extraction task {i}", "2026-06-20" if i <= 4 else "2026-07-05", "", 55, "no", "A. Iyer"] for i in range(1, 9)],
])
write_update(MERIDIAN, 3, 500000, 260000, 351000,
             "Critical: vendor unable to deliver API access, now directly blocking cutover readiness",
             "Client is now clearly concerned and frustrated, worried the vendor delay puts the go-live date at real risk, "
             "and confidence is slipping.",
             "Formally escalated to the vendor's leadership and to our steering committee this week.")


# ---------------------------------------------------------------------------
# Helix ERP Rollout — IMPROVING: Red -> Amber -> Amber -> Green
# Story: opens with a critical resourcing gap (no test owner), which gets
# fixed within a week; schedule and sentiment recover steadily after that.
# Demonstrates: improving trajectory, critical-blocker override resolving,
# resourcing/ownership category, "use this as a playbook" recommendation.
# ---------------------------------------------------------------------------
HELIX = "helix"

# Week 1 — critical blocker (no owner) + milestone overdue -> Red via override.
write_tasks(HELIX, 0, [
    ["Integration Testing", "2026-06-01", "", 30, "yes", ""],  # overdue milestone, no owner
    ["Chart of Accounts Config", "2026-05-28", "2026-05-28", 100, "no", "N. Mehta"],
    *[[f"UAT prep task {i}", "2026-06-20", "", 50, "no", "N. Mehta"] for i in range(1, 9)],
])
write_update(HELIX, 0, 300000, 40000, 41000,
             "Critical: no owner assigned to integration testing, blocking go-live readiness",
             "Client is concerned that ownership of integration testing is unclear, and sees this as a risk to go-live.",
             "Flagged to resourcing lead same day.")

# Week 2 — owner assigned, blocker cleared; still one milestone at risk soon.
write_tasks(HELIX, 1, [
    ["Integration Testing", "2026-06-20", "", 45, "yes", "R. Shah"],  # now owned, due in 2 weeks: at-risk not overdue
    ["Chart of Accounts Config", "2026-05-28", "2026-05-28", 100, "no", "N. Mehta"],
    *[[f"UAT prep task {i}", "2026-06-13" if i <= 2 else "2026-06-25", "", 60, "no", "N. Mehta"] for i in range(1, 9)],
])
write_update(HELIX, 1, 300000, 90000, 100800, "",
             "Team is relieved the ownership question is resolved; cautiously optimistic.",
             "Resourcing gap closed. Watching integration testing milestone closely.")

# Week 3 — schedule and budget continue to normalize; milestone still open
# but tracking to plan (at-risk window, not overdue).
write_tasks(HELIX, 2, [
    ["Integration Testing", "2026-06-20", "", 70, "yes", "R. Shah"],
    ["Chart of Accounts Config", "2026-05-28", "2026-05-28", 100, "no", "N. Mehta"],
    *[[f"UAT prep task {i}", "2026-06-16" if i <= 1 else "2026-06-25", "", 75, "no", "N. Mehta"] for i in range(1, 9)],
])
write_update(HELIX, 2, 300000, 150000, 166500, "",
             "Steady progress this week, no major concerns raised by the client.",
             "On track for the integration testing milestone next week.")

# Week 4 — clean. Milestone completed on time, no blockers.
write_tasks(HELIX, 3, [
    ["Integration Testing", "2026-06-20", "2026-06-19", 100, "yes", "R. Shah"],
    ["Chart of Accounts Config", "2026-05-28", "2026-05-28", 100, "no", "N. Mehta"],
    *[[f"UAT prep task {i}", "2026-07-10", "", 90, "no", "N. Mehta"] for i in range(1, 9)],
])
write_update(HELIX, 3, 300000, 210000, 214200, "",
             "Client is pleased with the recovery and confident in the go-live plan.",
             "No open items. Continuing at current cadence.")


# ---------------------------------------------------------------------------
# Cascade Vendor Onboarding — STABLE (Amber every week)
# Story: a low-grade but never-resolved vendor blocker sits at Amber for the
# whole period. Demonstrates: a stable (non-moving) trajectory, and — paired
# with Meridian's weeks 2-4 — the shared "vendor/third-party dependency"
# category risk that only shows up when you look across projects.
# ---------------------------------------------------------------------------
CASCADE = "cascade"

for wk in range(4):
    write_tasks(CASCADE, wk, [
        ["Sandbox Environment Setup", "2026-06-10", "", 60, "no", "K. Desai"],
        *[[f"Vendor onboarding task {i}", "2026-06-30", "", 55, "no", "K. Desai"] for i in range(1, 10)],
    ])
    write_update(CASCADE, wk, 150000, 20000 * (wk + 1), 23000 * (wk + 1),
                 "Vendor unable to provide sandbox credentials for onboarding integration",
                 "Client is patient but has asked for a firm date on vendor credential delivery.",
                 "Chasing vendor weekly; no escalation yet, monitoring.")

print("Demo dataset written to", HERE)
