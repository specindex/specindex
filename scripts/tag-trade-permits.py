#!/usr/bin/env python3
"""Tag Accela-sourced projects as trade-permit vs substantive-project records.

Background: broadening the commercial-type keyword match to fix Gwinnett's
date-filter bug (2026-07-25) had a side effect of also picking up narrow trade
permit types for Atlanta/Cobb (Electrical, Fire Alarm, Fire Sprinkler, etc.)
that the original narrower filter excluded. These are real permits but far
higher volume and lower signal for BPM brand-visibility purposes than actual
construction/alteration records -- keeping them requires being able to filter
them back out downstream rather than silently dropping or silently keeping
them mixed in.

Adds a "permit_category" field ("trade" or "project") to every record whose
"key_specs" first entry is a recognizable Accela permit-type label. Records
from non-Accela sources, or where the type can't be classified, are left
untouched (no field added).

Usage:
    python3 scripts/tag-trade-permits.py data/raw/ga-accela-commercial.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TRADE_KEYWORDS = re.compile(
    r"electrical|fire alarm|fire sprinkler|plumbing|mechanical|\bhvac\b|gas line|"
    r"elevator|boiler|\bsign\b|low voltage|antenna|backflow|irrigation|"
    r"qcr|express|\brepair\b|contractor info|no construction|"
    r"electrical vehicle|pool(?!\s*(?:facility|building))",
    re.I,
)


def classify(permit_type_label: str) -> str:
    return "trade" if TRADE_KEYWORDS.search(permit_type_label) else "project"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: tag-trade-permits.py <path-to-json>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    data = json.loads(path.read_text())
    projects = data.get("projects", [])

    counts = {"trade": 0, "project": 0, "unclassified": 0}
    for p in projects:
        key_specs = p.get("key_specs") or []
        if not key_specs:
            counts["unclassified"] += 1
            continue
        category = classify(key_specs[0])
        p["permit_category"] = category
        counts[category] += 1

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Tagged {len(projects)} records: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
