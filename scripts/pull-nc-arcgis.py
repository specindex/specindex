#!/usr/bin/env python3
"""Pull commercial (not residential) North Carolina permits from ArcGIS feeds.

Canonical reference: docs/states/nc.md (mirrors docs/states/ga.md's approach)

Sources wired, both verified live 2026-07-25 before building:
  - Mecklenburg County (Charlotte) "Building Permits" FeatureServer
    (meckgis.mecklenburgcountync.gov) -- permittype='Commercial', with a
    "SPT"/"No Review Bldg Permit" exclusion: ~67% of a live sample under
    that filter alone were temporary event permits (concert stages, food
    trailers) coded identically to real small commercial work
  - Wake County (Raleigh + county-wide) "Building Permits" FeatureServer
    (services.arcgis.com/v400IkDOw1ad7Yad) -- permitclassmapped=
    'Non-Residential', PLUS a text-based residential exclusion on top: that
    field alone let a "DETACHED SINGLE FAMILY DWELLING" condo project
    through in a live sample, so it can't be trusted alone (same lesson as
    Georgia's sources).

Rejected without building (checked live, not just guessed): all 17 Accela
slugs tried for major NC metros returned 404 except CONCORD (verified
real, working Citizen Access portal) -- NC's major metros lean ArcGIS-first,
unlike Georgia where Accela was the dominant pattern for Atlanta/Cobb/Gwinnett.

Usage:
    python3 scripts/pull-nc-arcgis.py --months 24 [--merge]
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

RESIDENTIAL_HINTS = re.compile(
    r"\b(single family|single-family|detached dwelling|townhome|townhouse|subdivision|"
    r"duplex|triplex|apartment|multifamily|condo|dwelling|residential)\b",
    re.I,
)
# Mecklenburg's "Commercial" permittype includes temporary event structures
# (concert stages, food trailers) coded identically to real small commercial
# permits (usdcdesc "437 - Commercial - No plan review") -- the only reliable
# signal found live 2026-07-25 is the "SPT" / "No Review Bldg Permit" pattern.
TEMP_EVENT_HINTS = re.compile(r"^SPT\b|no review bldg permit", re.I)
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
    """Returns each feature's attributes dict with `_lat`/`_lon` merged in
    from its geometry (outSR=4326, real WGS84 coordinates -- the same
    param used during this session's source-verification passes) so
    callers can persist real coordinates instead of discarding them."""
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


def pull_mecklenburg(cutoff: dt.date) -> list[dict]:
    base = "https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingPermits/FeatureServer"
    where = f"permittype = 'Commercial' AND issuedate >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields="permitnum,permitdesc,permittype,usdcdesc,projname,projadd,zipcode,issuedate,bldgcost,totalsqft,ownname,worktype,workdesc",
    )
    projects = []
    seen = set()
    for a in rows:
        permit_no = (a.get("permitnum") or "").strip()
        addr = (a.get("projadd") or "").strip()
        desc = (a.get("permitdesc") or a.get("workdesc") or "").strip()
        usdc = (a.get("usdcdesc") or "").strip()
        projname_raw = a.get("projname") or ""
        blob = f"{desc} {usdc} {projname_raw}"
        if not permit_no:
            continue
        if TEMP_EVENT_HINTS.search(projname_raw) or TEMP_EVENT_HINTS.search(desc):
            continue
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        if permit_no in seen:
            continue
        seen.add(permit_no)
        cost = a.get("bldgcost")
        sqft = a.get("totalsqft")
        opened = epoch_ms_to_date(a.get("issuedate")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        name = (a.get("projname") or "").strip() or addr.title()
        projects.append(
            {
                "id": f"nc-mecklenburg-{slugify(permit_no)}",
                "name": name[:120],
                "city": "Charlotte",
                "county": "Mecklenburg",
                "status": "permitting",
                "project_type": ptype,
                "estimated_value_usd": cost if cost and cost > 0 else None,
                "square_footage": sqft if sqft and sqft > 0 else None,
                "owner": (a.get("ownname") or "").strip(),
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": opened,
                "description": f"Mecklenburg County commercial permit {permit_no}: {desc or usdc}. {addr}.",
                "key_specs": [s for s in [usdc, addr, f"Permit {permit_no}"] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Mecklenburg County commercial permit {permit_no}",
                        "url": "https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingPermits/FeatureServer/0",
                    }
                ],
                "open_for": "Active commercial building permit. Early product/spec window.",
                "latitude": a.get("_lat"),
                "longitude": a.get("_lon"),
                "zip": str(a["zipcode"]).strip() or None if a.get("zipcode") else None,
                "state": "NC",
            }
        )
    return projects


def pull_wake(cutoff: dt.date) -> list[dict]:
    base = "https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer"
    where = f"permitclassmapped = 'Non-Residential' AND issueddate >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields=(
            "permitnum,projectname,proposeduse,description,estprojectcost,totalsqft,"
            "contractorcompanyname,streetnum,streetname,streettype,issueddate,"
            "statuscurrentmapped,parcelownername"
        ),
    )
    projects = []
    seen = set()
    for a in rows:
        permit_no = (a.get("permitnum") or "").strip()
        desc = (a.get("description") or "").strip()
        proposed_use = (a.get("proposeduse") or "").strip()
        blob = f"{desc} {proposed_use} {a.get('projectname') or ''}"
        if not permit_no:
            continue
        # permitclassmapped='Non-Residential' isn't fully reliable on its own --
        # confirmed live 2026-07-25 it let a "DETACHED SINGLE FAMILY DWELLING"
        # condo project through. Apply the same text-based exclusion as every
        # other source in this corpus.
        if RESIDENTIAL_HINTS.search(blob) and not COMMERCIAL_HINTS.search(blob):
            continue
        if permit_no in seen:
            continue
        seen.add(permit_no)
        addr = " ".join(
            p for p in [a.get("streetnum"), a.get("streetname"), a.get("streettype")] if p
        ).strip()
        cost = a.get("estprojectcost")
        sqft = a.get("totalsqft")
        opened = epoch_ms_to_date(a.get("issueddate")) or cutoff.isoformat()
        ptype = project_type_from(blob)
        status = (a.get("statuscurrentmapped") or "").strip()
        name = (a.get("projectname") or "").strip() or addr.title() or proposed_use.title()
        projects.append(
            {
                "id": f"nc-wake-{slugify(permit_no)}",
                "name": name[:120],
                "city": "Raleigh",
                "county": "Wake",
                "status": "permitting" if status.lower() in {"permit issued", "issued"} else "planning",
                "project_type": ptype,
                "estimated_value_usd": cost if cost and cost > 0 else None,
                "square_footage": sqft if sqft and sqft > 0 else None,
                "owner": (a.get("parcelownername") or "").strip(),
                "architect": "",
                "general_contractor": (a.get("contractorcompanyname") or "").strip(),
                "opened_or_announced_date": opened,
                "description": f"Wake County commercial permit {permit_no}: {desc or proposed_use}. {addr}.",
                "key_specs": [s for s in [proposed_use, addr, f"Permit {permit_no}"] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Wake County commercial permit {permit_no}",
                        "url": "https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer/0",
                    }
                ],
                "open_for": "Active commercial building permit. Early product/spec window.",
                "state": "NC",
                "latitude": a.get("_lat"),
                "longitude": a.get("_lon"),
            }
        )
    return projects


def merge_into_nc(new_projects: list[dict]) -> tuple[int, int]:
    path = ROOT / "data" / "states" / "nc.json"
    data = json.loads(path.read_text())
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
    if "ArcGIS" not in (data.get("capture_method") or ""):
        data["capture_method"] = (
            f"{data.get('capture_method', '').rstrip('. ')}, Mecklenburg/Wake County ArcGIS commercial permits"
        )
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added, len(existing)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true", help="Merge into data/states/nc.json")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    print(f"NC commercial ArcGIS pull, cutoff {cutoff}")
    buckets = {
        "mecklenburg": pull_mecklenburg(cutoff),
        "wake": pull_wake(cutoff),
    }
    all_projects: list[dict] = []
    for name, rows in buckets.items():
        print(f"  {name}: {len(rows)} commercial projects")
        all_projects.extend(rows)

    out = ROOT / "data" / "raw" / "nc-arcgis-commercial.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"projects": all_projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_projects)} to {out}")

    if args.merge:
        added, total = merge_into_nc(all_projects)
        print(f"Merged into nc.json: +{added} new, {total} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
