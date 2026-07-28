#!/usr/bin/env python3
"""Pull Philadelphia's L&I Building & Zoning Permits via the phl.carto.com
SQL API -- verified live 2026-07-26/27: 928,254 total rows, fresh to the
same day.

Real, verified data-quality trap (worth documenting like the VT Act 250
lesson, but inverted -- here the categorical field itself is misleading,
not merely permissive): `commercialorresidential='Commercial'` does NOT
mean commercial *use*. At least 68% of a sampled "Commercial" +
"New Construction" set were actually multi-family apartment buildings
(Philadelphia's field reflects an administrative permit-category bucket
-- 3+ units routes to "Commercial" -- not the building's actual use).
Fixed by ignoring that field entirely and requiring a positive
non-residential-use keyword in `approvedscopeofwork`, while excluding
"household living"/"dwelling" language. No cost/valuation field exists on
this dataset at all (a real gap vs. most other states' sources).
Coordinates (`geocode_x`/`geocode_y`) are in PA State Plane South feet
(EPSG:2272), not lat/lon -- left null rather than doing a projection
conversion.

Usage:
    python3 scripts/pull-pa-philadelphia.py --months 24 [--merge]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import slugify  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (SpecIndex research; +https://specindex.ai)"}
STATES_DIR = ROOT / "data" / "states"

COMMERCIAL_KEYWORDS = [
    "RETAIL", "OFFICE", "WAREHOUSE", "HOTEL", "RESTAURANT", "COMMERCIAL",
    "MEDICAL", "INDUSTRIAL", "STORE", "BANK", "SCHOOL", "CHURCH",
]
RESIDENTIAL_EXCLUDE = ["HOUSEHOLD LIVING", "DWELLING"]


def query_carto(sql: str) -> list[dict]:
    url = f"https://phl.carto.com/api/v2/sql?{urllib.parse.urlencode({'q': sql})}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    if "error" in data:
        raise RuntimeError(f"Carto query failed: {data['error']}")
    return data["rows"]


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t:
        return "industrial"
    if "hotel" in t:
        return "hospitality"
    if "office" in t or "bank" in t:
        return "office"
    if "retail" in t or "store" in t:
        return "retail"
    if "restaurant" in t:
        return "hospitality"
    if "medical" in t:
        return "healthcare"
    if "school" in t or "church" in t:
        return "education"
    return "other"


def categories_for(ptype: str) -> list[str]:
    return {
        "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression"],
        "office": ["glazing", "hvac", "elevators", "lighting", "flooring", "fire suppression"],
        "retail": ["glazing", "hvac", "roofing", "lighting", "doors and hardware", "fire suppression"],
        "hospitality": ["hvac", "elevators", "flooring", "plumbing fixtures", "lighting", "ff&e"],
        "healthcare": ["hvac", "medical gas", "elevators", "flooring", "lighting", "fire suppression"],
        "education": ["hvac", "roofing", "glazing", "lighting", "flooring", "fire suppression"],
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
    positive = " OR ".join(f"approvedscopeofwork ILIKE '%{kw}%'" for kw in COMMERCIAL_KEYWORDS)
    negative = " AND ".join(f"approvedscopeofwork NOT ILIKE '%{kw}%'" for kw in RESIDENTIAL_EXCLUDE)
    sql = (
        "SELECT permitnumber, approvedscopeofwork, typeofwork, permitissuedate, address, zip "
        "FROM permits "
        f"WHERE permittype='Building' AND permitissuedate > '{cutoff.isoformat()}' "
        f"AND ({positive}) AND {negative} "
        "ORDER BY permitissuedate DESC LIMIT 5000"
    )
    rows = query_carto(sql)
    projects, seen = [], set()
    for r in rows:
        permit_no = str(r.get("permitnumber") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        scope = (r.get("approvedscopeofwork") or "").strip()
        work_type = (r.get("typeofwork") or "").strip()
        ptype = project_type_from(scope)
        addr = (r.get("address") or "").strip()
        zip_code = (r.get("zip") or "").strip()[:5] or None
        opened = (r.get("permitissuedate") or "")[:10] or None
        projects.append({
            "id": f"pa-philadelphia-{slugify(permit_no)}",
            "name": f"{work_type or 'Permit'} — {addr}"[:120] if addr else f"Philadelphia permit {permit_no}",
            "city": "Philadelphia",
            "county": "Philadelphia",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Philadelphia commercial permit {permit_no} ({work_type}): {scope[:300] or 'No description provided'}",
            "key_specs": [s for s in [work_type, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Philadelphia commercial permit {permit_no}",
                "url": "https://www.opendataphilly.org/dataset/licenses-and-inspections-building-and-zoning-permits",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "PA",
            "latitude": None,
            "longitude": None,
            "zip": zip_code,
        })
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    projects = pull(cutoff)
    print(f"Philadelphia PA: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("PA", projects)
        print(f"  merged into pa.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
