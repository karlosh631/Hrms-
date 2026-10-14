#!/usr/bin/env python3
"""
Daily IT News Digest bot.

- Uses Gemini (with Google Search grounding) to find the top 5 IT/tech stories
  of the last ~48h and writes a 50+ line article for each one.
- Saves everything to news/YYYY-MM-DD.md and commits it in many small commits
  (random 80-100 per run), then the workflow pushes once.

Setup:
  export GEMINI_API_KEY="..."     (in GitHub: Settings > Secrets > Actions)
Optional env vars:
  GEMINI_MODEL   preferred model; default tries gemini-3.8-flash, then older fallbacks
  MIN_COMMITS    default: 80
  MAX_COMMITS    default: 100
  FORCE          set to 1 to regenerate even if today's file already exists
"""

import math
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# Tried in order; a model that returns 404 (retired / not available to this key) is skipped.
MODEL_CANDIDATES = [m for m in [
    os.environ.get("GEMINI_MODEL", "").strip(),
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
] if m]
MIN_COMMITS = int(os.environ.get("MIN_COMMITS", "80"))
MAX_COMMITS = int(os.environ.get("MAX_COMMITS", "100"))
FORCE = os.environ.get("FORCE") == "1"

NEWS_DIR = "news"
MIN_ARTICLE_LINES = 50
STORY_COUNT = 5
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_model_idx = 0  # index into MODEL_CANDIDATES; advances when a model 404s


# ----------------------------------------------------------------- Gemini ---
def gemini(prompt, grounded=True, retries=4):
    """Call Gemini. Returns (text, [(title, uri), ...])."""
    global _model_idx
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if grounded:
        body["tools"] = [{"google_search": {}}]
    headers = {"Content-Type": "application/json", "x-goog-api-key": API_KEY}

    last_err = None
    attempt = 0
    while attempt < retries:
        attempt += 1
        model = MODEL_CANDIDATES[_model_idx]
        try:
            r = requests.post(f"{BASE_URL}/{model}:generateContent",
                              json=body, headers=headers, timeout=180)
            if r.status_code == 404 and _model_idx + 1 < len(MODEL_CANDIDATES):
                print(f"  model '{model}' not available (404); trying "
                      f"'{MODEL_CANDIDATES[_model_idx + 1]}'")
                _model_idx += 1
                attempt -= 1  # switching models doesn't use up a retry
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code} from {model}: {r.text[:300]}")
            data = r.json()
            cand = data["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()
            chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
            sources = []
            for c in chunks:
                w = c.get("web")
                if w and w.get("uri"):
                    sources.append((w.get("title", "source"), w["uri"]))
            if not text:
                raise RuntimeError("empty response")
            return text, sources
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 5 * attempt
            print(f"  Gemini call failed ({e}); retry {attempt}/{retries} in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Gemini failed after {retries} attempts: {last_err}")


def find_top_stories(today):
    prompt = f"""Today is {today}. Using Google Search, find the {STORY_COUNT} most important
IT / technology news stories from the last 48 hours (software, AI, cybersecurity,
cloud, hardware, big-tech, developer tools). Pick distinct stories.

Output EXACTLY {STORY_COUNT} blocks separated by a line containing only =====
Each block must be:
TITLE: <headline in plain text>
SUMMARY: <one sentence>

No other text."""
    text, _ = gemini(prompt, grounded=True)
    stories = []
    for block in re.split(r"^\s*=====\s*$", text, flags=re.M):
        t = re.search(r"TITLE:\s*(.+)", block)
        s = re.search(r"SUMMARY:\s*(.+)", block)
        if t:
            stories.append((t.group(1).strip().strip("*"), s.group(1).strip() if s else ""))
    return stories[:STORY_COUNT]


def nonempty(lines):
    return [l for l in lines if l.strip()]


def write_article(title, summary, today):
    prompt = f"""Today is {today}. Using Google Search to verify facts, write a detailed
news article about this IT story:

Title: {title}
Context: {summary}

Rules:
- At least 60 lines. ONE short sentence or bullet per line, max ~25 words each.
- Blank line between paragraphs. Use these markdown sections: "### Overview",
  "### What happened", "### Why it matters", "### Technical details",
  "### Industry reaction", "### What to watch next".
- Only state facts you can support from search results. Do not invent quotes,
  numbers or dates. If something is unknown, say so.
- Do NOT include the title heading and do NOT include a sources list (added separately).
- Output only the article body."""
    best, best_sources = [], []
    for _ in range(3):
        text, sources = gemini(prompt, grounded=True)
        lines = text.splitlines()
        if len(nonempty(lines)) > len(nonempty(best)):
            best, best_sources = lines, sources
        if len(nonempty(best)) >= MIN_ARTICLE_LINES:
            break
        prompt += "\n\nIMPORTANT: your last answer was too short. Write MORE lines (65+)."
    return best, best_sources


# -------------------------------------------------------------- Build doc ---
def build_document(today):
    stories = find_top_stories(today)
    if len(stories) < STORY_COUNT:
        raise RuntimeError(f"Only found {len(stories)} stories, expected {STORY_COUNT}")

    doc = [(f"# IT News Digest - {today}", "header"), ("", "header"),
           ("> Auto-generated daily with Gemini + Google Search grounding. "
            "Verify important details against the linked sources.", "header"), ("", "header")]

    for i, (title, summary) in enumerate(stories, 1):
        print(f"[{i}/{STORY_COUNT}] writing: {title}")
        body, sources = write_article(title, summary, today)
        if len(nonempty(body)) < MIN_ARTICLE_LINES:
            print("  skipped: article too short")
            continue
        label = f"story {i}: {title[:60]}"
        doc.append((f"## {i}. {title}", label))
        doc.append(("", label))
        doc.extend((l.rstrip(), label) for l in body)
        doc.append(("", label))
        seen = set()
        doc.append(("### Sources", label))
        for t, u in sources:
            if u not in seen:
                seen.add(u)
                doc.append((f"- [{t}]({u})", label))
        doc.append(("", label))
    return doc


# -------------------------------------------------------------------- Git ---
def git(*args):
    subprocess.run(["git", *args], check=True)


def commit_in_chunks(path, doc):
    total = len(doc)
    n = min(random.randint(MIN_COMMITS, MAX_COMMITS), total)
    size = total / n
    os.makedirs(os.path.dirname(path), exist_ok=True)
    written = []
    start = 0
    for c in range(1, n + 1):
        end = total if c == n else int(round(c * size))
        part = doc[start:end]
        start = end
        if not part:
            continue
        written.extend(part)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(l for l, _ in written) + "\n")
        label = part[-1][1]
        git("add", path)
        git("commit", "-m", f"news: {label} ({c}/{n})", "--quiet")
    print(f"Created {n} commits for {path} ({total} lines)")


def main():
    if not API_KEY:
        sys.exit("GEMINI_API_KEY is not set")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(NEWS_DIR, f"{today}.md")
    if os.path.exists(path) and not FORCE:
        print(f"{path} already exists; nothing to do (set FORCE=1 to redo).")
        return

    doc = build_document(today)
    if len(nonempty([l for l, _ in doc])) < MIN_ARTICLE_LINES * 3:
        sys.exit("Too little content generated; aborting without committing.")
    commit_in_chunks(path, doc)


if __name__ == "__main__":
    main()
