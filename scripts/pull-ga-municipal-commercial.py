#!/usr/bin/env python3
"""Pull commercial (not residential) Georgia permits from municipal ArcGIS feeds.

Canonical reference: docs/states/ga.md
Rule: .cursor/rules/georgia-commercial-pull.mdc

Sources currently wired:
  - Alpharetta OpenData_PCE Commercial Permits (EnerGov / Cityworks-style)
  - Johns Creek Active Development Projects (commercial types only)
  - Marietta Developments layer (Industrial / Commercial / Mixed Use only)

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
