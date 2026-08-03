#!/usr/bin/env python3
"""Backfill null `opened_or_announced_date` on state rows from fresh pipeline output.

Why this exists (2026-08-03): Santa Clara and Sacramento held 5,474 rows with a
null date, making them invisible to every windowed query -- two top-25 counties
reading as 1 in-window project each. The cause was a date-mapping bug that has
since been fixed in the configs (`output_date_field`), but that fix only applies
at INGEST. Re-running the pipeline with `--merge-state` did not repair them:
the merge dedupes by id and keeps the record already on disk, so the freshly
fetched rows -- which DO carry correct dates -- were discarded as duplicates.

This closes that specific gap: match fresh pipeline output to existing state rows
by id and fill in a date **only where the existing one is null**. It is the
"explicit id-deduped merge" that the state-file write policy allows.

Deliberately conservative:
  * Only ever fills a NULL date. Never overwrites an existing value, so a bad
    run cannot corrupt good data.
  * Never adds, removes, or reorders rows -- the project count must be identical
    before and after, and the script aborts if it is not.
  * Requires --apply; dry-run by default.
  * Writes atomically via a temp file + os.replace.

Do NOT add an --output flag to this script. A previous incident destroyed ~26,000
projects when a script's --output was pointed at data/states/ca.json, because
--output means "write a new file" and truncated everything already there.

Usage:
    python3 scripts/backfill-dates-from-pipeline-output.py \
        --state-file data/states/ca.json \
        --pipeline-dir data/pipeline/ca-santaclara \
        --pipeline-dir data/pipeline/ca-sacramento
    # then re-run with --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_fresh_dates(dirs: list[Path]) -> dict[str, str]:
    """id -> date, taking the newest run per directory."""
    out: dict[str, str] = {}
    for d in dirs:
        runs = sorted(d.glob("*.json"))
        if not runs:
            print(f"  {d}: no run files", file=sys.stderr)
            continue
        newest = runs[-1]
        payload = json.loads(newest.read_text())
        rows = payload.get("projects") if isinstance(payload, dict) else payload
        n = 0
        for r in rows or []:
            rid, date = r.get("id"), r.get("opened_or_announced_date")
            if rid and date:
                out[str(rid)] = date
                n += 1
        print(f"  {d.name}: {newest.name} -> {n} dated rows")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state-file", required=True, help="e.g. data/states/ca.json")
    ap.add_argument("--pipeline-dir", action="append", required=True,
                    help="Pipeline output dir to read fresh dates from (repeatable).")
    ap.add_argument("--apply", action="store_true", help="Actually write. Dry-run without it.")
    args = ap.parse_args(argv)

    state_path = Path(args.state_file)
    payload = json.loads(state_path.read_text())
    projects = payload["projects"]
    before = len(projects)
    print(f"{state_path}: {before} projects")

    fresh = load_fresh_dates([Path(d) for d in args.pipeline_dir])
    print(f"fresh dated rows available: {len(fresh)}")

    filled = 0
    unmatched_null = 0
    for p in projects:
        if p.get("opened_or_announced_date"):
            continue
        rid = p.get("id")
        date = fresh.get(str(rid)) if rid else None
        if date:
            if args.apply:
                p["opened_or_announced_date"] = date
            filled += 1
        else:
            unmatched_null += 1

    print(f"\nnull dates that CAN be filled : {filled}")
    print(f"null dates with no fresh match: {unmatched_null}")

    if len(projects) != before:
        print("ABORT: project count changed; refusing to write.", file=sys.stderr)
        return 1

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 0

    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload))
    os.replace(tmp, state_path)
    after = len(json.loads(state_path.read_text())["projects"])
    print(f"\nwrote {state_path}: {after} projects (was {before})")
    if after != before:
        print("WARNING: count changed after write -- restore from backup.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
