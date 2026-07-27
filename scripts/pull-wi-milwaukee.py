#!/usr/bin/env python3
"""Pull Milwaukee's Residential and Commercial Permit Work Data via the
CKAN datastore SQL API -- verified live 2026-07-26: dataset actively
updated (metadata_modified = today), 8,257 total commercial records,
max Date Issued 2026-06-15. "Permit Type" LIKE 'Commercial%' cleanly
separates 'Commercial New Construction Permit' / 'Commercial Alteration
Permit' from residential types. Address-stub only -- no project-name
field, same limitation as most municipal permit feeds already in this
corpus (Hartford, Bentonville).

CKAN is a different platform than ArcGIS/Socrata (no shared adapter in
this repo yet) -- one-off script rather than forcing it into
pull-county-arcgis.py.

Usage:
    python3 scripts/pull-wi-milwaukee.py --months 24 [--merge]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import slugify  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (SpecIndex research; +https://specindex.ai)"}
STATES_DIR = ROOT / "data" / "states"
RESOURCE_ID = "828e9630-d7cb-42e4-960e-964eae916397"
DOMAIN = "data.milwaukee.gov"


def query_ckan_sql(sql: str) -> list[dict]:
    url = f"https://{DOMAIN}/api/3/action/datastore_search_sql?{urllib.parse.urlencode({'sql': sql})}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())
    if not data.get("success"):
        raise RuntimeError(f"CKAN query failed: {data}")
    return data["result"]["records"]


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t:
        return "industrial"
    if "hotel" in t or "hospitality" in t:
        return "hospitality"
    if "office" in t or "bank" in t:
        return "office"
    if "retail" in t or "store" in t or "shop" in t:
        return "retail"
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


ADDR_RE = re.compile(r"^(.*?),\s*MILWAUKEE,\s*WI\s*(\d{5})", re.I)


def pull(cutoff: dt.date) -> list[dict]:
    sql = (
        f'SELECT * FROM "{RESOURCE_ID}" '
        f"WHERE \"Permit Type\" LIKE 'Commercial%' "
        f"AND \"Date Issued\" >= '{cutoff.isoformat()}' "
        f'ORDER BY "Date Issued" DESC LIMIT 10000'
    )
    rows = query_ckan_sql(sql)
    projects, seen = [], set()
    for r in rows:
        record_id = str(r.get("Record ID") or "").strip()
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        permit_type = (r.get("Permit Type") or "").strip()
        addr_full = (r.get("Address") or "").strip()
        m = ADDR_RE.match(addr_full)
        street = m.group(1).strip() if m else addr_full
        try:
            cost = float(r.get("Construction Total Cost") or 0)
        except (TypeError, ValueError):
            cost = 0
        opened = (r.get("Date Issued") or "")[:10] or None
        use = (r.get("Use of Building") or "").strip()
        ptype = project_type_from(f"{permit_type} {use}")
        projects.append({
            "id": f"wi-milwaukee-{slugify(record_id)}",
            "name": f"{permit_type} — {street}"[:120],
            "city": "Milwaukee",
            "county": "Milwaukee",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Milwaukee commercial permit {record_id} ({permit_type}): {street}."
            + (f" Use of building: {use}." if use else ""),
            "key_specs": [s for s in [permit_type, use, f"Permit {record_id}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Milwaukee commercial permit {record_id}",
                "url": f"https://data.milwaukee.gov/dataset/wibrs-permits",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "WI",
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
    print(f"Milwaukee WI: {len(projects)} commercial permits (cutoff {cutoff})")
    if args.merge:
        added, total = merge_into_state("WI", projects)
        print(f"  merged into wi.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
