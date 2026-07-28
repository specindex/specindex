#!/usr/bin/env python3
"""Pull commercial (not residential) Georgia permits from municipal ArcGIS feeds.

Canonical reference: docs/states/ga.md
Rule: .cursor/rules/georgia-commercial-pull.mdc

Sources currently wired:
  - Alpharetta OpenData_PCE Commercial Permits (EnerGov / Cityworks-style)
  - Johns Creek Active Development Projects (commercial types only)
  - Marietta Developments layer (Industrial / Commercial / Mixed Use only)
  - Savannah/Chatham SAGIS Site Development Permits (private site work only,
    text-filtered for commercial signal -- checked 2026-07-25, live as of
    2026-07-17)
  - Fulton County "Building Permits Issued" (JobTypeDescription='Commercial')
    -- checked 2026-07-25, live as of 2026-06-23, includes square footage.
    Has a real ~1-month ingestion lag (overall dataset max date trails "today"
    by about a month) -- a --months 1 pull alone will return 0 for this source;
    use --months 2+ or accept a short lag window. Covers unincorporated Fulton
    + cities without their own system; may overlap with Alpharetta's separate
    feed (both are within Fulton County) -- cross-source dedup in
    project_identity.py handles exact name/address matches but a full-county
    feed isn't guaranteed to be caught.

  - Forsyth County GA "Public_EnerGovPlans/Building_Permits"
    (PermitNumber LIKE 'BLDGCOMM%') -- checked 2026-07-26, live as of
    2026-07-23 on ApplyDate. CONFIRMED via real coordinates (outSR=4326:
    34.15-34.31N, 84.0-84.2W) this is Forsyth County GA, NOT Forsyth County
    NC -- two pieces of secondhand research disagreed about this for the
    exact same URL; see docs/ROADMAP.md item 27. Sparse schema: no address,
    description, or contractor fields exist despite secondhand research
    claiming otherwise -- only PermitNumber/ParcelNumber/PermitType/
    PermitClassDescription/dates/Link are real.

Checked and rejected 2026-07-25: Columbus/Muscogee County "BuildingPermits"
MapServer has a purpose-built Commercial layer with excellent fields (owner,
contractor, valuation, sqft) but is stale -- most recent record is 2022-04-15,
so it contributes nothing to any realistic recency window. Not wired.

Checked and rejected 2026-07-26: a secondhand-research "Hall County GA"
source (services2.arcgis.com/HdTo6HJqh92wn4D8/.../Building_Permit_
Applications_Feature_Layer_view) is actually **Nashville/Davidson County,
Tennessee** -- its own State field says "TN", cities are Nashville/Old
Hickory/Brentwood, coordinates 36.0-36.2N/86.6-86.9W (real Hall County GA
is ~34.3N/83.8W). Caught by checking real coordinates before merging, same
discipline that resolved the Forsyth GA/NC question above -- but this one
slipped past an earlier, incomplete check (freshness/schema were verified,
geography wasn't) before being caught here. Lesson reinforced: always
verify city/state/coordinates on a real sample, not just date freshness
and field names, especially for sources found via generic web search
rather than a jurisdiction-specific domain.

Residential is hard-filtered out. Window defaults to last 12 months when a date
field exists; undated layers keep only clearly commercial type labels.

Usage:
    python3 scripts/pull-ga-municipal-commercial.py --months 12
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
UA = {"User-Agent": "Mozilla/5.0 (SpecIndex research; +https://specindex.ai)"}

RESIDENTIAL_HINTS = re.compile(
    r"\b(residential|single[- ]family|townhome|townhouse|subdivision|"
    r"duplex|triplex|apartment|multifamily|condo|dwelling|home)\b",
    re.I,
)
COMMERCIAL_TYPES = re.compile(
    r"\b(commercial|industrial|office|retail|hotel|hospitality|mixed[- ]?use|"
    r"warehouse|distribution|medical|hospital|school|civic|church|"
    r"data.?center|land disturbance)\b",
    re.I,
)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read())


def query_layer(base: str, layer: int, where: str, fields: str = "*", page_size: int = 1000) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": fields,
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "returnGeometry": "false",
        }
        url = f"{base}/{layer}/query?{urllib.parse.urlencode(params)}"
        data = fetch_json(url)
        if "error" in data:
            raise RuntimeError(str(data["error"])[:200])
        feats = data.get("features") or []
        out.extend(f.get("attributes") or {} for f in feats)
        if len(feats) < page_size or not data.get("exceededTransferLimit"):
            break
        offset += page_size
    return out


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:52] or "project"


def epoch_ms_to_date(v) -> str | None:
    if v is None:
        return None
    try:
        # ArcGIS often returns epoch ms
        if isinstance(v, (int, float)) and v > 1e11:
            return dt.datetime.utcfromtimestamp(v / 1000).date().isoformat()
        if isinstance(v, (int, float)) and v > 1e9:
            return dt.datetime.utcfromtimestamp(v).date().isoformat()
        s = str(v)
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return s[:10]
    except Exception:  # noqa: BLE001
        return None
    return None


def is_residential_blob(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p)
    return bool(RESIDENTIAL_HINTS.search(blob))


def project_type_from(text: str) -> str:
    t = text.lower()
    if "industrial" in t or "warehouse" in t or "distribution" in t:
        return "industrial"
    if "hotel" in t or "hospitality" in t:
        return "hospitality"
    if "hospital" in t or "medical" in t:
        return "healthcare"
    if "office" in t:
        return "office"
    if "retail" in t or "store" in t:
        return "retail"
    if "school" in t or "education" in t:
        return "education"
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
        "education": ["hvac", "roofing", "glazing", "lighting", "flooring", "fire suppression"],
        "mixed_use": ["glazing", "hvac", "elevators", "roofing", "lighting", "flooring"],
    }.get(ptype, ["hvac", "roofing", "lighting", "concrete", "fire suppression"])


def pull_alpharetta(cutoff: dt.date) -> list[dict]:
    base = "https://alphagis.alpharetta.ga.us/arcgis/rest/services/OpenData/OpenData_PCE_Full/MapServer"
    # Layer 1 is Commercial Permits. Date filter in SQL for ArcGIS.
    where = f"DATE_ENTERED >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(base, 1, where)
    projects = []
    seen = set()
    for a in rows:
        name = (a.get("CASE_NAME") or "").strip()
        case_type = (a.get("CASE_TYPE_DESC") or "").strip()
        case_no = (a.get("CASE_NUMBER") or "").strip()
        loc = (a.get("Location") or "").strip()
        status = (a.get("STATUS_CODE") or "").strip()
        if not name or not case_no:
            continue
        if is_residential_blob(name, case_type):
            continue
        # Deduplicate task rows: same CASE_NUMBER appears once per inspection task.
        if case_no in seen:
            continue
        seen.add(case_no)
        opened = epoch_ms_to_date(a.get("DATE_ENTERED")) or cutoff.isoformat()
        ptype = project_type_from(f"{case_type} {name}")
        projects.append(
            {
                "id": f"ga-alpharetta-{slugify(case_no)}",
                "name": name[:120],
                "city": "Alpharetta",
                "county": "Fulton",
                "status": "permitting" if status.upper() in {"OPEN", "ISSUE", "ISSUED"} else "planning",
                "project_type": ptype,
                "estimated_value_usd": None,
                "square_footage": None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": opened,
                "description": (
                    f"Alpharetta commercial permit {case_no}: {case_type}. "
                    f"Location: {loc or 'not listed'}. Status {status or 'unknown'}."
                ),
                "key_specs": [s for s in [case_type, loc, f"Permit {case_no}"] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Alpharetta commercial permit {case_no}, city open data",
                        "url": "https://alphagis.alpharetta.ga.us/arcgis/rest/services/OpenData/OpenData_PCE_Full/MapServer/1",
                    }
                ],
                "open_for": "Active commercial permit. Interior and MEP packages may still be open.",
                "state": "GA",
            }
        )
    return projects


def pull_johns_creek() -> list[dict]:
    base = "https://services1.arcgis.com/bqfNVPUK3HOnCFmA/arcgis/rest/services/ActiveDevelopmentProjects/FeatureServer"
    rows = query_layer(base, 0, "1=1")
    projects = []
    for a in rows:
        name = (a.get("Name") or "").strip()
        typ = (a.get("Type") or "").strip()
        status = (a.get("Status") or "").strip()
        addr = (a.get("Address") or "").strip()
        comments = (a.get("Comments") or "").strip()
        if not name:
            continue
        if status.lower() in {"complete", "removed", "withdrawn", "cancelled"}:
            continue
        if is_residential_blob(name, typ, comments):
            continue
        # Keep land disturbance only when comments/name suggest commercial; pure residential LD drops.
        if typ.lower() == "land disturbance" and not COMMERCIAL_TYPES.search(f"{name} {comments}"):
            # Keep non-residential-looking LD for commercial site work (warehouses etc.)
            if not re.search(r"\b(retail|office|industrial|commercial|center|plaza|park)\b", f"{name} {comments}", re.I):
                continue
        ptype = project_type_from(f"{typ} {name} {comments}")
        oid = a.get("OBJECTID")
        projects.append(
            {
                "id": f"ga-johnscreek-{oid}-{slugify(name)}",
                "name": name[:120],
                "city": "Johns Creek",
                "county": "Fulton",
                "status": "under_construction" if "construct" in status.lower() else "planning",
                "project_type": ptype,
                "estimated_value_usd": None,
                "square_footage": None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": None,
                "description": (
                    f"Johns Creek active development: {typ or 'project'}. "
                    f"Address {addr or 'not listed'}. Status {status or 'active'}."
                    + (f" {comments}" if comments else "")
                ),
                "key_specs": [s for s in [typ, addr, f"{a.get('Acres')} acres" if a.get("Acres") else ""] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Johns Creek active development: {name}",
                        "url": "https://services1.arcgis.com/bqfNVPUK3HOnCFmA/arcgis/rest/services/ActiveDevelopmentProjects/FeatureServer/0",
                    }
                ],
                "open_for": "Active development project. Early civil and building product window.",
                "state": "GA",
            }
        )
    return projects


def pull_marietta() -> list[dict]:
    base = "https://secure.mariettaga.gov/server/rest/services/HubContent/AGOL_OpenData/MapServer"
    rows = query_layer(base, 8, "1=1")
    keep_types = {"industrial", "commercial", "mixed use", "mixed-use", "office", "retail"}
    projects = []
    for a in rows:
        name = (a.get("Name") or a.get("NewName") or "").strip()
        typ = (a.get("TYPE") or "").strip()
        if not name:
            continue
        if typ.lower() not in keep_types:
            continue
        if is_residential_blob(name, typ):
            continue
        ptype = project_type_from(typ)
        oid = a.get("OBJECTID")
        units = a.get("UnitCount")
        projects.append(
            {
                "id": f"ga-marietta-{oid}-{slugify(name)}",
                "name": name[:120],
                "city": "Marietta",
                "county": "Cobb",
                "status": "planning",
                "project_type": ptype,
                "estimated_value_usd": None,
                "square_footage": None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": None,
                "description": (
                    f"Marietta mapped development parcel typed as {typ}. "
                    f"{'Unit count ' + str(units) + '.' if units else 'No unit count published.'}"
                ),
                "key_specs": [s for s in [typ, f"{units} units" if units else ""] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Marietta developments layer: {name}",
                        "url": "https://secure.mariettaga.gov/server/rest/services/HubContent/AGOL_OpenData/MapServer/8",
                    }
                ],
                "open_for": "Mapped commercial or industrial development. Timing depends on entitlement stage.",
                "state": "GA",
            }
        )
    return projects


def pull_savannah(cutoff: dt.date) -> list[dict]:
    base = "https://pub.sagis.org/arcgis/rest/services/Savannah/BuildingPermit/MapServer"
    # Layer 0 is "Site Permit by Work Class". No project-name field; WorkClass
    # distinguishes Full Site-Private (kept) from Subdivision/Grading/Government
    # (dropped -- Subdivision is residential, Grading is bare site prep, and
    # Government mixes non-building infrastructure work with actual civic
    # buildings with no way to tell them apart from WorkClass alone).
    where = f"WorkClass = 'Full Site-Private' AND IssuedDate_DATE >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields="PermitNumber,WorkClass,PermitStatus,Address,ApplicantName,Description,Permit_Value,IssuedDate_DATE",
    )
    projects = []
    seen = set()
    for a in rows:
        permit_no = (a.get("PermitNumber") or "").strip()
        addr = (a.get("Address") or "").strip()
        desc = (a.get("Description") or "").strip()
        status = (a.get("PermitStatus") or "").strip()
        applicant = (a.get("ApplicantName") or "").strip()
        if not permit_no or not desc:
            continue
        if is_residential_blob(desc, addr):
            continue
        if permit_no in seen:
            continue
        seen.add(permit_no)
        value = a.get("Permit_Value")
        value = value if value and value > 0 else None
        opened = epoch_ms_to_date(a.get("IssuedDate_DATE")) or cutoff.isoformat()
        ptype = project_type_from(desc)
        name = addr.title() if addr else desc[:60]
        projects.append(
            {
                "id": f"ga-savannah-{slugify(permit_no)}",
                "name": (f"Site development — {name}")[:120],
                "city": "Savannah",
                "county": "Chatham",
                "status": "permitting" if status.lower() in {"issued", "open"} else "planning",
                "project_type": ptype,
                "estimated_value_usd": value,
                "square_footage": None,
                "owner": applicant,
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": opened,
                "description": f"Savannah site development permit {permit_no}: {desc[:400]}",
                "key_specs": [s for s in ["Full Site-Private", addr, f"Permit {permit_no}"] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Savannah (SAGIS) site development permit {permit_no}",
                        "url": "https://pub.sagis.org/arcgis/rest/services/Savannah/BuildingPermit/MapServer/0",
                    }
                ],
                "open_for": "Active private site development permit. Early civil/site package window.",
                "state": "GA",
            }
        )
    return projects


def pull_fulton(cutoff: dt.date) -> list[dict]:
    base = "https://services1.arcgis.com/bqfNVPUK3HOnCFmA/arcgis/rest/services/Building_Permits_Issued/FeatureServer"
    where = f"JobTypeDescription = 'Commercial' AND ISSUE_DATE >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields="JobID,JobAddress,JobSquareFootage,JobStatus,ISSUE_DATE",
    )
    projects = []
    seen = set()
    for a in rows:
        job_id = (a.get("JobID") or "").strip()
        addr = (a.get("JobAddress") or "").strip()
        if not job_id or not addr:
            continue
        if is_residential_blob(addr):
            continue
        if job_id in seen:
            continue
        seen.add(job_id)
        sqft = a.get("JobSquareFootage")
        status = (a.get("JobStatus") or "").strip()
        opened = epoch_ms_to_date(a.get("ISSUE_DATE")) or cutoff.isoformat()
        projects.append(
            {
                "id": f"ga-fulton-{slugify(job_id)}",
                "name": f"Commercial permit — {addr.title()}"[:120],
                "city": "",
                "county": "Fulton",
                "status": "permitting" if status.lower() in {"issued", "open"} else "planning",
                "project_type": "commercial",
                "estimated_value_usd": None,
                "square_footage": sqft if sqft and sqft > 0 else None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": opened,
                "description": (
                    f"Fulton County commercial building permit {job_id} at {addr}. "
                    f"{f'{sqft:,} sq ft. ' if sqft else ''}Status {status or 'unknown'}."
                ),
                "key_specs": [s for s in ["Commercial", addr, f"Permit {job_id}", f"{sqft} sq ft" if sqft else ""] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for("commercial"),
                "sources": [
                    {
                        "title": f"Fulton County commercial permit {job_id}",
                        "url": "https://services1.arcgis.com/bqfNVPUK3HOnCFmA/arcgis/rest/services/Building_Permits_Issued/FeatureServer/0",
                    }
                ],
                "open_for": "Active commercial building permit. Early product/spec window.",
                "state": "GA",
            }
        )
    return projects


def pull_forsyth_ga(cutoff: dt.date) -> list[dict]:
    base = "https://geo.forsythco.com/gis3/rest/services/Public_EnerGovPlans/Building_Permits/FeatureServer"
    where = f"PermitNumber LIKE 'BLDGCOMM%' AND ApplyDate >= DATE '{cutoff.isoformat()}'"
    rows = query_layer(
        base, 0, where,
        fields="PermitNumber,ParcelNumber,PermitType,PermitClassDescription,PermitClass,PermitStatus,ApplyDate,IssueDate,Link",
    )
    projects = []
    seen = set()
    for a in rows:
        permit_no = (a.get("PermitNumber") or "").strip()
        if not permit_no:
            continue
        if permit_no in seen:
            continue
        seen.add(permit_no)
        parcel = (a.get("ParcelNumber") or "").strip()
        class_desc = (a.get("PermitClassDescription") or "").strip()
        permit_class = (a.get("PermitClass") or "").strip()
        status = (a.get("PermitStatus") or "").strip()
        link = (a.get("Link") or "").strip()
        opened = epoch_ms_to_date(a.get("ApplyDate")) or cutoff.isoformat()
        ptype = project_type_from(f"{class_desc} {permit_class}")
        # No address/description/contractor fields exist on this layer --
        # confirmed 2026-07-26, contradicting a secondhand-research claim
        # that they did. Name and description are necessarily sparse.
        name = f"{class_desc or 'Commercial permit'} (parcel {parcel})" if parcel else (class_desc or "Commercial permit")
        projects.append(
            {
                "id": f"ga-forsyth-{slugify(permit_no)}",
                "name": name[:120],
                "city": "",
                "county": "Forsyth",
                "status": "permitting" if status.lower() == "issued" else "planning",
                "project_type": ptype,
                "estimated_value_usd": None,
                "square_footage": None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": opened,
                "description": (
                    f"Forsyth County GA commercial permit {permit_no}: {class_desc or permit_class}. "
                    f"Parcel {parcel or 'not listed'}. Status {status or 'unknown'}."
                ),
                "key_specs": [s for s in [class_desc, permit_class, f"Parcel {parcel}", f"Permit {permit_no}"] if s],
                "mentioned_brands": [],
                "competitor_watch": categories_for(ptype),
                "sources": [
                    {
                        "title": f"Forsyth County GA commercial permit {permit_no}",
                        "url": link or "https://geo.forsythco.com/gis3/rest/services/Public_EnerGovPlans/Building_Permits/FeatureServer/0",
                    }
                ],
                "open_for": "Active commercial building permit. Early product/spec window.",
                "state": "GA",
            }
        )
    return projects


def merge_into_ga() -> tuple[int, int]:
    """Rebuild ga.json from all raw sources (safe dedupe path)."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "rebuild-ga-corpus.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "rebuild-ga-corpus.py failed")
    print(result.stdout.strip())
    ga = json.loads((ROOT / "data" / "states" / "ga.json").read_text())
    return ga.get("stats", {}).get("total", len(ga.get("projects", []))), 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--merge", action="store_true", help="Merge into data/states/ga.json")
    args = ap.parse_args()
    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))

    print(f"Commercial-only municipal pull, cutoff {cutoff}")
    buckets = {
        "alpharetta": pull_alpharetta(cutoff),
        "johns_creek": pull_johns_creek(),
        "marietta": pull_marietta(),
        "savannah": pull_savannah(cutoff),
        "fulton": pull_fulton(cutoff),
        "forsyth_ga": pull_forsyth_ga(cutoff),
    }
    all_projects: list[dict] = []
    for name, rows in buckets.items():
        print(f"  {name}: {len(rows)} commercial projects")
        all_projects.extend(rows)

    out = ROOT / "data" / "raw" / "ga-municipal-commercial.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"projects": all_projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_projects)} to {out}")

    if args.merge:
        total, skipped = merge_into_ga()
        print(f"Rebuilt ga.json: {total} projects (skipped raw noise: {skipped})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
