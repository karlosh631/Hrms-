#!/usr/bin/env python3
"""
Append human-like developer content to a randomized set of target files,
or perform a randomized "behavior" such as adding a CHANGELOG entry or updating README.

Outputs:
- .commit_message   : selected commit message (one line)
- .modified_files   : newline-separated list of files that were modified (staged by workflow)

Paths:
- scripts/commit_messages.txt   (external file you can edit)
- scripts/daily_contributor.py  (this script)
"""

import random
import os
from datetime import datetime

COMMIT_MESSAGES_FILE = "scripts/commit_messages.txt"

# Expanded target file list to create varied activity
TARGET_FILES = [
    "README.md",
    "CHANGELOG.md",
    "docs/dev_notes.md",
    "docs/meeting_notes.md",
    "docs/quick_tips.md",
    "notes/journal.log",
    "notes/todo_list.md",
    "CONTRIBUTING.md",
    "docs/architecture_notes.md",
    "docs/setup.md"
]

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

def ensure_parent_dir(path):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

def pick_commit_message():
    if not os.path.exists(COMMIT_MESSAGES_FILE):
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

def append_lines_to_file(path, n_lines):
    ensure_parent_dir(path)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"\n<!-- auto-updated: {datetime.utcnow().isoformat()} -->\n")
        for _ in range(n_lines):
            fh.write(make_line() + "\n")

def prepend_changelog_entry(path):
    ensure_parent_dir(path)
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    entry = f"- {ts}: automated daily note — quick status update.\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            existing = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(entry + "\n" + existing)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Changelog\n\n")
            fh.write(entry)

def update_readme_tip(path):
    ensure_parent_dir(path)
    tip = f"\n> Tip ({datetime.utcnow().strftime('%Y-%m-%d')}): Small dev note — check CONTRIBUTING.md for PR guidelines.\n"
    # Append tip to README to keep behavior unobtrusive
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(tip)

def touch_contributing(path):
    ensure_parent_dir(path)
    line = f"\n- Quick suggestion ({datetime.utcnow().strftime('%Y-%m-%d')}): add CI badge to README.\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)

def write_outputs(commit_msg, modified_files):
    with open(COMMIT_MSG_OUT, "w", encoding="utf-8") as fh:
        fh.write(commit_msg + "\n")
    with open(MODIFIED_FILES_OUT, "w", encoding="utf-8") as fh:
        for p in modified_files:
            fh.write(p + "\n")

def main():
    # Decide on behavior type to increase variety
    # probabilities: append_bundle 60%, changelog 15%, readme_tip 15%, contributing_touch 10%
    r = random.random()
    modified = []
    if r < 0.60:
        # Append to 1-3 files
        n_lines = random.randint(5, 10)
        n_files = random.randint(1, 3)
        chosen = random.sample(TARGET_FILES, k=n_files)
        for f in chosen:
            append_lines_to_file(f, n_lines)
            modified.append(f)
    elif r < 0.75:
        # Prepend a changelog entry
        prepend_changelog_entry("CHANGELOG.md")
        modified.append("CHANGELOG.md")
        # also sometimes add a dev_notes append to look natural
        if random.random() < 0.4:
            append_lines_to_file("docs/dev_notes.md", random.randint(3,6))
            modified.append("docs/dev_notes.md")
    elif r < 0.90:
        # Update README with a small tip
        update_readme_tip("README.md")
        modified.append("README.md")
        # maybe also append to quick_tips
        if random.random() < 0.3:
            append_lines_to_file("docs/quick_tips.md", random.randint(2,5))
            modified.append("docs/quick_tips.md")
    else:
        # Touch CONTRIBUTING.md or add a note
        touch_contributing("CONTRIBUTING.md")
        modified.append("CONTRIBUTING.md")
        if random.random() < 0.5:
            append_lines_to_file("docs/dev_notes.md", random.randint(2,5))
            modified.append("docs/dev_notes.md")

    # Deduplicate modified list and ensure paths are normalized
    modified = list(dict.fromkeys(modified))

    commit_msg = pick_commit_message()
    write_outputs(commit_msg, modified)

    print(f"Behavior roll: {r:.3f}")
    print(f"Modified files: {modified}")
    print(f"Selected commit message: {commit_msg}")

if __name__ == "__main__":
    main()
