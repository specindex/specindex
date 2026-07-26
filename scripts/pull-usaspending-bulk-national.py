#!/usr/bin/env python3
"""Pull federal construction contract awards from USAspending.gov for ALL
states at once (generalizes scripts/pull-usaspending-ga.py, verified live
2026-07-26 against Texas -- same PSC "Y" construction filter, real awards
returned, e.g. real border-wall/federal-facility contracts).

Covers awarded contracts (already funded, no API key or quota) -- the
national counterpart to SAM.gov's open solicitations. This is a genuine
national-tier source per the sourcing-priority rule (national before
state before county): one broad federal feed establishing a baseline
everywhere, cheaper per-record than any state/county integration.

Like scripts/pull-sam-gov-bulk-national.py, this merges directly into each
state's data/states/{code}.json (append + ID-based dedupe) rather than
writing to data/raw/, since most states have no per-source rebuild
pipeline the way Georgia does. GA is excluded by default for the same
reason that script excludes it -- GA already has a dedicated
pull-usaspending-ga.py -> data/raw/ -> rebuild-ga-corpus.py pipeline;
merging this script's output directly into ga.json would get silently
erased the next time rebuild-ga-corpus.py runs.

Usage:
    python3 scripts/pull-usaspending-bulk-national.py [--years 2] [--states TX,NC,...] [--exclude-states GA]
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

STATES_DIR = ROOT / "data" / "states"

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


def to_project(award: dict, today: dt.date, state: str) -> dict:
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
        "id": f"{state.lower()}-usaspending-{slugify(award_id)[:40]}",
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
        "state": state,
        "zip": zip5,
    }


def pull_state(state: str, years: int, page_size: int, delay: float, limit: int) -> list[dict]:
    today = dt.date.today()
    start_date = today - dt.timedelta(days=int(years * 365.25))

    awards: dict[str, dict] = {}
    page = 1
    while True:
        payload = {
            "filters": {
                "time_period": [{"start_date": start_date.isoformat(), "end_date": today.isoformat()}],
                "place_of_performance_locations": [{"country": "USA", "state": state}],
                "award_type_codes": AWARD_TYPE_CODES,
                "psc_codes": {"require": [["Product", "Y"]]},
            },
            "fields": FIELDS,
            "page": page,
            "limit": page_size,
            "sort": "Award Amount",
            "order": "desc",
        }
        try:
            data = api_post(payload)
        except RuntimeError as exc:
            print(f"  {state}: STOPPED on page {page}: {exc}", file=sys.stderr)
            break

        batch = data.get("results", [])
        for award in batch:
            key = award.get("generated_internal_id") or award.get("Award ID") or str(award.get("internal_id"))
            awards[key] = award

        has_next = (data.get("page_metadata") or {}).get("hasNext", False)
        if not batch or not has_next:
            break
        if limit and len(awards) >= limit:
            break
        page += 1
        time.sleep(delay)

    projects = [to_project(a, today, state) for a in awards.values() if (a.get("Award Amount") or 0) > 0]
    return assign_unique_ids(projects, state)


def merge_into_state_file(state: str, new_projects: list[dict]) -> tuple[int, int]:
    path = STATES_DIR / f"{state.lower()}.json"
    data = json.loads(path.read_text()) if path.exists() else {
        "state": state,
        "generated_at": dt.date.today().isoformat(),
        "date_range": "N/A",
        "capture_method": "",
        "projects": [],
        "stats": {},
    }
    existing = data.get("projects") or []
    existing_ids = {p["id"] for p in existing}

    added = 0
    skipped = 0
    for p in new_projects:
        if p["id"] in existing_ids:
            skipped += 1
            continue
        existing.append(p)
        existing_ids.add(p["id"])
        added += 1

    data["projects"] = existing
    data["stats"] = {**(data.get("stats") or {}), "total": len(existing)}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--states", help="Comma-separated state codes to limit to (default: all with a data/states/ file)")
    ap.add_argument(
        "--exclude-states",
        default="GA",
        help="Comma-separated state codes to skip (default: GA, which has its own dedicated pipeline)",
    )
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--limit-per-state", type=int, default=0, help="cap awards fetched per state, for testing")
    args = ap.parse_args()

    valid_states = {p.stem.upper() for p in STATES_DIR.glob("*.json")}
    target_states = (
        {s.strip().upper() for s in args.states.split(",")} if args.states else valid_states
    )
    exclude_states = (
        {s.strip().upper() for s in args.exclude_states.split(",") if s.strip()}
        if args.exclude_states
        else set()
    )
    target_states = (target_states & valid_states) - exclude_states

    total_added = 0
    for state in sorted(target_states):
        projects = pull_state(state, args.years, args.page_size, args.delay, args.limit_per_state)
        added, skipped = merge_into_state_file(state, projects)
        total_added += added
        print(f"{state}: pulled {len(projects)}, +{added} new (skipped {skipped} already present)")

    print(f"\nTotal new projects added: {total_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
