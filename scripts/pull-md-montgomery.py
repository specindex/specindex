#!/usr/bin/env python3
"""Pull Montgomery County MD commercial building permits via Socrata --
verified live 2026-07-27: 41,668 total records, pre-scoped to
`applicationtype='COMMERCIAL BUILDING'` (this dataset is commercial-only
by construction, no filter needed), max issueddate 2026-07-24. Real
`city` field populated on ~96.5% of rows -- directly fixes MD's
near-zero city-field gap.

Usage:
    python3 scripts/pull-md-montgomery.py --months 24 [--merge]
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
DOMAIN = "data.montgomerycountymd.gov"
DATASET = "i26v-w6bd"


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
    if "medical" in t or "hospital" in t:
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
    rows = query_socrata(
        DOMAIN, DATASET,
        where=f"applicationtype='COMMERCIAL BUILDING' AND issueddate > '{cutoff.isoformat()}'",
        select="permitno,stno,stname,suffix,city,zip,issueddate,buildingarea,"
        "declaredvaluation,description,worktype,usecode,location",
    )
    projects, seen = [], set()
    for r in rows:
        permit_no = str(r.get("permitno") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (r.get("description") or "").strip()
        worktype = (r.get("worktype") or "").strip()
        usecode = (r.get("usecode") or "").strip()
        ptype = project_type_from(f"{desc} {worktype} {usecode}")
        try:
            value = float(r.get("declaredvaluation") or 0)
        except (TypeError, ValueError):
            value = 0
        try:
            sqft = float(r.get("buildingarea") or 0)
        except (TypeError, ValueError):
            sqft = 0
        addr = " ".join(s for s in [r.get("stno"), r.get("stname"), r.get("suffix")] if s).strip()
        city = (r.get("city") or "Montgomery County").strip().title()
        opened = (r.get("issueddate") or "")[:10] or None
        loc = r.get("location") or {}
        coords = loc.get("coordinates") if isinstance(loc, dict) else None
        lat, lon = (coords[1], coords[0]) if coords and len(coords) == 2 else (None, None)
        name = desc[:120] or f"Montgomery County MD commercial permit {permit_no}"
        projects.append({
            "id": f"md-montgomery-{slugify(permit_no)}",
            "name": name,
            "city": city,
            "county": "Montgomery",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value > 0 else None,
            "square_footage": sqft if sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Montgomery County MD commercial permit {permit_no} ({worktype or 'permit'}): {desc or 'No description provided'}. {addr}.",
            "key_specs": [s for s in [worktype, usecode, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Montgomery County MD commercial permit {permit_no}",
                "url": "https://data.montgomerycountymd.gov/Property-and-Housing/Commercial-Building-Permits/i26v-w6bd",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "MD",
            "latitude": lat,
            "longitude": lon,
            "zip": str(r.get("zip")).strip()[:5] if r.get("zip") else None,
        })
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    projects = pull(cutoff)
    print(f"Montgomery County MD: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("MD", projects)
        print(f"  merged into md.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
