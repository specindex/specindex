#!/usr/bin/env python3
"""Pull commercial building permits from 5 county/city ArcGIS feeds,
verified live 2026-07-26 before building (liveness, schema, AND real
coordinates -- see docs/ROADMAP.md items 27/34 for why the coordinate
check specifically matters, two prior mislabeled-source incidents this
session were only caught that way):

  - Durham County, NC (webgis2.durhamnc.gov) -- Occupancy field for
    commercial/business codes
  - Maricopa County, AZ (services.arcgis.com/ykpntM6e3tHvzKRJ) --
    PermitType LIKE '%Commercial%'
  - Fort Worth, TX / Tarrant County (mapit.fortworthtexas.gov) --
    Permit_Type LIKE '%Commercial%'; already provides Latitude/Longitude
    as direct fields, no geometry query needed
  - Denver, CO (services1.arcgis.com/zdB7qR0BtYrg0Xpl) -- entire layer is
    commercial-only by construction (extracted where permit type =
    COMMCON), no filter needed
  - Nashville / Davidson County, TN (services2.arcgis.com/HdTo6HJqh92wn4D8)
    -- Permit_Subtype_Description LIKE '%Commercial%'; already provides
    Lon/Lat as direct fields

Usage:
    python3 scripts/pull-county-arcgis.py --months 24 [--merge]
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

RESIDENTIAL_HINTS = re.compile(
    r"\b(single family|single-family|detached dwelling|townhome|townhouse|subdivision|"
    r"duplex|triplex|apartment|multifamily|condo|dwelling|residential)\b",
    re.I,
)
COMMERCIAL_HINTS = re.compile(
    r"\b(office|retail|commercial|industrial|hotel|hospitality|warehouse|medical|"
    r"restaurant|bank|professional|mixed[- ]?use|store|shop|auto|church|school)\b",
    re.I,
)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read())


def query_layer(base: str, layer: int, where: str, fields: str = "*", page_size: int = 1000) -> list[dict]:
    """Returns each feature's attributes with `_lat`/`_lon` merged in from
    geometry (outSR=4326) when the source doesn't already provide direct
    lat/lon fields."""
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": fields,
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "returnGeometry": "true",
            "outSR": "4326",
        }
        url = f"{base}/{layer}/query?{urllib.parse.urlencode(params)}"
        data = fetch_json(url)
        if "error" in data:
            raise RuntimeError(str(data["error"])[:200])
        feats = data.get("features") or []
        for f in feats:
            attrs = dict(f.get("attributes") or {})
            geom = f.get("geometry") or {}
            if "x" in geom and "y" in geom:
                attrs["_lon"], attrs["_lat"] = geom["x"], geom["y"]
            out.append(attrs)
        if len(feats) < page_size or not data.get("exceededTransferLimit"):
            break
        offset += page_size
    return out


def epoch_ms_to_date(v) -> str | None:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)) and v > 1e11:
            return dt.datetime.utcfromtimestamp(v / 1000).date().isoformat()
    except Exception:  # noqa: BLE001
        return None
    return None


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t:
        return "industrial"
    if "hotel" in t or "hospitality" in t:
        return "hospitality"
    if "office" in t or "bank" in t or "professional" in t:
        return "office"
    if "retail" in t or "store" in t or "shop" in t:
        return "retail"
    if "restaurant" in t:
        return "hospitality"
    if "medical" in t or "hospital" in t:
        return "healthcare"
    if "school" in t or "church" in t:
        return "institutional"
    if "mixed" in t:
        return "mixed_use"
    return "commercial"


def categories_for(ptype: str) -> list[str]:
    return {
        "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression"],
        "office": ["glazing", "hvac", "elevators", "lighting", "flooring", "fire suppression"],
        "retail": ["glazing", "hvac", "roofing", "lighting", "doors and hardware", "fire suppression"],
        "hospitality": ["hvac", "elevators", "flooring", "plumbing fixtures", "lighting", "ff&e"],
        "healthcare": ["hvac", "medical gas", "elevators", "flooring", "lighting", "fire suppression"],
        "institutional": ["hvac", "roofing", "glazing", "lighting", "flooring", "fire suppression"],
        "mixed_use": ["glazing", "hvac", "elevators", "roofing", "lighting", "flooring"],
    }.get(ptype, ["hvac", "roofing", "lighting", "concrete", "fire suppression"])


def pull_durham(cutoff: dt.date) -> list[dict]:
    base = "https://webgis2.durhamnc.gov/server/rest/services/PublicServices/Inspections/MapServer"
    # Occupancy is spelled out (not IBC code letters as earlier research
    # assumed) -- confirmed live 2026-07-26 via a distinct-value scan:
    # 'Business'/'Mercantile'/'Non-Residential'/'Educational'/'Utility' and
    # 'Assembly (1)'..'Assembly (5)' are the non-residential categories;
    # 'Mixed Use Residential' deliberately excluded as residential-leaning.
    where = (
        "(Occupancy IN ('Business','Mercantile','Non-Residential','Educational','Utility') "
        "OR Occupancy LIKE 'Assembly%') "
        f"AND ISSUE_DATE >= DATE '{cutoff.isoformat()}'"
    )
    rows = query_layer(base, 12, where, fields="PermitNum,ISSUE_DATE,DESCRIPTION,PROJECT_NAME,PROJECT_TYPE,BLD_Cost,SQFT_FLOOR,Occupancy,PmtStatus")
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("PermitNum") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (a.get("DESCRIPTION") or "").strip()
        proj_type_raw = (a.get("PROJECT_TYPE") or "").strip()
        blob = f"{desc} {proj_type_raw}"
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        opened = epoch_ms_to_date(a.get("ISSUE_DATE")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        name = (a.get("PROJECT_NAME") or "").strip() or f"Commercial permit {permit_no}"
        cost = a.get("BLD_Cost")
        sqft = a.get("SQFT_FLOOR")
        projects.append({
            "id": f"nc-durham-{slugify(permit_no)}",
            "name": name[:120],
            "city": "Durham",
            "county": "Durham",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost and cost > 0 else None,
            "square_footage": sqft if sqft and sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Durham County commercial permit {permit_no}: {desc or proj_type_raw}.",
            "key_specs": [s for s in [proj_type_raw, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Durham County commercial permit {permit_no}", "url": f"{base}/12"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "NC",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
        })
    return projects


def pull_maricopa(cutoff: dt.date) -> list[dict]:
    base = "https://services.arcgis.com/ykpntM6e3tHvzKRJ/arcgis/rest/services/Building_Permits_(view)/FeatureServer"
    where = f"PermitType LIKE '%Commercial%' AND IssuedDate >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(base, 0, where, fields="PermitNumber,PermitType,WorkClass,PermitDescription,FullStreetAddress,ZipCode,IssuedDate,PermitStatus")
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("PermitNumber") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (a.get("PermitDescription") or "").strip()
        work_class = (a.get("WorkClass") or "").strip()
        blob = f"{desc} {work_class}"
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        opened = epoch_ms_to_date(a.get("IssuedDate")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        addr = (a.get("FullStreetAddress") or "").strip()
        name = addr.title() or f"Commercial permit {permit_no}"
        projects.append({
            "id": f"az-maricopa-{slugify(permit_no)}",
            "name": name[:120],
            "city": "",
            "county": "Maricopa",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Maricopa County commercial permit {permit_no}: {desc or work_class}. {addr}.",
            "key_specs": [s for s in [work_class, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Maricopa County commercial permit {permit_no}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "AZ",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
            "zip": str(a["ZipCode"]).strip() or None if a.get("ZipCode") else None,
        })
    return projects


def pull_fortworth(cutoff: dt.date) -> list[dict]:
    base = "https://mapit.fortworthtexas.gov/ags/rest/services/CIVIC/Permits/MapServer"
    where = f"Permit_Type LIKE '%Commercial%' AND File_Date >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(base, 0, where, fields="Permit_No,Permit_Type,Permit_SubType,B1_WORK_DESC,Address,Owner_Full_Name,File_Date,JobValue,SqFt,Current_Status,Zip_Code,Latitude,Longitude")
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("Permit_No") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (a.get("B1_WORK_DESC") or "").strip()
        subtype = (a.get("Permit_SubType") or "").strip()
        blob = f"{desc} {subtype}"
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        opened = epoch_ms_to_date(a.get("File_Date")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        addr = (a.get("Address") or "").strip()
        name = addr.title() or f"Commercial permit {permit_no}"
        value = a.get("JobValue")
        # SqFt comes back as a string field on this service (confirmed
        # live 2026-07-26, e.g. "0", "12334"), unlike every other numeric
        # field here -- coerce defensively rather than assume.
        try:
            sqft = int(float(a.get("SqFt") or 0))
        except (TypeError, ValueError):
            sqft = None
        lat = a.get("Latitude")
        lon = a.get("Longitude")
        projects.append({
            "id": f"tx-tarrant-{slugify(permit_no)}",
            "name": name[:120],
            "city": "Fort Worth",
            "county": "Tarrant",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value and value > 0 else None,
            "square_footage": sqft if sqft and sqft > 0 else None,
            "owner": (a.get("Owner_Full_Name") or "").strip(),
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Fort Worth commercial permit {permit_no}: {desc or subtype}. {addr}.",
            "key_specs": [s for s in [subtype, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Fort Worth commercial permit {permit_no}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "TX",
            "latitude": lat if lat else a.get("_lat"),
            "longitude": lon if lon else a.get("_lon"),
            "zip": str(a["Zip_Code"]).strip() or None if a.get("Zip_Code") else None,
        })
    return projects


def pull_denver(cutoff: dt.date) -> list[dict]:
    base = "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_DEV_COMMERCIALCONSTPERMIT_P/FeatureServer"
    where = f"DATE_ISSUED >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(base, 317, where, fields="PERMIT_NUM,DATE_ISSUED,ADDRESS,CLASS,VALUATION,CONTRACTOR_NAME")
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("PERMIT_NUM") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        cls = (a.get("CLASS") or "").strip()
        addr = (a.get("ADDRESS") or "").strip()
        opened = epoch_ms_to_date(a.get("DATE_ISSUED")) or cutoff.isoformat()
        ptype = project_type_from(cls)
        name = addr.title() or f"Commercial permit {permit_no}"
        value = a.get("VALUATION")
        projects.append({
            "id": f"co-denver-{slugify(permit_no)}",
            "name": name[:120],
            "city": "Denver",
            "county": "Denver",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value and value > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": (a.get("CONTRACTOR_NAME") or "").strip(),
            "opened_or_announced_date": opened,
            "description": f"Denver commercial permit {permit_no}: {cls}. {addr}.",
            "key_specs": [s for s in [cls, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Denver commercial permit {permit_no}", "url": f"{base}/317"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "CO",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
        })
    return projects


def pull_nashville(cutoff: dt.date) -> list[dict]:
    base = "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Building_Permit_Applications_Feature_Layer_view/FeatureServer"
    # Date_Issued is NULL for essentially all commercial-subtype records
    # (confirmed live 2026-07-26 -- a query for commercial + non-null
    # Date_Issued returned zero rows). Date_Entered (application/intake
    # date) is reliably populated instead; used both for the cutoff filter
    # and as this permit's opened_or_announced_date.
    where = f"Permit_Subtype_Description LIKE '%Commercial%' AND Date_Entered >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(base, 0, where, fields="Permit__,Permit_Type_Description,Permit_Subtype_Description,Date_Entered,Const_Cost,Address,City,State,Purpose,Lon,Lat,ZIP")
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("Permit__") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        purpose = (a.get("Purpose") or "").strip()
        subtype = (a.get("Permit_Subtype_Description") or "").strip()
        blob = f"{purpose} {subtype}"
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        opened = epoch_ms_to_date(a.get("Date_Entered")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        addr = (a.get("Address") or "").strip()
        city = (a.get("City") or "Nashville").strip().title()
        name = addr.title() or f"Commercial permit {permit_no}"
        cost = a.get("Const_Cost")
        lat = a.get("Lat")
        lon = a.get("Lon")
        projects.append({
            "id": f"tn-davidson-{slugify(permit_no)}",
            "name": name[:120],
            "city": city,
            "county": "Davidson",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost and cost > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Nashville/Davidson County commercial permit {permit_no}: {purpose or subtype}. {addr}.",
            "key_specs": [s for s in [subtype, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Nashville/Davidson County commercial permit {permit_no}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "TN",
            "latitude": lat if lat else a.get("_lat"),
            "longitude": lon if lon else a.get("_lon"),
            "zip": str(a["ZIP"]).strip() or None if a.get("ZIP") else None,
        })
    return projects


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--only", help="Comma-separated subset: durham,maricopa,fortworth,denver,nashville")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    pullers = {
        "durham": ("NC", pull_durham),
        "maricopa": ("AZ", pull_maricopa),
        "fortworth": ("TX", pull_fortworth),
        "denver": ("CO", pull_denver),
        "nashville": ("TN", pull_nashville),
    }
    selected = set(args.only.split(",")) if args.only else set(pullers)

    print(f"County ArcGIS pull, cutoff {cutoff}")
    all_results: dict[str, list[dict]] = {}
    for key, (state, fn) in pullers.items():
        if key not in selected:
            continue
        try:
            projects = fn(cutoff)
        except Exception as exc:  # noqa: BLE001
            print(f"  {key}: FAILED ({exc})", file=sys.stderr)
            continue
        all_results[key] = projects
        print(f"  {key} ({state}): {len(projects)} commercial projects")

        if args.merge:
            added, total = merge_into_state(state, projects)
            print(f"    merged into {state.lower()}.json: +{added} new, {total} total")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
