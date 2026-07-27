#!/usr/bin/env python3
"""Pull Seattle's Building Permits via Socrata -- verified live 2026-07-27:
191,801 total records, max issueddate 2026-07-25. permitclassmapped=
'Non-Residential' is a real categorical field; permittypedesc filter
drops non-construction noise (Shoreline/ECA exemptions). Direct lat/lon
already present -- no geocoding pass needed.

Usage:
    python3 scripts/pull-wa-seattle.py --months 24 [--merge]
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
DOMAIN = "data.seattle.gov"
DATASET = "76t5-zqzr"

PERMIT_TYPES = ["New", "Addition/Alteration", "Tenant Improvment", "Demolition"]


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t:
        return "industrial"
    if "hotel" in t:
        return "hospitality"
    if "office" in t:
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
    types_clause = " OR ".join(f"permittypedesc='{t}'" for t in PERMIT_TYPES)
    where = f"permitclassmapped='Non-Residential' AND ({types_clause}) AND issueddate>'{cutoff.isoformat()}'"
    rows = query_socrata(
        DOMAIN, DATASET,
        where=where,
        select="permitnum,permittypedesc,description,estprojectcost,originaladdress1,"
        "originalcity,originalzip,issueddate,contractorcompanyname,latitude,longitude,link",
    )
    projects, seen = [], set()
    for r in rows:
        permit_no = str(r.get("permitnum") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (r.get("description") or "").strip()
        permit_type = (r.get("permittypedesc") or "").strip()
        ptype = project_type_from(desc)
        try:
            cost = float(r.get("estprojectcost") or 0)
        except (TypeError, ValueError):
            cost = 0
        addr = (r.get("originaladdress1") or "").strip()
        city = (r.get("originalcity") or "Seattle").strip().title()
        opened = (r.get("issueddate") or "")[:10] or None
        contractor = (r.get("contractorcompanyname") or "").strip().title()
        try:
            lat = float(r.get("latitude")) if r.get("latitude") else None
            lon = float(r.get("longitude")) if r.get("longitude") else None
        except (TypeError, ValueError):
            lat = lon = None
        name = desc[:120] or f"Seattle commercial permit {permit_no}"
        # Socrata's "link" column is a compound URL type -- serializes as
        # {"url": "...", "description": "..."}, not a plain string. This
        # crashed merge-national-corpus.py's source_urls() ~43 minutes
        # into a run (AttributeError: 'dict' object has no attribute
        # 'strip') since every other source in the corpus has a plain
        # string url.
        link_field = r.get("link")
        link_url = (
            link_field.get("url") if isinstance(link_field, dict) else link_field
        ) or "https://data.seattle.gov/Permitting/Building-Permits/76t5-zqzr"
        projects.append({
            "id": f"wa-seattle-{slugify(permit_no)}",
            "name": name,
            "city": city,
            "county": "King",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": contractor,
            "opened_or_announced_date": opened,
            "description": f"Seattle commercial permit {permit_no} ({permit_type}): {desc or 'No description provided'}. {addr}.",
            "key_specs": [s for s in [permit_type, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Seattle commercial permit {permit_no}",
                "url": link_url,
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "WA",
            "latitude": lat,
            "longitude": lon,
        })
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    projects = pull(cutoff)
    print(f"Seattle WA: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("WA", projects)
        print(f"  merged into wa.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
