#!/usr/bin/env python3
"""Pull Georgia construction opportunities from SAM.gov's bulk CSV extract.

Supersedes the quota-limited approach in scripts/pull-sam-gov-ga.py. SAM.gov
publishes a public, no-auth, no-API-key CSV of every Contract Opportunity
nationwide, updated daily, at:

  https://s3.amazonaws.com/falextracts/Contract Opportunities/datagov/ContractOpportunitiesFullCSV.csv

Found 2026-07-25: 232MB, government-wide (~80k rows), no quota. The old
API-based script hit ~10 calls/day before throttling on a public key; this
file has no such limit since it's a static daily snapshot, not a live query.
One real gap vs. the API: this CSV has no per-notice attachment/resourceLinks
field, only the notice page URL -- spec/drawing PDFs (if any) would need a
follow-up fetch of that page, not done here.

Usage:
    python3 scripts/pull-sam-gov-bulk-ga.py [--csv-path FILE] [--out FILE]
"""

from __future__ import annotations

import argparse
import csv
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import assign_unique_ids, slugify  # noqa: E402

BULK_URL = "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv"

# Matches scripts/pull-sam-gov-ga.py -- building construction only, excludes
# highway/civil codes (not building-envelope/MEP spec opportunities).
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


def download_csv(dest: Path) -> None:
    req = urllib.request.Request(BULK_URL, headers={"User-Agent": "Mozilla/5.0 (SpecIndex research)"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)


def to_project(row: dict) -> dict:
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

    return {
        "id": f"ga-sam-{notice_id[:16]}-{slug}",
        "name": (row.get("Title") or "Untitled")[:120],
        "city": city,
        "county": "",
        "status": STATUS_BY_TYPE.get(notice_type, "planning"),
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
        "state": "GA",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-path", help="Use an already-downloaded CSV instead of fetching fresh")
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "sam-gov-bulk-ga-construction.json"))
    args = ap.parse_args()

    if args.csv_path:
        csv_path = Path(args.csv_path)
    else:
        csv_path = ROOT / "data" / "raw" / ".sam-gov-bulk-download.csv"
        print(f"Downloading {BULK_URL} -> {csv_path} (~230MB, no auth)...", file=sys.stderr)
        download_csv(csv_path)
        print(f"Downloaded {csv_path.stat().st_size:,} bytes", file=sys.stderr)

    csv.field_size_limit(10_000_000)
    projects = []
    # SAM.gov's export is cp1252, not UTF-8 (confirmed 2026-07-25 -- utf-8
    # decoding fails outright on byte 0xb7; cp1252 decodes cleanly). Using
    # utf-8 with errors="replace" "works" but silently mangles em-dashes
    # etc. into U+FFFD in every title/description.
    with open(csv_path, encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("PopState") != "GA":
                continue
            if row.get("NaicsCode") not in NAICS_CODES:
                continue
            projects.append(to_project(row))

    projects = assign_unique_ids(projects, "GA")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(__import__("json").dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(projects)} projects to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
