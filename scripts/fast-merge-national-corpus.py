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

    # Split the headline number by record class.
    #
    # The corpus blends two different things: county PERMIT records, which are
    # what county-coverage reporting measures, and FEDERAL AWARD records from
    # sam_gov / usaspending, which are statewide and carry no county at all.
    # 100 of 254 configs are federal, and their ~16,000 rows are invisible to
    # every (county, state) join -- so quoting one combined total silently
    # overstates permit coverage. Report both.
    #
    # Classified by id segment rather than by adding a field to 600K+ rows:
    # the pipeline already prefixes ids as {state}-{feed}-{record}.
    FEDERAL_FEEDS = {"usaspending", "sam"}

    def is_federal(p: dict) -> bool:
        parts = (p.get("id") or "").split("-")
        return len(parts) > 1 and parts[1] in FEDERAL_FEEDS

    federal = sum(1 for p in deduped if is_federal(p))
    permits = len(deduped) - federal

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
            # permit_projects is the number county-coverage reporting is about;
            # federal_awards are statewide and have no county.
            "permit_projects": permits,
            "federal_awards": federal,
            "states": len(states_covered),
        },
        "notes": (
            f"{len(deduped)} records across {len(states_covered)} states "
            f"({permits} county permit projects + {federal} federal awards). "
            "Fast rebuild (no cross-source pairwise merge) -- see "
            "fast-merge-national-corpus.py docstring."
        ),
    }

    text = json.dumps(payload, indent=2) + "\n"
    OUT.write_text(text)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(text)
    print(f"Fast-merged {len(deduped)} records from {len(states_covered)} states -> {OUT}")
    print(f"   county permit projects: {permits:,}")
    print(f"   federal awards (no county, statewide): {federal:,}")


if __name__ == "__main__":
    main()
