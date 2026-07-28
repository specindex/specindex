#!/usr/bin/env python3
"""Pull Cincinnati building permits via Socrata (Tyler Data & Insights) --
verified live 2026-07-27: 178,428 total records, max issueddate 2026-07-24.
`permitclass='OBC'` (Ohio Building Code) vs 'RCO' (Residential Code of
Ohio) is the real categorical split. Note: OBC still includes R-2/R-3/R-4
occupancy codes (apartment/institutional-residential reviewed under
commercial code) -- kept per this corpus's existing rule ("drop
residential unless clearly commercial multifamily"). `jurisdiction` is
100% 'CINCINNATI' -- city only, no county-wide coverage despite CAGIS
branding. `proposeduse` values come back with literal embedded quote
characters (e.g. '"B"') -- stripped when used.

Usage:
    python3 scripts/pull-oh-cincinnati.py --months 24 [--merge]
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
DOMAIN = "data.cincinnati-oh.gov"
DATASET = "uhjb-xac9"


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t or "factory" in t:
        return "industrial"
    if "hotel" in t:
        return "hospitality"
    if "office" in t or "business" in t:
        return "office"
    if "retail" in t or "mercantile" in t or "store" in t:
        return "retail"
    if "restaurant" in t or "assembly" in t:
        return "hospitality"
    if "medical" in t or "hospital" in t or "institutional" in t:
        return "healthcare"
    if "school" in t or "educational" in t:
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
        where=f"permitclass='OBC' AND issueddate > '{cutoff.isoformat()}'",
        select="permitnum,description,issueddate,originaladdress1,originalcity,"
        "workclassmapped,companyname,totalsqft,estprojectcostdec,proposeduse,link,neighborhood",
    )
    projects, seen = [], set()
    for r in rows:
        permit_no = str(r.get("permitnum") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (r.get("description") or "").strip()
        proposed_use = (r.get("proposeduse") or "").strip().strip('"')
        workclass = (r.get("workclassmapped") or "").strip()
        ptype = project_type_from(f"{desc} {proposed_use} {workclass}")
        try:
            cost = float(r.get("estprojectcostdec") or 0)
        except (TypeError, ValueError):
            cost = 0
        try:
            sqft = float(r.get("totalsqft") or 0)
        except (TypeError, ValueError):
            sqft = 0
        addr = (r.get("originaladdress1") or "").strip()
        city = (r.get("originalcity") or "Cincinnati").strip().title()
        opened = (r.get("issueddate") or "")[:10] or None
        company = (r.get("companyname") or "").strip().title()
        link = (r.get("link") or "").strip() or None
        name = desc[:120] or f"Cincinnati commercial permit {permit_no}"
        projects.append({
            "id": f"oh-cincinnati-{slugify(permit_no)}",
            "name": name,
            "city": city,
            "county": "Hamilton",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost > 0 else None,
            "square_footage": sqft if sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": company,
            "opened_or_announced_date": opened,
            "description": f"Cincinnati commercial permit {permit_no} ({workclass or 'OBC'}, use {proposed_use or 'not specified'}): {desc or addr}.",
            "key_specs": [s for s in [workclass, proposed_use, addr] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Cincinnati commercial permit {permit_no}",
                "url": link or "https://data.cincinnati-oh.gov/Thriving-Neighborhoods/Cincinnati-Building-Permits/uhjb-xac9",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "OH",
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
    print(f"Cincinnati OH: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("OH", projects)
        print(f"  merged into oh.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
