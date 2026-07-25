#!/usr/bin/env python3
"""Fetch Fulton County / Atlanta public planning PDFs and index project document sources."""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "documents" / "fulton-county"
INDEX = OUT / "index.json"

USER_AGENT = "SpecIndexDocumentBot/1.0 (+https://specindex.ai)"
ctx = ssl.create_default_context()

# Official Fulton County (Fulton Industrial District only) permit/spec forms
FULTON_COUNTY_PDFS = [
    {
        "title": "Commercial Plan Review / Building Permit Instructions",
        "url": "https://www.fultoncountyga.gov/-/media/Departments/Public-Works/Planning-Zoning-and-Permits/Commercial-Plan-Review---Building-Permit-Instructions-updated-8-25-25.pdf",
        "category": "county_specifications",
    },
    {
        "title": "Building Permit Application and Site Plan Checklist",
        "url": "https://www.fultoncountyga.gov/-/media/Departments/Public-Works/Planning-Zoning-and-Permits/Permits-and-plan-review/updated-forms/Building_Permit_Application_and_Site_Plan_Checklist.pdf",
        "category": "county_specifications",
    },
    {
        "title": "DCP Digital Submittal Instructions (City of Atlanta)",
        "url": "https://www.atlantaga.gov/home/showdocument?id=47397",
        "category": "atlanta_specifications",
    },
]

# Project-specific public document URLs (BoardDocs, Invest Atlanta, Accela-linked)
FULTON_PROJECT_DOCS = [
    {
        "project_id": "centennial-yards",
        "title": "Invest Atlanta Board Presentation — Centennial Yards (June 2024)",
        "url": "https://go.boarddocs.com/ga/investatlanta/Board.nsf/files/D6DSS57406FE/$file/Centennial%20Yards%20-%20Invest%20Atlanta%20Board%20and%20Finance%20Committee%20Presentation%20(06.20.2024)vFinal.pdf",
    },
    {
        "project_id": "centennial-yards",
        "title": "Centennial Yards Site Plan PDF (CIM Property Capsule)",
        "url": "https://cimgroup.propertycapsule.com/property/capsule_data/803/property/pdf/siteplan/3393.pdf",
    },
    {
        "project_id": "teachers-village-atlanta",
        "title": "Invest Atlanta — Teachers Village project page",
        "url": "https://www.investatlanta.com/developments/under-construction/teachers-village",
        "type": "page",
    },
]

ACCELA_SEARCHES = [
    {
        "project_id": "teachers-village-atlanta",
        "street": "Fairlie",
        "notes": "Teachers Village tower — search Atlanta Accela Planning",
    },
    {
        "project_id": "motto-hilton-midtown",
        "street": "Peachtree",
        "street_no": "512",
        "notes": "512 W Peachtree Motto hotel permit",
    },
    {
        "project_id": "overlook-at-garson",
        "street": "Garson",
        "notes": "Overlook at Garson — Garson Drive NE",
    },
    {
        "project_id": "centennial-yards-elliott-hotel",
        "street": "Elliott",
        "notes": "Centennial Yards Elliott Street boutique hotel",
    },
]


def fetch(url: str, timeout: int = 45) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read(), resp.headers.get("Content-Type", ""), resp.geturl()


def safe_filename(title: str, ext: str = ".pdf") -> str:
    name = re.sub(r"[^\w\- ]+", "", title)
    name = re.sub(r"\s+", "-", name.strip()).lower()
    return (name[:70] or "document") + ext


def download(url: str, dest: Path) -> dict:
    data, ctype, final = fetch(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {
        "path": str(dest.relative_to(ROOT)),
        "url": final,
        "content_type": ctype,
        "size_bytes": len(data),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    county_dir = OUT / "county-forms"
    project_dir = OUT / "projects"
    county_dir.mkdir(exist_ok=True)
    project_dir.mkdir(exist_ok=True)

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jurisdiction_notes": (
            "Fulton County Public Works only handles Planning/Zoning/Permits for the "
            "Fulton Industrial Business District. Most Fulton County corpus projects "
            "are in incorporated cities (primarily Atlanta, Alpharetta, South Fulton). "
            "Atlanta project plans/specs are in Accela Citizen Access (Planning/Building tabs)."
        ),
        "county_portal": "https://www.fultoncountyga.gov/inside-fulton-county/fulton-county-departments/public-works/planning-zoning-and-permitting",
        "atlanta_portal": "https://aca-prod.accela.com/ATLANTA_GA/Cap/CapHome.aspx?TabName=Planning&module=Planning",
        "county_forms": [],
        "project_documents": [],
        "accela_search_targets": ACCELA_SEARCHES,
        "errors": [],
    }

    for item in FULTON_COUNTY_PDFS:
        try:
            ext = ".pdf" if ".pdf" in item["url"].lower() else ".pdf"
            fname = safe_filename(item["title"], ext)
            saved = download(item["url"], county_dir / fname)
            saved["title"] = item["title"]
            saved["category"] = item["category"]
            results["county_forms"].append(saved)
            print(f"Saved county form: {fname}")
        except Exception as e:
            results["errors"].append(f"{item['title']}: {e}")
            print(f"Error {item['title']}: {e}")
        time.sleep(0.4)

    for item in FULTON_PROJECT_DOCS:
        if item.get("type") == "page":
            results["project_documents"].append(
                {
                    "project_id": item["project_id"],
                    "title": item["title"],
                    "url": item["url"],
                    "type": "reference_page",
                }
            )
            continue
        try:
            pid_dir = project_dir / item["project_id"]
            fname = safe_filename(item["title"])
            saved = download(item["url"], pid_dir / fname)
            saved["project_id"] = item["project_id"]
            saved["title"] = item["title"]
            results["project_documents"].append(saved)
            print(f"Saved project doc: {item['project_id']}/{fname}")
        except Exception as e:
            results["errors"].append(f"{item['project_id']} {item['title']}: {e}")
            print(f"Error {item['title']}: {e}")
        time.sleep(0.4)

    INDEX.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nWrote index to {INDEX}")


if __name__ == "__main__":
    main()
