#!/usr/bin/env python3
"""Pull New Jersey's statewide DCA Construction Permit Data -- verified
live 2026-07-27: 2,755,796 total records, all 21 counties, real
`usegroupdesc` (IBC-style use group) categorical field. NJ's real Tier-0
equivalent -- a statewide, municipality-populated permit register, unlike
most states which only have city/county-level feeds.

Data-quality notes from verification:
  - No street address, project name, or lat/lon -- only `muniname`+
    `county`+`block`/`lot` (parcel reference). Fixes jurisdiction-level
    granularity (the "7.1% have a city field" gap), not street-level
    detail.
  - Real dollar value (`constcost`) and square footage (`squarefeet`)
    ARE present, unlike what first appeared in the schema sample.
  - `permitdate` has garbage far-future values in the raw data (a typo'd
    year like 2925 was observed) -- clamp the upper bound of any date
    filter rather than trusting an unbounded max().
  - `usegroupdesc='Multiple family dwellings'` exists and is excluded
    here (residential), along with 'International Residential Code' and
    single-family use groups.

Usage:
    python3 scripts/pull-nj-dca.py --months 24 [--merge]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import slugify  # noqa: E402
from socrata_adapter import query_socrata  # noqa: E402

STATES_DIR = ROOT / "data" / "states"
DOMAIN = "data.nj.gov"
DATASET = "w9se-dmra"

# Commercial/institutional use groups confirmed live via a distinct-value
# scan -- deliberately excludes "International Residential Code", single-
# and multi-family dwelling groups, and "Accessory buildings and
# miscellaneous structures" (too generic/low-signal).
COMMERCIAL_USE_GROUPS = [
    "Business Uses",
    "Mercantile buildings",
    "Restaurants/Night Clubs",
    "Hotels/motels",
    "Educational",
    "Factory and industrial (low hazard)",
    "Factory and industrial (moderate hazard)",
    "Storage (low hazard)",
    "Storage (moderate hazard)",
    "Institutional",
]


def project_type_from(use_group: str) -> str:
    t = use_group.lower()
    if "factory" in t or "industrial" in t or "storage" in t:
        return "industrial"
    if "hotel" in t:
        return "hospitality"
    if "business" in t:
        return "office"
    if "mercantile" in t:
        return "retail"
    if "restaurant" in t:
        return "hospitality"
    if "educational" in t:
        return "education"
    if "institutional" in t:
        return "civic"
    return "other"


def categories_for(ptype: str) -> list[str]:
    return {
        "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression"],
        "office": ["glazing", "hvac", "elevators", "lighting", "flooring", "fire suppression"],
        "retail": ["glazing", "hvac", "roofing", "lighting", "doors and hardware", "fire suppression"],
        "hospitality": ["hvac", "elevators", "flooring", "plumbing fixtures", "lighting", "ff&e"],
        "education": ["hvac", "roofing", "glazing", "lighting", "flooring", "fire suppression"],
        "civic": ["hvac", "roofing", "lighting", "fire suppression", "concrete", "glazing"],
    }.get(ptype, ["hvac", "roofing", "lighting", "concrete", "fire suppression"])


def merge_into_state(state: str, new_projects: list[dict]) -> tuple[int, int]:
    path = STATES_DIR / f"{state.lower()}.json"
    data = json.loads(path.read_text()) if path.exists() else {
        "state": state, "generated_at": dt.date.today().isoformat(),
        "date_range": "N/A", "capture_method": "", "projects": [], "stats": {},
    }
    existing = data.get("projects") or []
    existing_ids = {p["id"] for p in existing}
    added = 0
    for p in new_projects:
        if p["id"] in existing_ids:
            continue
        existing.append(p)
        existing_ids.add(p["id"])
        added += 1
    data["projects"] = existing
    data["stats"] = {**(data.get("stats") or {}), "total": len(existing)}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added, len(existing)


def pull(cutoff: dt.date) -> list[dict]:
    today = dt.date.today().isoformat()
    use_group_clause = " OR ".join(f"usegroupdesc='{g}'" for g in COMMERCIAL_USE_GROUPS)
    where = f"({use_group_clause}) AND permitdate > '{cutoff.isoformat()}' AND permitdate <= '{today}'"
    rows = query_socrata(
        DOMAIN, DATASET,
        where=where,
        select="permitno,muniname,county,usegroupdesc,permittypedesc,permitdate,constcost,squarefeet,block,lot",
    )
    projects, seen = [], set()
    for r in rows:
        permit_no = str(r.get("permitno") or "").strip()
        muni = (r.get("muniname") or "").strip()
        uid = slugify(f"{muni}-{permit_no}")
        if not permit_no or not uid or uid in seen:
            continue
        seen.add(uid)
        use_group = (r.get("usegroupdesc") or "").strip()
        permit_type = (r.get("permittypedesc") or "").strip()
        ptype = project_type_from(use_group)
        try:
            cost = float(r.get("constcost") or 0)
        except (TypeError, ValueError):
            cost = 0
        try:
            sqft = float(r.get("squarefeet") or 0)
        except (TypeError, ValueError):
            sqft = 0
        county = (r.get("county") or "").strip().title()
        date_str = (r.get("permitdate") or "")[:10]
        block, lot = r.get("block"), r.get("lot")
        projects.append({
            "id": f"nj-dca-{uid}",
            "name": f"{permit_type or use_group} — {muni.title()}"[:120],
            "city": muni.title(),
            "county": county,
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost > 0 else None,
            "square_footage": sqft if sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": date_str or None,
            "description": f"New Jersey commercial construction permit {permit_no} ({muni.title()}, {county} County): {use_group}, {permit_type or 'permit type not specified'}.",
            "key_specs": [s for s in [use_group, permit_type, f"Block {block} Lot {lot}" if block and lot else None] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"NJ DCA construction permit {permit_no}",
                "url": "https://data.nj.gov/Reference-Data/NJ-Construction-Permit-Data/w9se-dmra",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "NJ",
            "latitude": None,
            "longitude": None,
        })
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    projects = pull(cutoff)
    print(f"NJ DCA: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("NJ", projects)
        print(f"  merged into nj.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
