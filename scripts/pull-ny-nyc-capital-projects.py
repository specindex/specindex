#!/usr/bin/env python3
"""Pull NYC's Capital Projects Database (CPDB) -- verified live 2026-07-26
before building:

  - Projects (budget/agency data): data.cityofnewyork.us, dataset fi59-268w
    -- 12,587 total rows, 7,222 with typecategory='Fixed Asset' (physical
    construction, excludes 'Lump Sum' and 'ITT, Vehicles, and Equipment'
    line items), 2,959 of those with totalplannedcommit > $1M.
  - Points (geospatial companion, joined by projectid): dataset h2ic-zdws,
    real lat/lon per project confirmed via a live sample query.

This is city capital construction (libraries, schools, hospitals, public
buildings), not private commercial development -- the same category
SAM.gov/USAspending federal contracts already occupy in this corpus (public
works needing HVAC/electrical/glazing same as any commercial build).
Classified as project_type "civic"/"education"/"healthcare" by agency name
rather than by a description-keyword scan, since CPDB rows are agency
budget lines (e.g. "Central Phase 3") not permit descriptions.

Usage:
    python3 scripts/pull-ny-nyc-capital-projects.py [--merge] [--min-value 1000000]
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
DOMAIN = "data.cityofnewyork.us"
PROJECTS_DATASET = "fi59-268w"
POINTS_DATASET = "h2ic-zdws"

AGENCY_TYPE = {
    "New York Public Library": "civic",
    "Brooklyn Public Library": "civic",
    "Queens Borough Public Library": "civic",
    "New York Research Libraries": "civic",
    "Department of Education": "education",
    "City University of New York": "education",
    "Health and Hospitals Corporation": "healthcare",
    "Department of Health and Mental Hygiene": "healthcare",
    "Department of Parks and Recreation": "civic",
    "Department of Cultural Affairs": "civic",
    "Fire Department": "civic",
    "Police Department": "civic",
    "Department of Correction": "civic",
    "Department of Sanitation": "civic",
    "Department of Homeless Services": "civic",
    "Housing Preservation and Development": "multifamily",
}


def agency_project_type(agency: str) -> str:
    return AGENCY_TYPE.get(agency, "civic")


def categories_for(ptype: str) -> list[str]:
    return {
        "civic": ["hvac", "roofing", "lighting", "fire suppression", "concrete", "glazing"],
        "education": ["hvac", "flooring", "lighting", "fire suppression", "glazing"],
        "healthcare": ["hvac", "medical gas", "elevators", "flooring", "lighting", "fire suppression"],
        "multifamily": ["glazing", "hvac", "elevators", "roofing", "lighting", "flooring"],
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


def pull(min_value: float) -> list[dict]:
    rows = query_socrata(
        DOMAIN,
        PROJECTS_DATASET,
        where=f"typecategory='Fixed Asset' AND totalplannedcommit>{min_value}",
        select="projectid,description,magencyname,mindate,maxdate,totalplannedcommit",
    )
    points = query_socrata(DOMAIN, POINTS_DATASET, select="projectid,the_geom")
    coords: dict[str, tuple[float, float]] = {}
    for pt in points:
        geom = pt.get("the_geom") or {}
        pid = pt.get("projectid")
        coord_list = geom.get("coordinates")
        if pid and coord_list:
            # MultiPoint coordinates: [[lon, lat], ...] -- take the first.
            lon, lat = coord_list[0]
            coords[pid] = (lat, lon)

    projects, seen = [], set()
    for r in rows:
        pid = (r.get("projectid") or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        agency = (r.get("magencyname") or "").strip() or "Unknown"
        ptype = agency_project_type(agency)
        desc = (r.get("description") or "").strip() or f"Capital project {pid}"
        try:
            value = float(r.get("totalplannedcommit") or 0)
        except (TypeError, ValueError):
            value = 0
        lat, lon = coords.get(pid, (None, None))
        opened = (r.get("mindate") or "")[:10] or None
        projects.append({
            "id": f"ny-nyc-cpdb-{slugify(pid)}",
            "name": desc[:120],
            "city": "New York",
            "county": "New York",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value > 0 else None,
            "square_footage": None,
            "owner": agency,
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"NYC capital project ({agency}): {desc}.",
            "key_specs": [agency, f"Project ID {pid}"],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"NYC Capital Projects Database: {pid}",
                "url": f"https://data.cityofnewyork.us/City-Government/Capital-Projects-Database-CPDB-Projects/fi59-268w",
            }],
            "open_for": "Active NYC capital construction line item. Early product/spec window.",
            "state": "NY",
            "latitude": lat,
            "longitude": lon,
        })
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--min-value", type=float, default=1_000_000)
    args = ap.parse_args()

    projects = pull(args.min_value)
    with_coords = sum(1 for p in projects if p["latitude"] is not None)
    print(f"NYC CPDB: {len(projects)} commercial-grade capital projects >= ${args.min_value:,.0f} ({with_coords} geocoded)")

    if args.merge:
        added, total = merge_into_state("NY", projects)
        print(f"  merged into ny.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
