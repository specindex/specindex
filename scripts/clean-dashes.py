#!/usr/bin/env python3
"""Replace em and en dashes in captured project text with plain punctuation.

The corpus was captured by language models, which favour em dashes heavily. They
read as machine-written on the project pages, so this normalises them:

  name        "Station 33 — Chattanooga"      -> "Station 33, Chattanooga"
  other text  "Just started — early specs."   -> "Just started. Early specs."

Run against data/states/*.json, then re-run merge-national-corpus.py.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATES_DIR = ROOT / "data" / "states"

DASHES = "\u2014\u2013"  # em, en
DASH_RE = re.compile(rf"\s*[{DASHES}]\s*")
# Captures the character after the dash so it can be recased in place.
DASH_NEXT_RE = re.compile(rf"\s*[{DASHES}]\s*(.)")

# Fields where a dash separates a title from its place, so a comma reads best.
COMMA_FIELDS = {"name"}
# Fields of prose where the dash joins clauses, so a sentence break reads best.
SENTENCE_FIELDS = {"description", "open_for", "owner", "architect", "general_contractor"}
LIST_FIELDS = {"key_specs", "competitor_watch", "mentioned_brands"}


def to_comma(text: str) -> str:
    return DASH_RE.sub(", ", text)


def to_sentence(text: str) -> str:
    """Split on the dash and start a new sentence, capitalising where sensible."""

    def repl(match: re.Match[str]) -> str:
        first = match.group(1)
        # Leave numbers, currency and acronyms as they are; only lift lowercase.
        return ". " + (first.upper() if first.islower() else first)

    # A trailing dash with nothing after it has no character to capture.
    return DASH_RE.sub("", DASH_NEXT_RE.sub(repl, text))


def clean_value(field: str, value: str) -> str:
    if not any(d in value for d in DASHES):
        return value
    if field in COMMA_FIELDS:
        return to_comma(value)
    if field in SENTENCE_FIELDS:
        return to_sentence(value)
    return to_comma(value)


def clean_project(project: dict) -> int:
    changes = 0
    for field, value in list(project.items()):
        if isinstance(value, str):
            cleaned = clean_value(field, value)
            if cleaned != value:
                project[field] = cleaned
                changes += 1
        elif isinstance(value, list) and field in LIST_FIELDS:
            for i, item in enumerate(value):
                if isinstance(item, str):
                    cleaned = clean_value(field, item)
                    if cleaned != item:
                        value[i] = cleaned
                        changes += 1

    # Source labels read "Topic — Publication"; a comma keeps the attribution
    # without the dash.
    for source in project.get("sources") or []:
        title = source.get("title")
        if isinstance(title, str):
            cleaned = to_comma(title)
            if cleaned != title:
                source["title"] = cleaned
                changes += 1
    return changes


def main() -> int:
    files = sorted(STATES_DIR.glob("*.json"))
    if not files:
        print(f"No state files found in {STATES_DIR}", file=sys.stderr)
        return 1

    total_changes = 0
    touched_files = 0
    for path in files:
        payload = json.loads(path.read_text())
        projects = payload.get("projects") or []
        changes = sum(clean_project(p) for p in projects)
        if changes:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            touched_files += 1
            total_changes += changes
            print(f"{path.name}: {changes} fields cleaned")

    print(f"\n{total_changes} fields cleaned across {touched_files} of {len(files)} state files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
