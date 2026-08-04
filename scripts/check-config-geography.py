#!/usr/bin/env python3
"""Detect configs that pull a WIDER geography than their hardcoded `county` label.

Why this exists (2026-08-03): `generic_mapping` takes `county` as a fixed
per-config parameter, not per-row from the source data. So if a config's
`commercial_where` doesn't scope the query to that county, it silently pulls the
entire feed and stamps every row with the wrong county. Two real instances were
found the same day, both invisible until corpus counts were compared against
live source counts:

  * NY-NYC pulled the CITYWIDE NYC DOB filings dataset with county hardcoded
    "New York". Every Brooklyn/Queens/Bronx/Staten Island filing landed in the
    corpus as Manhattan -- 29,910 rows, and it masked the fact that NY-QUEENS
    had never been registered at all (Queens held 1 project against 24,469 live).
  * TX-WILLIAMSON-PERMITS and TX-MIDLAND shared an identical endpoint, layer and
    filter with no geographic discriminator. The service description reads
    "permit requests/applications across all of Midland, Texas"; 110 rows were
    Midland permits stamped Williamson.

Detection: group configs by endpoint (or resource_id). Any endpoint claimed by
configs with two or more DIFFERENT counties is multi-jurisdiction by definition,
so every config on it MUST carry a geographic discriminator in `commercial_where`
-- otherwise they all pull the same rows and disagree about the label.

This is a heuristic, deliberately tuned to few false negatives. A single-config
endpoint is not flagged: a city portal that only ever serves its own city is
legitimately unscoped. Review flagged pairs by hand -- confirm against the
service's own `serviceDescription` and a sample record's address/ZIP, which is
how both real cases were settled.

Exit code 1 if any suspect is found, so this can gate CI.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "state_agent_pipeline"))

from core.state_configs import STATE_CONFIGS  # noqa: E402

# Terms that indicate the WHERE clause actually narrows to a place.
GEO_TERMS = (
    "borough",
    "county",
    "city",
    "jurisdiction",
    "municipal",
    "region",
    "district",
    "fips",
    "township",
    "parish",
)


def has_geo_filter(where: str) -> bool:
    return any(t in (where or "").lower() for t in GEO_TERMS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true", help="Show every shared endpoint, not just suspects.")
    args = ap.parse_args(argv)

    by_endpoint: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
    for key, cfg in STATE_CONFIGS.items():
        ep = cfg.get("endpoint") or cfg.get("resource_id")
        if ep:
            by_endpoint[str(ep)].append((key, cfg))

    suspects: list[tuple[str, str, str]] = []
    shared = 0

    for ep, items in sorted(by_endpoint.items()):
        counties = {c.get("county") for _, c in items if c.get("county")}
        if len(counties) < 2:
            continue
        shared += 1
        unscoped = [(k, c) for k, c in items if not has_geo_filter(c.get("commercial_where") or "")]
        if unscoped or args.verbose:
            print(f"\n{ep[:88]}")
            print(f"  {len(items)} configs across counties: {sorted(counties)}")
            for key, cfg in items:
                ok = has_geo_filter(cfg.get("commercial_where") or "")
                mark = "ok " if ok else "!! "
                print(f"  {mark}{key:<28} county={cfg.get('county') or '-':<18} geo_filter={ok}")
                if not ok:
                    suspects.append((key, str(cfg.get("county") or "-"), ep))

    print(f"\nChecked {len(STATE_CONFIGS)} configs; {shared} endpoints shared across multiple counties.")
    if not suspects:
        print("Config geography check OK (no unscoped multi-jurisdiction configs)")
        return 0

    print(f"\nSUSPECTS ({len(suspects)}) -- each pulls a shared feed with no geographic filter,")
    print("so it stamps every row it fetches with its own hardcoded county:")
    for key, county, ep in suspects:
        print(f"  {key}  labels everything '{county}'  ({ep[:60]})")
    print("\nVerify by hand before changing anything: check the service's own")
    print("serviceDescription and a sample record's address/ZIP to establish which")
    print("jurisdiction the feed really covers, then relabel rows (do NOT delete)")
    print("and scope or remove the offending config.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
