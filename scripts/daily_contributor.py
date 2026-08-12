#!/usr/bin/env python3
"""
Append human-like developer content to a randomized set of target files,
or perform a randomized "behavior" such as adding a CHANGELOG entry or updating README.

Outputs:
- .commit_message    : selected commit message (one line)
- .modified_files    : newline-separated list of files that were modified (staged by workflow)

Paths:
- scripts/commit_messages.txt   (external file you can edit)
- scripts/daily_contributor.py  (this script)
"""

import random
import os
from datetime import datetime, timezone

COMMIT_MESSAGES_FILE = "scripts/commit_messages.txt"

# Target file list for varied activity
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
    "Refactor thought: consider splitting {component} into smaller helpers for tests.",
    "Performance review: benchmarked {component} under heavy payload.",
    "Security check: audited permission flags in {component}.",
    "Deprecation notice: flagged legacy interface in {component} for future removal.",
    "Dx improvement: simplified setup commands in {component} guide.",
    "Log adjustment: toned down verbose debug statements in {component}.",
    "Type check: tightened strict mode types across {component}.",
    "Coverage update: added unit test stubs for {component}.",
    "API draft: sketched out REST response contract for {component}.",
    "State sync: investigated race conditions within {component}.",
    "Error handling: added graceful fallback logic inside {component}.",
    "Dependency check: reviewed compatibility of packages used in {component}.",
    "Cache strategy: evaluated TTL values for {component}.",
    "UI alignment: verified design token consistency in {component}.",
    "Telemetry: added event tracking markers to {component}.",
    "Database review: verified indexing strategy on queries in {component}."
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
    "session store",
    "jwt validation",
    "rate limiter",
    "payment gateway wrapper",
    "redis cache pool",
    "notification dispatcher",
    "s3 file uploader",
    "graphql resolver",
    "cors middleware",
    "input sanitizer",
    "logger service",
    "audit trail recorder",
    "feature flag manager",
    "email template engine",
    "websocket handler",
    "rbac permission check",
    "search index sync",
    "background queue worker",
    "health check endpoint",
    "env variable validator",
    "metrics exporter"
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
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
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
        fh.write(f"\n<!-- auto-updated: {datetime.now(timezone.utc).isoformat()} -->\n")
        for _ in range(n_lines):
            fh.write(make_line() + "\n")

def prepend_changelog_entry(path):
    ensure_parent_dir(path)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d GMT")
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
    tip = f"\n> Tip ({datetime.now(timezone.utc).strftime('%Y-%m-%d GMT')}): Small dev note — check CONTRIBUTING.md for PR guidelines.\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(tip)

def touch_contributing(path):
    ensure_parent_dir(path)
    line = f"\n- Quick suggestion ({datetime.now(timezone.utc).strftime('%Y-%m-%d GMT')}): add CI badge to README.\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)

def write_outputs(commit_msg, modified_files):
    with open(COMMIT_MSG_OUT, "w", encoding="utf-8") as fh:
        fh.write(commit_msg + "\n")
    with open(MODIFIED_FILES_OUT, "w", encoding="utf-8") as fh:
        for p in modified_files:
            fh.write(p + "\n")

def main():
    r = random.random()
    modified = []
    if r < 0.60:
        n_lines = random.randint(5, 10)
        n_files = random.randint(1, 3)
        chosen = random.sample(TARGET_FILES, k=n_files)
        for f in chosen:
            append_lines_to_file(f, n_lines)
            modified.append(f)
    elif r < 0.75:
        prepend_changelog_entry("CHANGELOG.md")
        modified.append("CHANGELOG.md")
        if random.random() < 0.4:
            append_lines_to_file("docs/dev_notes.md", random.randint(3, 6))
            modified.append("docs/dev_notes.md")
    elif r < 0.90:
        update_readme_tip("README.md")
        modified.append("README.md")
        if random.random() < 0.3:
            append_lines_to_file("docs/quick_tips.md", random.randint(2, 5))
            modified.append("docs/quick_tips.md")
    else:
        touch_contributing("CONTRIBUTING.md")
        modified.append("CONTRIBUTING.md")
        if random.random() < 0.5:
            append_lines_to_file("docs/dev_notes.md", random.randint(2, 5))
            modified.append("docs/dev_notes.md")

    modified = list(dict.fromkeys(modified))

    commit_msg = pick_commit_message()
    write_outputs(commit_msg, modified)

    print(f"Behavior roll: {r:.3f}")
    print(f"Modified files: {modified}")
    print(f"Selected commit message: {commit_msg}")

if __name__ == "__main__":
    main()
