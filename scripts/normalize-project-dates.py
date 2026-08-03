#!/usr/bin/env python3
"""Backfill-normalize `opened_or_announced_date` across all state corpus files.

Why this exists (2026-08-03): a coverage audit of the top-50 counties showed
several counties onboarded earlier the same night reporting ~0 projects since
2025-01-01 despite thousands of in-window rows. Root cause: 10.8% of the corpus
(43,731 projects) carried an unusable date --

  * 24,168 raw epoch values never converted at all (Clark NV's 8,151 rows all
    store `"1784851200"`, a 10-digit epoch-SECONDS string). These predate
    `generic_mapping._iso_date()` existing, so nothing ever normalized them.
  * 7,385 otherwise malformed (bare YYYYMMDD ints, timestamps with trailing
    junk, MM/DD/YYYY with a time suffix).
  * 12,178 null/empty -- left alone here; a missing date is a source gap, not a
    formatting bug, and inventing one would be worse than leaving it null.

`_iso_date()` itself was also fixed in the same change: its epoch branch matched
`\\d{10,}` and divided by 1000 unconditionally, i.e. it assumed milliseconds and
would have turned a 10-digit seconds value into a 1970 date. It now switches on
magnitude. This script applies the corrected logic to data already on disk.

Date correctness is load-bearing for the standing goal (capture everything since
2025-01-01): any date-filtered query silently drops these rows, which is exactly
how the audit came to report "Clark NV: 0 projects since 2025" for a county that
actually has 8,151 in-window.

Idempotent -- rows already in YYYY-MM-DD form are left untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "state_agent_pipeline"))

from core.ingestion.generic_mapping import _iso_date  # noqa: E402

ISO_LEN = 10


def looks_iso(v: object) -> bool:
    s = str(v)
    return (
        len(s) >= ISO_LEN
        and s[4] == "-"
        and s[7] == "-"
        and s[:4].isdigit()
        and s[5:7].isdigit()
        and s[8:10].isdigit()
    )


def normalize_file(path: Path, apply: bool) -> Counter:
    stats: Counter = Counter()
    doc = json.loads(path.read_text())
    projects = doc["projects"] if isinstance(doc, dict) and "projects" in doc else doc

    for p in projects:
        raw = p.get("opened_or_announced_date")
        if raw in (None, ""):
            stats["null_left_alone"] += 1
            continue
        if looks_iso(raw):
            # Trim any time suffix so everything is a clean YYYY-MM-DD.
            trimmed = str(raw)[:ISO_LEN]
            if trimmed != raw:
                stats["trimmed"] += 1
                if apply:
                    p["opened_or_announced_date"] = trimmed
            else:
                stats["already_ok"] += 1
            continue

        fixed = _iso_date(raw)
        if fixed and looks_iso(fixed):
            stats["fixed"] += 1
            if apply:
                p["opened_or_announced_date"] = fixed
        else:
            # Could not be rescued -- leave the original rather than destroy it,
            # and report it so the source's mapping can be fixed upstream.
            stats["unrescuable"] += 1

    if apply and (stats["fixed"] or stats["trimmed"]):
        path.write_text(json.dumps(doc, indent=2) + "\n")
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Without this, runs as a dry-run report only.",
    )
    args = ap.parse_args(argv)

    total: Counter = Counter()
    per_file: list[tuple[str, Counter]] = []
    for path in sorted((ROOT / "data" / "states").glob("*.json")):
        s = normalize_file(path, args.apply)
        total.update(s)
        if s["fixed"] or s["unrescuable"]:
            per_file.append((path.name, s))

    mode = "APPLIED" if args.apply else "DRY RUN (use --apply to write)"
    print(f"=== {mode} ===")
    for name, s in per_file:
        print(f"  {name:<10} fixed={s['fixed']:<7} unrescuable={s['unrescuable']:<6} null={s['null_left_alone']}")
    print("\nTOTals:")
    for k, v in total.most_common():
        print(f"  {k:<18} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
