#!/usr/bin/env python3
"""
Append 5-10 human-like developer note lines to a random selection of target files
and write the chosen commit message to .commit_message and the list of modified files
to .modified_files.

Paths:
- scripts/commit_messages.txt  (external list editable by you)
- scripts/daily_contributor.py (this script)
- .commit_message              (written by script, read by workflow)
- .modified_files              (written by script, read by workflow)
"""

import random
import os
from datetime import datetime

# External commit messages file (one per line). Edit this file to change messages.
COMMIT_MESSAGES_FILE = "scripts/commit_messages.txt"

# Files that the script may update (choose 1-3 each run)
TARGET_FILES = [
    "docs/dev_notes.md",
    "notes/journal.log",
    "docs/meeting_notes.md",
    "docs/quick_tips.md",
    "notes/todo_list.md"
]

# Output helper files that the workflow reads
COMMIT_MSG_OUT = ".commit_message"
MODIFIED_FILES_OUT = ".modified_files"

TEMPLATES = [
    "Quick note: reviewed {component} and left a small TODO about edge-case handling.",
    "Follow-up: reworded docs for {component} and clarified expected inputs.",
    "Investigation: observed flaky behavior around {component}; note to reproduce later.",
    "Housekeeping: removed an outdated comment in {component}.",
    "Reminder: check CI setup that references {component}.",
    "Small tweak: adjusted formatting and examples in {component}.",
    "Progress: sketched optimization idea for {component}; prototype next.",
    "Found: minor typo in {component} docs; corrected phrasing.",
    "Note: added a checklist item for code review of {component}.",
    "Refactor thought: consider splitting {component} into smaller helpers for tests."
]

COMPONENTS = [
    "auth.login",
    "db.connection",
    "api/users",
    "scheduler",
    "task runner",
    "deployment script",
    "CI configuration",
    "docs/setup",
    "error handling",
    "session store"
]


def ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def pick_commit_message():
    if not os.path.exists(COMMIT_MESSAGES_FILE):
        # fallback messages if the external file is missing
        defaults = [
            "docs: update daily development log",
            "refactor: minor notes cleanup",
            "chore: sync workspace notes",
            "style: format internal documentation",
            "chore: daily notes update"
        ]
        return random.choice(defaults)
    with open(COMMIT_MESSAGES_FILE, "r", encoding="utf-8") as fh:
        messages = [line.strip() for line in fh if line.strip()]
    if not messages:
        raise RuntimeError(f"{COMMIT_MESSAGES_FILE} contains no commit messages.")
    return random.choice(messages)


def make_line():
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    template = random.choice(TEMPLATES)
    component = random.choice(COMPONENTS)
    extra = ""
    r = random.random()
    if r < 0.12:
        extra = f" (see issue #{random.randint(10, 400)})"
    elif r < 0.24:
        extra = f" — example: `fix_{random.randint(100,999)}`"
    return f"[{ts}] {template.format(component=component)}{extra}"


def append_lines_to_file(path: str, n_lines: int):
    ensure_parent_dir(path)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"\n<!-- auto-updated: {datetime.utcnow().isoformat()} -->\n")
        for _ in range(n_lines):
            fh.write(make_line() + "\n")


def write_commit_and_modified_files(commit_msg: str, modified_files: list):
    with open(COMMIT_MSG_OUT, "w", encoding="utf-8") as fh:
        fh.write(commit_msg + "\n")
    with open(MODIFIED_FILES_OUT, "w", encoding="utf-8") as fh:
        for p in modified_files:
            fh.write(p + "\n")


def main():
    n_lines = random.randint(5, 10)
    # choose 1-3 different target files each run
    n_files = random.randint(1, 3)
    chosen_files = random.sample(TARGET_FILES, k=n_files)

    for f in chosen_files:
        append_lines_to_file(f, n_lines)

    commit_msg = pick_commit_message()
    write_commit_and_modified_files(commit_msg, chosen_files)

    print(f"Appended {n_lines} lines to {len(chosen_files)} file(s): {chosen_files}")
    print(f"Selected commit message: {commit_msg}")


if __name__ == "__main__":
    main()
