#!/usr/bin/env python3
"""Fast national-corpus rebuild: skips merge-national-corpus.py's O(k^2)
same-bucket pairwise dedupe (project_identity.dedupe_projects), which stalls
for hours once a single (state, county) bucket grows into the tens of
thousands of rows (e.g. NJ post-backfill). Cross-source duplicate merging is
skipped here; load-corpus-to-postgres.py's ON CONFLICT (project_id) upsert
still collapses exact-id duplicates. Use this only as a stopgap for a fast
reload -- merge-national-corpus.py remains the source of truth once its
dedupe bottleneck is fixed.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import assign_unique_ids, ensure_state_prefixed  # noqa: E402

STATES_DIR = ROOT / "data" / "states"
OUT = ROOT / "data" / "national-commercial-projects.json"
PUBLIC = ROOT / "public" / "data" / "national-commercial-projects.json"


def main() -> None:
    all_projects: list[dict] = []
    states_covered: list[str] = []

    for path in sorted(STATES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        code = path.stem.upper()
        projects = data.get("projects") if isinstance(data, dict) else data
        if not isinstance(projects, list) or not projects:
            continue
        normalized = [ensure_state_prefixed(dict(p), code) for p in projects]
        all_projects.extend(assign_unique_ids(normalized, code))
        states_covered.append(code)

    # Re-dedupe ids globally (assign_unique_ids only guarantees uniqueness
    # per-state-file call, and two different state files could in theory
    # both prefix to the same code).
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for p in all_projects:
        if p["id"] in seen_ids:
            continue
        seen_ids.add(p["id"])
        deduped.append(p)

    deduped.sort(
        key=lambda p: (p.get("opened_or_announced_date") or "0000", p.get("name", "")),
        reverse=True,
    )

    payload = {
        "generated_at": date.today().isoformat(),
        "geography": "United States",
        "capture_method": (
            "Multi-jurisdiction web research: state economic development releases, "
            "permit filings, REBusinessOnline, BLDUP, city and county announcements"
        ),
        "states_covered": sorted(states_covered),
        "projects": deduped,
        "stats": {
            "total": len(deduped),
            "states": len(states_covered),
        },
        "notes": (
            f"{len(deduped)} commercial projects across {len(states_covered)} states. "
            "Fast rebuild (no cross-source pairwise merge) -- see "
            "fast-merge-national-corpus.py docstring."
        ),
    }

    text = json.dumps(payload, indent=2) + "\n"
    OUT.write_text(text)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(text)
    print(f"Fast-merged {len(deduped)} projects from {len(states_covered)} states -> {OUT}")


if __name__ == "__main__":
    main()
