"""
scheduler.py
Bonus (Phase 2): run the agent automatically every week.

This uses APScheduler so it can run as a long-lived process (e.g. in a
container/VM). In most enterprise setups, a simpler and more reliable choice
is to let the OS/orchestrator handle scheduling and just call run_weekly.py
as a script — see the two alternatives below the code.
"""
import subprocess
import sys
import glob
import os
from apscheduler.schedulers.blocking import BlockingScheduler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_all_projects():
    """Loops over every project's task/update file pair found in data/project_plans
    and runs the weekly agent for each.

    Three naming conventions are supported, checked in this order:
      1. Production convention: <project>_tasks.csv / <project>_update.csv —
         a single file per project that the PM/export job overwrites each
         week. This is what a real weekly cron job would point at.
      2. This project's real-data convention: <project>_tasks_current.csv /
         <project>_current_update.csv — the current single-snapshot files
         for the two real Zycus projects (see convert_real_data.py).
      3. The original demo's numbered-snapshot convention:
         <project>_tasks_week{N}.csv / <project>_week{N}_update.csv —
         kept for backwards compatibility if you ever reintroduce
         multi-week sample data.

    (Caught in review: the original version only checked convention #1, so
    running this against either the sample data or the real project data
    found nothing. All three are supported now, checked in the order above.)
    """
    plans_dir = os.path.join(PROJECT_ROOT, "data", "project_plans")
    jobs = []  # list of (project_slug, tasks_path, update_path)

    # Convention 1: production-style single current file per project.
    for tf in glob.glob(os.path.join(plans_dir, "*_tasks.csv")):
        project_slug = os.path.basename(tf).replace("_tasks.csv", "")
        update_file = os.path.join(plans_dir, f"{project_slug}_update.csv")
        if os.path.exists(update_file):
            jobs.append((project_slug, tf, update_file))
        else:
            print(f"[SKIP] no matching update file for {project_slug}")

    # Convention 2: this project's real-data current-snapshot files.
    if not jobs:
        for tf in glob.glob(os.path.join(plans_dir, "*_tasks_current.csv")):
            project_slug = os.path.basename(tf).replace("_tasks_current.csv", "")
            update_file = os.path.join(plans_dir, f"{project_slug}_current_update.csv")
            if os.path.exists(update_file):
                jobs.append((project_slug, tf, update_file))
            else:
                print(f"[SKIP] no matching update file for {project_slug}")

    # Convention 3: numbered weekly snapshots — pick the latest week
    # available for each project so a schedule run always reflects the
    # most recent data, the same way conventions #1/#2 would.
    if not jobs:
        import re
        week_files = glob.glob(os.path.join(plans_dir, "*_tasks_week*.csv"))
        by_project = {}
        for tf in week_files:
            m = re.match(r"(.+)_tasks_week(\d+)\.csv$", os.path.basename(tf))
            if not m:
                continue
            slug, week = m.group(1), int(m.group(2))
            if slug not in by_project or week > by_project[slug][0]:
                by_project[slug] = (week, tf)
        for slug, (week, tf) in by_project.items():
            update_file = os.path.join(plans_dir, f"{slug}_week{week}_update.csv")
            if os.path.exists(update_file):
                jobs.append((slug, tf, update_file))
            else:
                print(f"[SKIP] no matching update file for {slug} week {week}")

    for project_slug, tf, update_file in jobs:
        cmd = [
            # sys.executable, not "python3" — see the same note in
            # run_current_projects.py. "python3" isn't a registered command
            # on most Windows installs and fails there.
            sys.executable, os.path.join(PROJECT_ROOT, "agent", "run_weekly.py"),
            "--tasks", tf, "--update", update_file,
            "--project", project_slug.replace("_", " ").title(),
            "--out", os.path.join(PROJECT_ROOT, "outputs", "weekly", "week1"),
        ]
        subprocess.run(cmd, check=False)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    # Every Monday at 7am
    scheduler.add_job(run_all_projects, "cron", day_of_week="mon", hour=7, minute=0)
    print("Scheduler started. Reports will generate every Monday at 7:00 AM.")
    scheduler.start()

"""
ALTERNATIVE SCHEDULING (recommended for enterprise reliability over a
long-running Python process):

1) Cron (Linux/Mac):
   0 7 * * 1  cd /path/to/project-health-agent && python3 agent/scheduler.py --once
   (add a --once flag calling run_all_projects() directly, then exit)

2) Windows Task Scheduler:
   Trigger: Weekly, Monday, 7:00 AM
   Action:  python.exe C:/path/to/agent/run_weekly.py --tasks ... --update ...

3) GitHub Actions (if data lives in a repo):
   on:
     schedule:
       - cron: '0 12 * * 1'   # 7am ET Monday
   jobs:
     weekly-report:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - run: pip install -r requirements.txt
         - run: python agent/scheduler.py --once
         - run: git add outputs/ && git commit -m "weekly report" && git push
"""
