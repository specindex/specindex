#!/usr/bin/env python3
"""Pull Cook County Assessor's commercial building permits -- verified
live 2026-07-27: 711,162 total records across 124 municipalities (all of
Cook County including Chicago, not just the city). Real categorical
`job_code_primary='COMMERCIAL PERMIT'` field -- no text-keyword guessing
needed, unlike Chicago's own city permit portal (checked separately,
rejected in favor of this single county-wide source to avoid a
Chicago/Cook-County double-count dedup problem: this dataset's own
`municipality='CITY OF CHICAGO'` rows already cover Chicago).

Data-quality notes from verification:
  - `property_address` is populated on almost none of the rows (88 of
    25,203 in a 2-year commercial window) -- most records only carry
    `municipality`/`township`, not a street address. Still a real fix for
    this corpus's city-field gap (city-level, not address-level).
  - `amount`/`work_description`/`applicant_name` are populated on ~99.7%
    of rows -- real dollar values and descriptions exist even without an
    address.
  - `date_issued` has ~18 garbage far-future values across the full
    dataset (up to year 2210) -- clamp the upper bound of any date filter
    to avoid a "the dataset looks dead" false read from an unfiltered max().

Usage:
    python3 scripts/pull-il-cook-county.py --months 24 [--merge]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import slugify  # noqa: E402
from socrata_adapter import query_socrata  # noqa: E402

STATES_DIR = ROOT / "data" / "states"
DOMAIN = "datacatalog.cookcountyil.gov"
DATASET = "6yjf-dfxs"

ZIP_RE = re.compile(r"(\d{5})\s*$")


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t or "factory" in t:
        return "industrial"
    if "hotel" in t:
        return "hospitality"
    if "office" in t or "bank" in t:
        return "office"
    if "retail" in t or "store" in t or "restaurant" in t:
        return "retail"
    if "medical" in t or "hospital" in t or "clinic" in t:
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
    today = dt.date.today().isoformat()
    rows = query_socrata(
        DOMAIN, DATASET,
        where=(
            f"job_code_primary='COMMERCIAL PERMIT' AND date_issued > '{cutoff.isoformat()}' "
            f"AND date_issued <= '{today}'"
        ),
        select="pin,local_permit_number,permit_number,date_issued,amount,municipality,township,"
        "property_address,applicant_name,work_description,improvement_code_1,improvement_code_2",
    )
    projects, seen = [], set()
    for r in rows:
        permit_id = str(r.get("local_permit_number") or r.get("permit_number") or r.get("pin") or "").strip()
        date_issued = (r.get("date_issued") or "")[:10]
        uid = slugify(f"{permit_id}-{date_issued}")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        desc = (r.get("work_description") or "").strip()
        improvements = " ".join(s for s in [r.get("improvement_code_1"), r.get("improvement_code_2")] if s)
        blob = f"{desc} {improvements}"
        ptype = project_type_from(blob)
        try:
            amount = float(r.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        municipality = (r.get("municipality") or "").strip().title()
        addr = (r.get("property_address") or "").strip()
        zip_m = ZIP_RE.search(addr)
        applicant = (r.get("applicant_name") or "").strip().title()
        name = (desc[:100] if desc else f"Cook County commercial permit {permit_id}")
        projects.append({
            "id": f"il-cook-{uid}",
            "name": name,
            "city": municipality or "Cook County",
            "county": "Cook",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": amount if amount > 0 else None,
            "square_footage": None,
            "owner": applicant,
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": date_issued or None,
            "description": f"Cook County IL commercial permit {permit_id} ({municipality or 'unincorporated'}): {desc or improvements or 'No description provided'}.",
            "key_specs": [s for s in [improvements, addr, f"Permit {permit_id}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Cook County IL commercial permit {permit_id}",
                "url": "https://datacatalog.cookcountyil.gov/Property-Taxation/Cook-County-Assessor-s-Permits/6yjf-dfxs",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "IL",
            "latitude": None,
            "longitude": None,
            "zip": zip_m.group(1) if zip_m else None,
        })
    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    projects = pull(cutoff)
    print(f"Cook County IL: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("IL", projects)
        print(f"  merged into il.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
