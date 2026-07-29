#!/usr/bin/env python3
"""Fail if any data/states/*.json (or the national corpus) has duplicate
project ids.

Exists because of a real bug (2026-07-28): a retroactive id-cleanup
script bypassed persist.py's merge_into_state() id-exact-match dedup and
silently wrote 867 duplicate records into fl.json + 2 into az.json.
Caught manually before that commit; this makes the check automatic so it
can't happen silently again -- run in CI on every PR/push touching the
corpus (see .github/workflows/check-corpus-integrity.yml), and safe to
run locally before merging any new source.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_file(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"{path}: invalid JSON ({e})"]
    projects = data.get("projects") if isinstance(data, dict) else data
    if not isinstance(projects, list):
        return [f"{path}: no 'projects' list found"]
    ids = [p.get("id") for p in projects if isinstance(p, dict)]
    counts = Counter(ids)
    dupes = {i: n for i, n in counts.items() if i and n > 1}
    if not dupes:
        return []
    lines = [f"{path}: {len(dupes)} duplicate id(s), {sum(dupes.values()) - len(dupes)} extra record(s)"]
    for i, n in sorted(dupes.items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"  {i!r} appears {n}x")
    if len(dupes) > 10:
        lines.append(f"  ... and {len(dupes) - 10} more")
    return lines


def main() -> int:
    targets = sorted((ROOT / "data" / "states").glob("*.json"))
    national = ROOT / "public" / "data" / "national-commercial-projects.json"
    if national.exists():
        targets.append(national)

    problems: list[str] = []
    for path in targets:
        problems.extend(check_file(path))

    if problems:
        print("Corpus integrity check FAILED:\n")
        print("\n".join(problems))
        return 1

    print(f"Corpus integrity check OK ({len(targets)} files, no duplicate ids)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
