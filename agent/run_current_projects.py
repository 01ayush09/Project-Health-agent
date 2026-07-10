"""
run_current_projects.py
Convenience script that runs the weekly agent for both real Zycus projects'
current-status snapshot (as of 2026-07-02) and regenerates outputs/weekly/week1.
Supersedes the old run_all_projects_demo.py, which looped over the fictional
alpha/beta/gamma sample data across 4 weeks — that sample data has been
replaced with the two real project exports (see convert_real_data.py and
the README's "What the current data is" section).
"""
import subprocess
import sys

AS_OF = "2026-07-02"
PROJECTS = [
    ("unisan", "UniSan S2P Implementation"),
    ("titan", "Titan (Outokumpu) S2P Implementation"),
]

for slug, name in PROJECTS:
    subprocess.run([
        # sys.executable (not "python3") is the currently-running Python
        # interpreter's own path. On Windows, only the "python" command is
        # normally registered, not "python3" — calling "python3" directly
        # hits the Microsoft Store's app-execution-alias stub instead of a
        # real interpreter and fails. sys.executable works correctly on
        # Windows, macOS, and Linux, and always uses the active venv.
        sys.executable, "run_weekly.py",
        "--tasks", f"../data/project_plans/{slug}_tasks_current.csv",
        "--update", f"../data/project_plans/{slug}_current_update.csv",
        "--project", name,
        "--as-of", AS_OF,
        "--out", "../outputs/weekly/week1",
    ], check=True)

