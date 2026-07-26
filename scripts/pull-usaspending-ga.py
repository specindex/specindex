#!/usr/bin/env python3
"""Pull Georgia federal construction contract awards from USAspending.gov.

Complements scripts/pull-sam-gov-ga.py: SAM.gov covers open solicitations
(pre-award, quota-limited to ~10 calls/day on a public API key). USAspending
covers awarded contracts (already funded, no API key or quota at all) --
labs, military facilities, federal research campuses, etc. Real find
2026-07-25: top GA construction awards in the last 2 years include a $491M
CDC high-containment lab and a $195M Navy Trident Refit Facility expansion.

Uses the public spending_by_award search endpoint, filtered to Product
Service Codes under the "Y" (construction) tier1/tier2 bucket and contract
award types (A/B/C/D -- BPA call, purchase order, delivery order, definitive
contract). No API key required.

Note: Place of Performance City/County/NAICS come back null for most awards
in this dataset (a USAspending data-quality gap, not a bug here) -- ZIP is
populated and used as the location signal instead.

Usage:
    python3 scripts/pull-usaspending-ga.py --years 2 [--limit N] [--out FILE]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import assign_unique_ids, slugify  # noqa: E402

API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
AWARD_TYPE_CODES = ["A", "B", "C", "D"]

FIELDS = [
    "Award ID",
    "Recipient Name",
    "Award Amount",
    "Description",
    "Start Date",
    "End Date",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Place of Performance State Code",
    "Place of Performance City",
    "Place of Performance County Name",
    "Place of Performance Zip5",
]

PROJECT_TYPE_KEYWORDS = [
    ("data_center", ("data center", "data centre")),
    ("healthcare", ("hospital", "medical", "clinic", "laboratory", "lab ")),
    ("aviation", ("hangar", "airfield", "runway", "aviation")),
    ("housing", ("barracks", "housing", "dormitory", "quarters")),
    ("industrial", ("warehouse", "distribution", "industrial", "manufacturing plant")),
    ("office", ("office building", "headquarters", "admin building")),
]

COMPETITOR_WATCH_DEFAULT = {
    "data_center": ["hvac", "switchgear", "fire suppression", "generators", "raised flooring"],
    "healthcare": ["hvac", "medical gas", "elevators", "flooring", "lighting", "fire suppression"],
    "aviation": ["roofing", "hvac", "doors and hardware", "concrete", "lighting"],
    "housing": ["hvac", "roofing", "plumbing fixtures", "flooring", "lighting"],
    "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression"],
    "office": ["glazing", "hvac", "elevators", "lighting", "flooring", "fire suppression"],
}


def project_type_from(text: str) -> str:
    t = text.lower()
    for ptype, keywords in PROJECT_TYPE_KEYWORDS:
        if any(kw in t for kw in keywords):
            return ptype
    return "commercial"


def api_post(payload: dict, tries: int = 4) -> dict:
    data = json.dumps(payload).encode()
    last_exc: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                API_URL, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from None
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise last_exc or RuntimeError("USAspending POST failed")


def status_from_dates(start: str | None, end: str | None, today: dt.date) -> str:
    start_d = dt.date.fromisoformat(start) if start else None
    end_d = dt.date.fromisoformat(end) if end else None
    if start_d and start_d > today:
        return "planning"
    if end_d and end_d < today:
        return "completed"
    return "under_construction"


def to_project(award: dict, today: dt.date) -> dict:
    award_id = award.get("Award ID") or str(award.get("internal_id", "unknown"))
    description = (award.get("Description") or "Untitled award").strip()
    name = description.title()[:120]
    recipient = (award.get("Recipient Name") or "").strip()
    agency = (award.get("Awarding Agency") or "").strip()
    sub_agency = (award.get("Awarding Sub Agency") or "").strip()
    zip5 = (award.get("Place of Performance Zip5") or "").strip()
    city = (award.get("Place of Performance City") or "").strip()
    county = (award.get("Place of Performance County Name") or "").strip()
    amount = award.get("Award Amount")
    start = award.get("Start Date")
    end = award.get("End Date")

    ptype = project_type_from(description)
    generated_id = award.get("generated_internal_id", "")

    key_specs = [f"Award {award_id}", f"Awarding agency: {sub_agency or agency}"]
    if zip5:
        key_specs.append(f"ZIP {zip5}")

    desc_parts = [description]
    if sub_agency and sub_agency != agency:
        desc_parts.append(f"Awarded by {sub_agency} ({agency})")
    elif agency:
        desc_parts.append(f"Awarded by {agency}")
    if end:
        desc_parts.append(f"Period of performance through {end}")
    full_description = ". ".join(p.rstrip(".") for p in desc_parts if p) + "."

    status = status_from_dates(start, end, today)
    open_for = {
        "planning": (
            "Awarded federal construction contract, not yet started. Design/construction-documents "
            "phase is likely still open for product substitution requests."
        ),
        "under_construction": (
            "Awarded federal construction contract, in progress. Construction-documents phase may "
            "still be open for product substitution requests."
        ),
        "completed": (
            "Completed federal contract (period of performance has ended). Not an active spec "
            "window -- useful for GC/agency relationship history and competitor-win tracking only."
        ),
    }[status]

    return {
        "id": f"ga-usaspending-{slugify(award_id)[:40]}",
        "name": name,
        "city": city,
        "county": county,
        "status": status,
        "project_type": ptype,
        "estimated_value_usd": amount,
        "square_footage": None,
        "owner": agency,
        "architect": "",
        "general_contractor": recipient,
        "opened_or_announced_date": start,
        "description": full_description[:900],
        "key_specs": key_specs,
        "mentioned_brands": [],
        "competitor_watch": COMPETITOR_WATCH_DEFAULT.get(ptype, ["hvac", "roofing", "lighting", "concrete"]),
        "sources": [
            {
                "title": f"USAspending.gov award {award_id}: {name[:80]}",
                "url": f"https://www.usaspending.gov/award/{generated_id}" if generated_id else "https://www.usaspending.gov",
            }
        ],
        "open_for": open_for,
        "state": "GA",
        "zip": zip5,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="cap total awards fetched, for testing")
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "usaspending-ga-construction.json"))
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    today = dt.date.today()
    start_date = today - dt.timedelta(days=int(args.years * 365.25))

    awards: dict[str, dict] = {}
    page = 1
    while True:
        payload = {
            "filters": {
                "time_period": [{"start_date": start_date.isoformat(), "end_date": today.isoformat()}],
                "place_of_performance_locations": [{"country": "USA", "state": "GA"}],
                "award_type_codes": AWARD_TYPE_CODES,
                "psc_codes": {"require": [["Product", "Y"]]},
            },
            "fields": FIELDS,
            "page": page,
            "limit": args.page_size,
            "sort": "Award Amount",
            "order": "desc",
        }
        try:
            data = api_post(payload)
        except RuntimeError as exc:
            print(f"STOPPED on page {page}: {exc}", file=sys.stderr)
            break

        batch = data.get("results", [])
        for award in batch:
            key = award.get("generated_internal_id") or award.get("Award ID") or str(award.get("internal_id"))
            awards[key] = award
        print(f"page={page} got={len(batch)} total_so_far={len(awards)}")

        has_next = (data.get("page_metadata") or {}).get("hasNext", False)
        if not batch or not has_next:
            break
        if args.limit and len(awards) >= args.limit:
            break
        page += 1
        time.sleep(args.delay)

    projects = [to_project(a, today) for a in awards.values() if (a.get("Award Amount") or 0) > 0]
    skipped = len(awards) - len(projects)
    if skipped:
        print(f"Skipped {skipped} zero/null-value award(s) (IDV placeholders, not real spend)")
    projects = assign_unique_ids(projects, "GA")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(projects)} projects to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
