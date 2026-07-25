#!/usr/bin/env python3
"""Automatically pull major commercial construction permits from municipal open data APIs."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES_DIR = ROOT / "data" / "states"

HEADERS = {"User-Agent": "SpecIndexPermitIngest/1.0 (+https://specindex.ai)"}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "project"


def load_state_data(state_code: str) -> dict:
    path = STATES_DIR / f"{state_code.lower()}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {
        "state": state_code.upper(),
        "generated_at": date.today().isoformat(),
        "date_range": "Last 90 days",
        "capture_method": "Public municipal permit feeds & web research",
        "projects": [],
    }


def save_state_data(state_code: str, data: dict) -> None:
    path = STATES_DIR / f"{state_code.lower()}.json"
    data["generated_at"] = date.today().isoformat()
    path.write_text(json.dumps(data, indent=2) + "\n")


def merge_project(state_code: str, new_project: dict) -> bool:
    data = load_state_data(state_code)
    existing = data.setdefault("projects", [])
    
    # Check duplicate by ID or name
    pid = new_project["id"]
    for p in existing:
        if p.get("id") == pid or (p.get("name") and p["name"].lower() == new_project["name"].lower()):
            return False
            
    existing.append(new_project)
    save_state_data(state_code, data)
    return True


def pull_chicago_permits() -> int:
    """Pull major commercial new construction / renovation permits from City of Chicago Open Data."""
    print("Pulling Chicago commercial $1M+ permits...")
    
    # Last 90 days cutoff
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    
    params = urllib.parse.urlencode({
        "$limit": 50,
        "$where": f"reported_cost >= 1000000 AND issue_date >= '{cutoff}T00:00:00.000'",
        "$order": "issue_date DESC",
    })
    url = f"https://data.cityofchicago.org/resource/ydr8-5enu.json?{params}"
    
    added = 0
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            rows = json.loads(resp.read())
            print(f"Retrieved {len(rows)} raw permits from Chicago Open Data.")
            for r in rows:
                desc = (r.get("work_description") or "").strip()
                cost = float(r.get("reported_cost") or 0)
                street = f"{r.get('street_number', '')} {r.get('street_direction', '')} {r.get('street_name', '')}".strip()
                date_str = (r.get("issue_date") or "2026-05-01")[:10]
                permit_no = r.get("permit_") or r.get("id", "")
                
                if cost < 1000000 or len(desc) < 8:
                    continue
                    
                # Skip minor single residential
                desc_lower = desc.lower()
                if "single family" in desc_lower or "one story frame" in desc_lower:
                    continue
                    
                ptype = "commercial"
                if "office" in desc_lower:
                    ptype = "office"
                elif "retail" in desc_lower or "store" in desc_lower:
                    ptype = "retail"
                elif "hospital" in desc_lower or "chiller" in desc_lower or "medical" in desc_lower:
                    ptype = "healthcare"
                elif "bank" in desc_lower:
                    ptype = "retail"
                elif "casino" in desc_lower or "event" in desc_lower or "hotel" in desc_lower:
                    ptype = "hospitality"
                elif "apartment" in desc_lower or "dwelling" in desc_lower or "condo" in desc_lower:
                    ptype = "multifamily"
                elif "school" in desc_lower or "university" in desc_lower:
                    ptype = "education"
                else:
                    ptype = "mixed_use"
                    
                proj_name = f"Chicago Permit #{permit_no} — {street}"
                if "casino" in desc_lower:
                    proj_name = f"Chicago Casino & Event Center Site Work — {street}"
                elif "bank" in desc_lower:
                    proj_name = f"New Commercial Bank Facility — {street}"
                elif "office" in desc_lower:
                    proj_name = f"Commercial Office Buildout — {street}"
                elif "retail" in desc_lower:
                    proj_name = f"Retail Commercial Building — {street}"
                    
                p_id = f"il-chicago-permit-{permit_no}"
                
                owner = r.get("contact_1_name") or "Chicago Development Group"
                architect = r.get("contact_2_name") if r.get("contact_2_type") == "ARCHITECT" else ""
                gc = r.get("contact_1_name") if "CONTRACTOR" in r.get("contact_1_type", "") else ""
                
                project = {
                    "id": p_id,
                    "name": proj_name,
                    "state": "IL",
                    "city": "Chicago",
                    "county": "Cook",
                    "status": "under_construction" if "ERECTION" in desc_lower or "NEW" in desc_lower else "permitting",
                    "project_type": ptype,
                    "estimated_value_usd": int(cost),
                    "square_footage": None,
                    "owner": owner,
                    "architect": architect,
                    "general_contractor": gc,
                    "opened_or_announced_date": date_str,
                    "description": f"City of Chicago Building Permit #{permit_no} issued on {date_str}. Reported cost ${cost:,.0f}. Work description: {desc}",
                    "key_specs": [
                        f"Permit #{permit_no}",
                        f"Reported Cost: ${cost:,.0f}",
                        f"Location: {street}, Chicago, IL",
                        f"Review Type: {r.get('review_type', 'Standard')}"
                    ],
                    "mentioned_brands": [],
                    "competitor_watch": ["HVAC", "glazing", "elevators", "roofing", "switchgear"],
                    "sources": [
                        {
                            "title": f"Chicago Building Permit #{permit_no} — Open Data",
                            "url": "https://data.cityofchicago.org/Building-Permits/Building-Permits/ydr8-5enu"
                        }
                    ],
                    "open_for": "Active Chicago commercial permit — open for MEP, glazing, structural and interior sub-trades."
                }
                
                if merge_project("IL", project):
                    added += 1
    except Exception as e:
        print(f"Error pulling Chicago permits: {e}")
        
    print(f"Added {added} new Chicago projects to IL")
    return added


def main() -> None:
    tot = pull_chicago_permits()
    print(f"\nCompleted open permit ingestion. Added {tot} new projects.")


if __name__ == "__main__":
    main()
