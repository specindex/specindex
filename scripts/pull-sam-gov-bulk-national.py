#!/usr/bin/env python3
"""Pull construction opportunities for ALL 50 states from SAM.gov's bulk CSV.

Generalizes scripts/pull-sam-gov-bulk-ga.py (built 2026-07-25 to unblock
Georgia's quota-limited SAM.gov API pull) to every state at once, since the
underlying file is government-wide anyway -- filtering it to one state and
throwing away the rest was leaving real, free data on the table for the
other 49 states, most of which (per docs/ROADMAP.md item 8) only have a
handful of hand-researched projects.

Unlike the GA-specific corpus (which has a dedicated rebuild-ga-corpus.py
pipeline combining DRI/municipal/Accela/etc.), most other states only have
a thin data/states/{code}.json with no per-source raw pipeline. This script
merges directly into each state's file (append + ID-based dedupe) rather
than writing to data/raw/, since there's no per-state rebuild step to
consume a raw file the way Georgia's does.

Usage:
    python3 scripts/pull-sam-gov-bulk-national.py [--csv-path FILE] [--states GA,TX,...]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import slugify  # noqa: E402

BULK_URL = "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv"
STATES_DIR = ROOT / "data" / "states"

# Same building-construction-only NAICS set as pull-sam-gov-ga.py --
# excludes highway/civil codes, not building-envelope/MEP spec opportunities.
NAICS_CODES = {
    "236220": "commercial",
    "236210": "industrial",
}

STATUS_BY_TYPE = {
    "Presolicitation": "planning",
    "Sources Sought": "planning",
    "Special Notice": "planning",
    "Solicitation": "bidding",
    "Combined Synopsis/Solicitation": "bidding",
    "Modification/Amendment/Cancel": "bidding",
    "Award Notice": "under_construction",
}

COMPETITOR_WATCH_DEFAULT = {
    "commercial": ["glazing", "hvac", "roofing", "lighting", "flooring", "doors and hardware", "fire suppression"],
    "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression", "switchgear"],
}


def valid_state_codes() -> set[str]:
    return {p.stem.upper() for p in STATES_DIR.glob("*.json")}


def download_csv(dest: Path) -> None:
    req = urllib.request.Request(BULK_URL, headers={"User-Agent": "Mozilla/5.0 (SpecIndex research)"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)


def to_project(row: dict, state: str) -> dict:
    notice_id = row["NoticeId"]
    naics = row.get("NaicsCode", "")
    project_type = NAICS_CODES.get(naics, "commercial")
    notice_type = row.get("Type", "")
    slug = slugify(row.get("Title", "untitled"))[:50]
    city = (row.get("PopCity") or "").strip()
    posted = (row.get("PostedDate") or "")[:10]
    deadline = (row.get("ResponseDeadLine") or "")[:10]

    desc_parts = [
        f"Federal {notice_type.lower()} {row.get('Sol#', '')}".strip(),
        row.get("Title", ""),
    ]
    if deadline:
        desc_parts.append(f"Response deadline {deadline}")
    description = ". ".join(p.rstrip(".") for p in desc_parts if p) + "."

    key_specs = [f"NAICS {naics}", f"Notice type: {notice_type}"]
    if row.get("SetASide"):
        key_specs.append(row["SetASide"])
    if row.get("ClassificationCode"):
        key_specs.append(f"Classification code {row['ClassificationCode']}")

    status = STATUS_BY_TYPE.get(notice_type, "planning")

    return {
        "id": f"{state.lower()}-sam-{notice_id[:16]}-{slug}",
        "name": (row.get("Title") or "Untitled")[:120],
        "city": city,
        "county": "",
        "status": status,
        "project_type": project_type,
        "estimated_value_usd": None,
        "square_footage": None,
        "owner": (row.get("Department/Ind.Agency") or "").title(),
        "architect": "",
        "general_contractor": (row.get("Awardee") or "").title() if row.get("Awardee") else "",
        "opened_or_announced_date": posted or None,
        "description": description[:900],
        "key_specs": key_specs,
        "mentioned_brands": [],
        "competitor_watch": COMPETITOR_WATCH_DEFAULT.get(project_type, ["hvac", "roofing", "lighting", "concrete"]),
        "sources": [
            {
                "title": f"SAM.gov {notice_type} {row.get('Sol#', notice_id)}",
                "url": row.get("Link", ""),
            }
        ],
        "open_for": (
            "Federal solicitation, bid package open. Product substitution requests may still be "
            "possible before award -- note: no attachment links in the bulk extract, check the "
            "notice page directly for spec/drawing documents."
            if notice_type in {"Solicitation", "Combined Synopsis/Solicitation"}
            else "Presolicitation/sources-sought notice -- spec window not yet finalized, "
            "earliest point to reach the design team."
        ),
        "state": state,
    }


def merge_into_state_file(state: str, new_projects: list[dict]) -> tuple[int, int]:
    """Append new_projects into data/states/{state}.json, deduping by id.
    Returns (added, skipped_existing)."""
    path = STATES_DIR / f"{state.lower()}.json"
    data = json.loads(path.read_text()) if path.exists() else {
        "state": state,
        "generated_at": date.today().isoformat(),
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
    data["generated_at"] = date.today().isoformat()
    if "sam-gov-bulk" not in (data.get("capture_method") or ""):
        data["capture_method"] = (data.get("capture_method") or "").rstrip(". ")
        data["capture_method"] = (
            f"{data['capture_method']}, SAM.gov federal solicitations (bulk CSV extract)"
            if data["capture_method"]
            else "SAM.gov federal solicitations (bulk CSV extract)"
        )

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-path", help="Use an already-downloaded CSV instead of fetching fresh")
    ap.add_argument("--states", help="Comma-separated state codes to limit to (default: all with a data/states/ file)")
    ap.add_argument(
        "--exclude-states",
        default="GA",
        help=(
            "Comma-separated state codes to skip (default: GA). GA has its own "
            "rebuild-ga-corpus.py pipeline that rebuilds data/states/ga.json from "
            "raw/ sources only -- merging this script's output directly into "
            "ga.json would get silently erased the next time rebuild-ga-corpus.py "
            "runs. Use scripts/pull-sam-gov-bulk-ga.py instead, which writes to "
            "data/raw/ where rebuild-ga-corpus.py actually looks. Pass '' to "
            "disable this exclusion."
        ),
    )
    args = ap.parse_args()

    if args.csv_path:
        csv_path = Path(args.csv_path)
    else:
        csv_path = ROOT / "data" / "raw" / ".sam-gov-bulk-download.csv"
        print(f"Downloading {BULK_URL} -> {csv_path} (~230MB, no auth)...", file=sys.stderr)
        download_csv(csv_path)
        print(f"Downloaded {csv_path.stat().st_size:,} bytes", file=sys.stderr)

    valid_states = valid_state_codes()
    target_states = (
        {s.strip().upper() for s in args.states.split(",")} if args.states else valid_states
    )
    exclude_states = (
        {s.strip().upper() for s in args.exclude_states.split(",") if s.strip()}
        if args.exclude_states
        else set()
    )
    target_states -= exclude_states
    target_states &= valid_states

    csv.field_size_limit(10_000_000)
    by_state: dict[str, list[dict]] = {}
    with open(csv_path, encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row.get("PopState")
            if state not in target_states:
                continue
            if row.get("NaicsCode") not in NAICS_CODES:
                continue
            by_state.setdefault(state, []).append(to_project(row, state))

    total_added = 0
    for state in sorted(by_state):
        added, skipped = merge_into_state_file(state, by_state[state])
        total_added += added
        print(f"{state}: +{added} new (skipped {skipped} already present)")

    no_data_states = target_states - set(by_state)
    if no_data_states:
        print(f"No matching opportunities for: {', '.join(sorted(no_data_states))}", file=sys.stderr)

    print(f"\nTotal new projects added across {len(by_state)} states: {total_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
