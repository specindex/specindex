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
        # quote_via=quote (not the urlencode default quote_plus) -- some
        # ArcGIS REST servers reject "+"-encoded spaces inside a quoted
        # LIKE string literal (confirmed live on Cleveland OH's endpoint:
        # identical query 400s with "+" for spaces, works with "%20").
        url = f"{base}/{layer}/query?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
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


def pull_hartford(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: a Table (no geometry -- PROPERTY_ADDRESS
    # only, no lat/lon), RECORD_TYPE_TYPE='Commercial' cleanly separates
    # commercial/residential/temporary-structure records, DateIssued is
    # epoch ms. 35,691 total records, fresh to within the last month.
    base = "https://utility.arcgis.com/usrsvcs/servers/d595ae995fb049d3ac54919ebf24b1ac/rest/services/HartfordOpenDataTables/FeatureServer"
    where = f"RECORD_TYPE_TYPE='Commercial' AND DateIssued >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields="RECORD_ID,DESCRIPTION,B1_APP_TYPE_ALIAS,PROPERTY_ADDRESS,PROPERTY_CITY,Total_Construction_Cost,DateIssued",
    )
    projects, seen = [], set()
    for a in rows:
        record_id = str(a.get("RECORD_ID") or "").strip()
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        desc = (a.get("DESCRIPTION") or "").strip()
        app_type = (a.get("B1_APP_TYPE_ALIAS") or "").strip()
        blob = f"{desc} {app_type}"
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        opened = epoch_ms_to_date(a.get("DateIssued")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        cost = a.get("Total_Construction_Cost")
        addr = (a.get("PROPERTY_ADDRESS") or "").strip()
        name = desc[:120] or f"Hartford commercial permit {record_id}"
        projects.append({
            "id": f"ct-hartford-{slugify(record_id)}",
            "name": name,
            "city": (a.get("PROPERTY_CITY") or "Hartford").title(),
            "county": "Hartford",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost and cost > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Hartford commercial permit {record_id} ({app_type or 'Commercial'}): {desc or 'No description provided'}. {addr}.",
            "key_specs": [s for s in [app_type, addr, f"Permit {record_id}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Hartford commercial permit {record_id}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "CT",
            "latitude": None,
            "longitude": None,
        })
    return projects


def pull_burlington(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: Feature Layer with direct Latitude/Longitude
    # fields (no geometry query needed), PrimaryLUC cleanly flags
    # commercial/industrial ("C - Commercial", "I - Industrial",
    # "CC - Comm Condo", "CR - Com/Resident"), fresh to ~Apr 2026.
    base = "https://services1.arcgis.com/1bO0c7PxQdsGidPK/arcgis/rest/services/OpenGov_Building/FeatureServer"
    where = (
        "PrimaryLUC IN ('C - Commercial','I - Industrial','CC - Comm Condo','CR - Com/Resident') "
        f"AND EstimatedConstructionCost > 25000 AND ApplicationDate >= DATE '{cutoff.isoformat()}'"
    )
    rows = query_layer(
        base, 0, where,
        fields="ProjectName,Description,StreetAddress,PrimaryLUC,EstimatedConstructionCost,"
        "ApplicationDate,Latitude,Longitude,ContractorOrOrganizationName,PermitStatus,PermitNo",
    )
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("PermitNo") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        desc = (a.get("Description") or "").strip()
        luc = (a.get("PrimaryLUC") or "").strip()
        ptype = project_type_from(f"{desc} {luc}")
        opened = epoch_ms_to_date(a.get("ApplicationDate")) or cutoff.isoformat()
        cost = a.get("EstimatedConstructionCost")
        addr = (a.get("StreetAddress") or "").strip()
        name = (a.get("ProjectName") or "").strip() or f"Burlington commercial permit {permit_no}"
        projects.append({
            "id": f"vt-burlington-{slugify(permit_no)}",
            "name": name[:120],
            "city": "Burlington",
            "county": "Chittenden",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost and cost > 0 else None,
            "square_footage": None,
            "owner": (a.get("ContractorOrOrganizationName") or "").strip() or "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Burlington VT commercial permit {permit_no} ({luc}): {desc or 'No description provided'}. {addr}.",
            "key_specs": [s for s in [luc, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Burlington VT commercial permit {permit_no}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "VT",
            "latitude": a.get("Latitude"),
            "longitude": a.get("Longitude"),
        })
    return projects


def pull_act250(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: Vermont's statewide land-use/pre-construction
    # review register (the closest VT equivalent to GA's DRI). No date
    # field on the layer -- pulls the full 8,278-record set and relies on
    # text classification (same RESIDENTIAL_HINTS/COMMERCIAL_HINTS regex
    # used everywhere else) since Act 250 covers everything from
    # commercial buildings to single-family driveway culverts.
    base = "http://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASBASEMAPLITE_WM_NOCACHE/MapServer"
    rows = query_layer(
        base, 2, "1=1",
        fields="AppNum,AppType,ProjectName,ProjectTown,District,Status,Description,GisLatitude,GisLongitude,LINK",
    )
    projects, seen = [], set()
    for a in rows:
        app_num = str(a.get("AppNum") or "").strip()
        if not app_num or app_num in seen:
            continue
        seen.add(app_num)
        desc = (a.get("Description") or "").strip()
        name = (a.get("ProjectName") or "").strip() or f"Act 250 application {app_num}"
        blob = f"{desc} {name}"
        # Act 250 covers everything from commercial buildings to gravel
        # pits, farms, solid-waste sites, and utility poles -- the usual
        # "keep unless a residential hint fires" rule let almost all of
        # that noise through (spot-checked: 6,934 of 8,278 records passed
        # it). Require a positive commercial/building signal instead.
        if not COMMERCIAL_HINTS.search(blob):
            continue
        if RESIDENTIAL_HINTS.search(blob):
            continue
        ptype = project_type_from(blob)
        town = (a.get("ProjectTown") or "").strip()
        link = (a.get("LINK") or "").strip() or f"{base}/2"
        projects.append({
            "id": f"vt-act250-{slugify(app_num)}",
            "name": name[:120],
            "city": town,
            "county": town,
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": None,
            "description": f"Vermont Act 250 application {app_num} ({a.get('AppType') or 'Application'}, {town}): {desc or name}.",
            "key_specs": [s for s in [a.get("AppType"), a.get("District"), f"Application {app_num}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Vermont Act 250 application {app_num}", "url": link}],
            "open_for": "Active Act 250 land-use review. Early product/spec window.",
            "state": "VT",
            "latitude": a.get("GisLatitude"),
            "longitude": a.get("GisLongitude"),
        })
    return projects


def pull_providence(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: Providence's hand-curated planning-dept
    # tracker (not a permit feed -- no date/value/sqft fields), two layers
    # (Pipeline = in progress, Completed). Actively maintained (parent item
    # modified 2026-07-15). Small volume (85 + 97 records) but real and
    # current; needs text classification since it mixes commercial,
    # institutional, and some residential/mixed-use projects.
    base = "https://services6.arcgis.com/wv9mHoqblhTsnqdG/arcgis/rest/services"
    layers = [
        (f"{base}/Pipeline_Development_Projects/FeatureServer", "pipeline", "planning"),
        (f"{base}/Completed_Development_Projects/FeatureServer", "completed", "under_construction"),
    ]
    projects, seen = [], set()
    for layer_base, tag, status in layers:
        rows = query_layer(
            layer_base, 0, "1=1",
            fields="Project_Name,Address,Neighborhood,Project_Description,Status,Latitude,Longitude",
        )
        for a in rows:
            name = (a.get("Project_Name") or "").strip()
            addr = (a.get("Address") or "").strip()
            if not name:
                continue
            uid = slugify(f"{name}-{addr}")
            if not uid or uid in seen:
                continue
            seen.add(uid)
            desc = (a.get("Project_Description") or "").strip()
            blob = f"{name} {desc}"
            if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
                continue
            ptype = project_type_from(blob)
            neighborhood = (a.get("Neighborhood") or "").strip()
            projects.append({
                "id": f"ri-providence-{tag}-{uid}",
                "name": name[:120],
                "city": "Providence",
                "county": "Providence",
                "status": status,
                "project_type": ptype,
                "estimated_value_usd": None,
                "square_footage": None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": None,
                "description": f"Providence development project ({neighborhood or 'Providence'}): {desc or name}.",
                "key_specs": [s for s in [neighborhood, a.get("Status"), addr] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [{"title": f"Providence development project: {name}", "url": f"{layer_base}/0"}],
                "open_for": "Active Providence development-tracker project. Early product/spec window.",
                "state": "RI",
                "latitude": a.get("Latitude"),
                "longitude": a.get("Longitude"),
            })
    return projects


def pull_delaware(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: statewide non-residential building permit
    # layer covering all 3 counties, real R_NR flag. CAVEAT: confirmed
    # stale -- max P_YEAR is 2024, P_YEAR=2025 returns 0 records. Still
    # real historical commercial permits worth having (project value comes
    # from breadth, not freshness, for this one source).
    base = "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/PlanningCadastre/DE_Planning_Development/MapServer"
    rows = query_layer(
        base, 3, "R_NR IN ('NR','Mixed')",
        fields="R_NR,NR_SF,NOTES,RECTYPE,P_YEAR,COUNTY,JURISDICTION",
    )
    projects, seen = [], set()
    for i, a in enumerate(rows):
        notes = (a.get("NOTES") or "").strip()
        county = (a.get("COUNTY") or "").strip()
        jurisdiction = (a.get("JURISDICTION") or "").strip()
        uid = slugify(f"{county}-{jurisdiction}-{notes}-{i}")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        blob = f"{notes} {a.get('RECTYPE') or ''}"
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob) and a.get("R_NR") != "NR":
            continue
        ptype = project_type_from(blob) if COMMERCIAL_HINTS.search(blob) else "other"
        sqft = a.get("NR_SF")
        year = str(a.get("P_YEAR") or "").strip()
        opened = f"{year}-01-01" if year.isdigit() and len(year) == 4 else None
        projects.append({
            "id": f"de-statewide-{uid}",
            "name": (notes[:120] or f"{jurisdiction or county} non-residential permit"),
            "city": jurisdiction or county,
            "county": county,
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": None,
            "square_footage": sqft if sqft and sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Delaware statewide non-residential building permit ({jurisdiction or county}): {notes or 'No description provided'}.",
            "key_specs": [s for s in [a.get("RECTYPE"), jurisdiction, f"Year {year}" if year else None] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Delaware statewide building permit, {jurisdiction or county}", "url": f"{base}/3"}],
            "open_for": "Historical non-residential building permit (source is stale past 2024, still real commercial activity).",
            "state": "DE",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
        })
    return projects


def pull_overland_park(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: Overland Park (Johnson County KS, KC
    # metro), max IssueDate 2026-07-23. ReportPermitType cleanly separates
    # commercial from residential. CAVEAT (per research pass): the
    # service's own metadata says it was "specifically created for Teri in
    # IT... for school lookup" -- an unofficial/ad-hoc extract, not a
    # documented open-data product. Could be renamed/pulled without
    # notice; re-verify liveness before relying on it long-term.
    base = "https://maps.opkansas.org/mapping/rest/services/MixedInfo/Building_Permit_Report/MapServer"
    commercial_types = (
        "'New Commercial','Other Commercial','New Institutional, Churches, and Schools'"
    )
    where = f"ReportPermitType IN ({commercial_types}) AND IssueDate >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields="CaseNumber,Project,Description,MainAddressLine1,Valuation,SquareFeet,IssueDate,PermitStatus,ReportPermitType",
    )
    projects, seen = [], set()
    for a in rows:
        case_no = str(a.get("CaseNumber") or "").strip()
        if not case_no or case_no in seen:
            continue
        seen.add(case_no)
        desc = (a.get("Description") or "").strip()
        ptype_raw = (a.get("ReportPermitType") or "").strip()
        ptype = project_type_from(f"{desc} {ptype_raw}")
        opened = epoch_ms_to_date(a.get("IssueDate")) or cutoff.isoformat()
        val = a.get("Valuation")
        sqft = a.get("SquareFeet")
        addr = (a.get("MainAddressLine1") or "").strip()
        name = (a.get("Project") or "").strip() or f"Overland Park permit {case_no}"
        projects.append({
            "id": f"ks-overlandpark-{slugify(case_no)}",
            "name": name[:120],
            "city": "Overland Park",
            "county": "Johnson",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": val if val and val > 0 else None,
            "square_footage": sqft if sqft and sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Overland Park KS commercial permit {case_no} ({ptype_raw}): {desc or name}. {addr}.",
            "key_specs": [s for s in [ptype_raw, addr, f"Permit {case_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Overland Park KS commercial permit {case_no}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "KS",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
        })
    return projects


def pull_bentonville(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: 50,456 total historical records, max
    # ISSUED 2026-07-17. CAVEAT: some records have bad future-dated ISSUED
    # values (unfiltered max = 2026-12-06) -- clamp to today, don't trust
    # the raw max. PERMIT_TYPE LIKE '%COM%' separates commercial permits.
    base = "https://gis.bentonvillear.com/arcgis/rest/services/Planning/Community_Development23/MapServer"
    today = dt.date.today().isoformat()
    where = (
        f"PERMIT_TYPE LIKE '%COM%' AND ISSUED >= DATE '{cutoff.isoformat()}' "
        f"AND ISSUED <= DATE '{today}'"
    )
    rows = query_layer(
        base, 188, where,
        fields="PERMIT_NO,PERMIT_TYPE,PERMIT_SUBTYPE,STATUS,SITE_ADDR,ISSUED,LAT,LON",
    )
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("PERMIT_NO") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        ptype_raw = (a.get("PERMIT_TYPE") or "").strip()
        subtype = (a.get("PERMIT_SUBTYPE") or "").strip()
        ptype = project_type_from(f"{ptype_raw} {subtype}")
        opened = epoch_ms_to_date(a.get("ISSUED")) or cutoff.isoformat()
        addr = (a.get("SITE_ADDR") or "").strip()
        name = f"{ptype_raw} — {addr}" if addr else f"Bentonville permit {permit_no}"
        projects.append({
            "id": f"ar-bentonville-{slugify(permit_no)}",
            "name": name[:120],
            "city": "Bentonville",
            "county": "Benton",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Bentonville AR commercial permit {permit_no} ({ptype_raw}{', ' + subtype if subtype else ''}): {addr}.",
            "key_specs": [s for s in [ptype_raw, subtype, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Bentonville AR commercial permit {permit_no}", "url": f"{base}/188"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "AR",
            "latitude": a.get("LAT"),
            "longitude": a.get("LON"),
        })
    return projects


def pull_fargo(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-26: Fargo's site-plan pre-construction review
    # layer, max DATE 2026-06-26. Minimal schema (no permit-type/valuation
    # field) -- Fargo doesn't require site-plan review for single-family
    # homes, so this layer skews commercial/institutional by construction,
    # but still needs text classification since there's no categorical
    # field to filter on.
    base = "https://gis.cityoffargo.com/arcgis/rest/services/General/SitePlans/MapServer"
    rows = query_layer(base, 0, "1=1", fields="ADDRESS,SECTION,NAME,DATE")
    projects, seen = [], set()
    for a in rows:
        name_raw = (a.get("NAME") or "").strip()
        addr = (a.get("ADDRESS") or "").strip()
        if not name_raw:
            continue
        uid = slugify(f"{name_raw}-{addr}")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        if RESIDENTIAL_HINTS.search(name_raw) and not COMMERCIAL_HINTS.search(name_raw):
            continue
        # DATE is a string "M/D/YYYY", not epoch ms -- parse directly.
        opened = None
        date_str = (a.get("DATE") or "").strip()
        try:
            if date_str:
                opened = dt.datetime.strptime(date_str, "%m/%d/%Y").date().isoformat()
        except ValueError:
            opened = None
        if opened and opened < cutoff.isoformat():
            continue
        ptype = project_type_from(name_raw)
        projects.append({
            "id": f"nd-fargo-{uid}",
            "name": name_raw[:120],
            "city": "Fargo",
            "county": "Cass",
            "status": "planning",
            "project_type": ptype,
            "estimated_value_usd": None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Fargo ND site plan review: {name_raw}. {addr}.",
            "key_specs": [s for s in [a.get("SECTION"), addr] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Fargo ND site plan: {name_raw}", "url": f"{base}/0"}],
            "open_for": "Active Fargo site-plan review. Early product/spec window.",
            "state": "ND",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
        })
    return projects


def pull_miamidade(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-27: 139,870 total records, max PermitIssuedDate
    # = today. ResidentialCommercial='C' is real but buckets 5+-unit
    # multifamily as "commercial" for permitting purposes -- excluded via
    # a ProposedUseDescription text check, same class of fix as Chicago/
    # Philadelphia. EstimatedValue/SquareFootage are STRING-typed fields
    # needing cast. A Table (no geometry) -- no lat/lon available.
    base = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/miamidade_permit_data/FeatureServer"
    # Filtering on CAST(EstimatedValue AS FLOAT) server-side, combined with
    # deep OFFSET pagination over 139K+ rows, reliably timed out (a
    # computed predicate can't use an index, so the server re-scans
    # progressively more rows per page). Filter by value client-side
    # instead -- pull the cheap categorical/date filter only, then drop
    # low-value rows in Python.
    where = (
        "ResidentialCommercial='C' AND ProposedUseDescription NOT LIKE '%RESIDENTIAL%' "
        f"AND PermitIssuedDate >= DATE '{cutoff.isoformat()}'"
    )
    rows = query_layer(
        base, 0, where,
        fields="PermitNumber,PermitType,EstimatedValue,ApplicationTypeDescription,"
        "ProposedUseDescription,PropertyAddress,OwnerName,City,PermitIssuedDate,SquareFootage",
    )
    projects, seen = [], set()
    for a in rows:
        permit_no = str(a.get("PermitNumber") or "").strip()
        if not permit_no or permit_no in seen:
            continue
        seen.add(permit_no)
        use_desc = (a.get("ProposedUseDescription") or "").strip()
        app_type = (a.get("ApplicationTypeDescription") or "").strip()
        ptype = project_type_from(f"{use_desc} {app_type}")
        try:
            value = float(a.get("EstimatedValue") or 0)
        except (TypeError, ValueError):
            value = 0
        if value <= 25000:
            continue
        try:
            sqft = float(a.get("SquareFootage") or 0)
        except (TypeError, ValueError):
            sqft = 0
        addr = (a.get("PropertyAddress") or "").strip()
        city = (a.get("City") or "").strip().title() or "Miami-Dade County"
        owner = (a.get("OwnerName") or "").strip().title()
        opened = a.get("PermitIssuedDate")
        opened_str = epoch_ms_to_date(opened) if isinstance(opened, (int, float)) else (str(opened)[:10] if opened else None)
        name = f"{app_type} — {use_desc}"[:120] if use_desc else f"Miami-Dade commercial permit {permit_no}"
        projects.append({
            "id": f"fl-miamidade-{slugify(permit_no)}",
            "name": name,
            "city": city,
            "county": "Miami-Dade",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value > 0 else None,
            "square_footage": sqft if sqft > 0 else None,
            "owner": owner,
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened_str,
            "description": f"Miami-Dade County commercial permit {permit_no} ({app_type}, {use_desc}): {addr}.",
            "key_specs": [s for s in [use_desc, app_type, addr, f"Permit {permit_no}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Miami-Dade County commercial permit {permit_no}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "FL",
            "latitude": None,
            "longitude": None,
        })
    return projects


def pull_detroit(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-27: 46,148 total records, max issued_date =
    # today. `use_group` (real IBC class: M/B/A/E/U vs R-2/R-3) is the
    # clean categorical field but frequently null (497 records/24mo with
    # the strict filter alone) -- combined with a positive text match on
    # `proposed_use_type` as a backstop (1,257 records/24mo combined).
    # `record_id` prefix (BLD/RES) is NOT a reliable filter on its own --
    # sampled BLD* records include single-family alterations.
    base = "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/bseed_building_permits/FeatureServer"
    where = (
        "(use_group IN ('M','B','A','E','U') OR proposed_use_type LIKE '%COMMERCIAL%' "
        "OR proposed_use_type LIKE '%RETAIL%' OR proposed_use_type LIKE '%OFFICE%' "
        "OR proposed_use_type LIKE '%WAREHOUSE%' OR proposed_use_type LIKE '%INDUSTRIAL%' "
        "OR proposed_use_type LIKE '%RESTAURANT%') "
        "AND proposed_use_type NOT LIKE '%RESIDENTIAL%' AND proposed_use_type NOT LIKE '%SINGLE FAMILY%' "
        f"AND issued_date >= timestamp '{cutoff.isoformat()} 00:00:00'"
    )
    rows = query_layer(
        base, 0, where,
        fields="record_id,address,issued_date,permit_type,use_group,current_use_type,"
        "proposed_use_type,zip_code,neighborhood,amt_estimated_contractor_cost",
    )
    projects, seen = [], set()
    for a in rows:
        record_id = str(a.get("record_id") or "").strip()
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        proposed = (a.get("proposed_use_type") or "").strip()
        permit_type = (a.get("permit_type") or "").strip()
        ptype = project_type_from(f"{proposed} {permit_type}")
        opened = epoch_ms_to_date(a.get("issued_date")) if isinstance(a.get("issued_date"), (int, float)) else None
        addr = (a.get("address") or "").strip()
        neighborhood = (a.get("neighborhood") or "").strip()
        try:
            cost = float(a.get("amt_estimated_contractor_cost") or 0)
        except (TypeError, ValueError):
            cost = 0
        name = f"{permit_type} — {addr}"[:120] if addr else f"Detroit permit {record_id}"
        projects.append({
            "id": f"mi-detroit-{slugify(record_id)}",
            "name": name,
            "city": "Detroit",
            "county": "Wayne",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Detroit commercial permit {record_id} ({permit_type}, {proposed or 'use not specified'}): {addr}.",
            "key_specs": [s for s in [proposed, neighborhood, f"Permit {record_id}"] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Detroit commercial permit {record_id}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "MI",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
            "zip": str(a.get("zip_code")).strip()[:5] if a.get("zip_code") else None,
        })
    return projects


def pull_fairfax(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-27: 10,746 total records, max ISSUED_DATE =
    # 4 days old. APPTYPEALIAS is a clean categorical field. Bonus:
    # DATA_CENTER Yes/No field -- direct hit on "Data Center Alley"
    # (Reston/Herndon/Chantilly), e.g. CoreSite VA3-2A Phase 2A ($90M).
    # Polygon (parcel) geometry, not point -- left lat/lon null rather
    # than risk a bad centroid extraction.
    base = "https://www.fairfaxcounty.gov/lambert/rest/services/LDS/DevelopmentTracker/FeatureServer"
    where = (
        "APPTYPEALIAS IN ('Commercial New','Commercial Addition/Alteration') "
        f"AND ISSUED_DATE >= timestamp '{cutoff.isoformat()} 00:00:00'"
    )
    rows = query_layer(
        base, 5, where,
        fields="RECORDID,APPTYPEALIAS,PROJECT_NAME,ESTIMATED_COST,ADDRESS_1,CITY,ZIP_CODE,ISSUED_DATE,DATA_CENTER",
    )
    projects, seen = [], set()
    for a in rows:
        record_id = str(a.get("RECORDID") or "").strip()
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        app_type = (a.get("APPTYPEALIAS") or "").strip()
        proj_name = (a.get("PROJECT_NAME") or "").strip()
        is_data_center = (a.get("DATA_CENTER") or "").strip().upper() == "YES"
        ptype = "industrial" if is_data_center else project_type_from(f"{proj_name} {app_type}")
        opened = epoch_ms_to_date(a.get("ISSUED_DATE")) or cutoff.isoformat()
        try:
            cost = float(a.get("ESTIMATED_COST") or 0)
        except (TypeError, ValueError):
            cost = 0
        addr = (a.get("ADDRESS_1") or "").strip()
        city = (a.get("CITY") or "").strip().title() or "Fairfax County"
        name = proj_name[:120] or f"Fairfax County commercial permit {record_id}"
        key_specs = [s for s in [app_type, addr, f"Permit {record_id}"] if s]
        if is_data_center:
            key_specs.insert(0, "Data center")
        projects.append({
            "id": f"va-fairfax-{slugify(record_id)}",
            "name": name,
            "city": city,
            "county": "Fairfax",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": cost if cost > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": "",
            "opened_or_announced_date": opened,
            "description": f"Fairfax County VA commercial permit {record_id} ({app_type}){' [DATA CENTER]' if is_data_center else ''}: {proj_name or addr}.",
            "key_specs": key_specs,
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Fairfax County VA commercial permit {record_id}", "url": f"{base}/5"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "VA",
            "latitude": None,
            "longitude": None,
            "zip": str(a.get("ZIP_CODE")).strip()[:5] if a.get("ZIP_CODE") else None,
        })
    return projects


def pull_columbus(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-27: 675,280 total records, max ISSUED_DT =
    # yesterday. B1_PER_TYPE='Commercial' is real and clean (mutually
    # exclusive vs 1,2,3-Family/Multi Family/Residential), but most
    # commercial rows are trade sub-permits (Plumbing/Electrical/
    # Mechanical) with G3_VALUE_TTL=0 -- filtered with a $25K value floor
    # to keep real construction-relevant records.
    base = "https://services1.arcgis.com/9yy6msODkIBzkUXU/arcgis/rest/services/Building_Permits/FeatureServer"
    where = (
        "B1_PER_TYPE='Commercial' AND G3_VALUE_TTL>25000 "
        f"AND ISSUED_DT >= timestamp '{cutoff.isoformat()} 00:00:00'"
    )
    rows = query_layer(
        base, 0, where,
        fields="B1_PER_CATEGORY,GENERAL_TYPE,SITE_ADDRESS,B1_SITUS_ZIP,PERMIT_STATUS,"
        "APPLICANT_BUS_NAME,SQFT,G3_VALUE_TTL,ISSUED_DT,ACA_URL",
    )
    projects, seen = [], set()
    for a in rows:
        addr = (a.get("SITE_ADDRESS") or "").strip()
        category = (a.get("B1_PER_CATEGORY") or "").strip()
        opened = epoch_ms_to_date(a.get("ISSUED_DT")) or cutoff.isoformat()
        uid = slugify(f"{addr}-{category}-{opened}")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        general_type = (a.get("GENERAL_TYPE") or "").strip()
        ptype = project_type_from(f"{category} {general_type}")
        try:
            value = float(a.get("G3_VALUE_TTL") or 0)
        except (TypeError, ValueError):
            value = 0
        try:
            sqft = float(a.get("SQFT") or 0)
        except (TypeError, ValueError):
            sqft = 0
        applicant = (a.get("APPLICANT_BUS_NAME") or "").strip().title()
        name = f"{category} — {addr}"[:120] if addr else f"Columbus commercial permit {uid}"
        projects.append({
            "id": f"oh-columbus-{uid}",
            "name": name,
            "city": "Columbus",
            "county": "Franklin",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value > 0 else None,
            "square_footage": sqft if sqft > 0 else None,
            "owner": "",
            "architect": "",
            "general_contractor": applicant,
            "opened_or_announced_date": opened,
            "description": f"Columbus commercial permit ({category}, {general_type}): {addr}.",
            "key_specs": [s for s in [category, general_type, addr] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{
                "title": f"Columbus commercial permit: {addr}",
                "url": a.get("ACA_URL") or f"{base}/0",
            }],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "OH",
            "latitude": a.get("_lat"),
            "longitude": a.get("_lon"),
            "zip": str(a.get("B1_SITUS_ZIP")).strip()[:5] if a.get("B1_SITUS_ZIP") else None,
        })
    return projects


def pull_cleveland(cutoff: dt.date) -> list[dict]:
    # Verified live 2026-07-27: 198,276 total records, max ISSUE_DATE =
    # yesterday. PERMIT_CATEGORY='Commercial...' is a trap -- only ~1,675
    # records carry that label; the real commercial signal is USE_GROUP_1
    # (real IBC occupancy classes with descriptive suffixes, e.g.
    # "B Business", "M Mercantile - Stores...", vs "One Family"/
    # "R-2 Residential..."). Direct LAT/LON fields, no geocoding needed.
    base = "https://services3.arcgis.com/dty2kHktVXHrqO8i/arcgis/rest/services/Building_Permits/FeatureServer"
    commercial_prefixes = ["B ", "M ", "A-", "F-", "I-", "S-", "Commercial", "Mixed Use"]
    like_clause = " OR ".join(f"USE_GROUP_1 LIKE '{p}%'" for p in commercial_prefixes)
    where = f"({like_clause}) AND ISSUE_DATE >= timestamp '{cutoff.isoformat()} 00:00:00'"
    rows = query_layer(
        base, 0, where,
        fields="PERMIT_CATEGORY,USE_GROUP_1,PRIMARY_ADDRESS,JOB_VALUE,CONTRACTOR_NAME,ISSUE_DATE,LAT,LON",
    )
    projects, seen = [], set()
    for a in rows:
        addr = (a.get("PRIMARY_ADDRESS") or "").strip()
        use_group = (a.get("USE_GROUP_1") or "").strip()
        opened = epoch_ms_to_date(a.get("ISSUE_DATE")) or cutoff.isoformat()
        uid = slugify(f"{addr}-{use_group}-{opened}")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        category = (a.get("PERMIT_CATEGORY") or "").strip()
        ptype = project_type_from(f"{use_group} {category}")
        try:
            value = float(a.get("JOB_VALUE") or 0)
        except (TypeError, ValueError):
            value = 0
        contractor = (a.get("CONTRACTOR_NAME") or "").strip().title()
        name = f"{category or use_group} — {addr}"[:120] if addr else f"Cleveland commercial permit {uid}"
        projects.append({
            "id": f"oh-cleveland-{uid}",
            "name": name,
            "city": "Cleveland",
            "county": "Cuyahoga",
            "status": "permitting",
            "project_type": ptype,
            "estimated_value_usd": value if value > 0 else None,
            "square_footage": None,
            "owner": "",
            "architect": "",
            "general_contractor": contractor,
            "opened_or_announced_date": opened,
            "description": f"Cleveland commercial permit ({use_group}, {category or 'permit'}): {addr}.",
            "key_specs": [s for s in [use_group, category, addr] if s],
            "mentioned_brands": [],
            "competitor_watch": categories_for(ptype),
            "sources": [{"title": f"Cleveland commercial permit: {addr}", "url": f"{base}/0"}],
            "open_for": "Active commercial building permit. Early product/spec window.",
            "state": "OH",
            "latitude": a.get("LAT"),
            "longitude": a.get("LON"),
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
    ap.add_argument(
        "--only",
        help="Comma-separated subset: durham,maricopa,fortworth,denver,nashville,hartford,"
        "burlington,act250,providence,delaware,overland_park,bentonville,fargo",
    )
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    pullers = {
        "durham": ("NC", pull_durham),
        "maricopa": ("AZ", pull_maricopa),
        "fortworth": ("TX", pull_fortworth),
        "denver": ("CO", pull_denver),
        "nashville": ("TN", pull_nashville),
        "hartford": ("CT", pull_hartford),
        "burlington": ("VT", pull_burlington),
        "act250": ("VT", pull_act250),
        "providence": ("RI", pull_providence),
        "delaware": ("DE", pull_delaware),
        "overland_park": ("KS", pull_overland_park),
        "bentonville": ("AR", pull_bentonville),
        "fargo": ("ND", pull_fargo),
        "miamidade": ("FL", pull_miamidade),
        "detroit": ("MI", pull_detroit),
        "fairfax": ("VA", pull_fairfax),
        "columbus": ("OH", pull_columbus),
        "cleveland": ("OH", pull_cleveland),
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
