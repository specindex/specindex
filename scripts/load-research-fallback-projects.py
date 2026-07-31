#!/usr/bin/env python3
"""Load step 6 research-fallback findings into the production corpus.

Closes step 6c's remaining gap (see docs/AGENT_STRATEGY.md Phase II
step 6c and docs/PIPELINE_REVIEW_2026-07-31.md) -- everything found by
research-county-sources.py-style grounded search + independent
cross-check has, until now, only ever landed in data/raw/*.json,
verified but never loaded into `projects`.

SAFETY RULE (not optional, matches this project's whole discipline):
by default, only loads projects with "cross_checked": true AND a
cross_check_result that starts with "CONFIRMED" -- an unconfirmed or
merely-claimed fact from a single grounded search call does not meet
the bar every other source in this corpus meets. Use
--include-unverified to override, but that should be a deliberate,
named exception, not the default.

project_id convention: "{state}-{county}-research-{slug}" (e.g.
"il-mclean-research-rivian-automotive-supplier-park-plant-expansion")
-- the "research" token keeps these visibly distinct from structured-
source project_ids (e.g. "il-cook-...") in project_identity.py's
classify_source(), which falls through to the local-source label path
for any unrecognized second token, so these correctly show up as a
local (non-broad) source, not a national one.

Two-step pipeline, matching load-corpus-to-postgres.py's own expected
input shape ({"generated_at": ..., "projects": [...]}):
  1. This script reads one or more data/raw/*-research-fallback*.json
     files and writes a single combined corpus-shaped JSON file.
  2. load-corpus-to-postgres.py loads that file the normal way (same
     upsert-by-project_id path every other source uses).

Usage:
  python3 scripts/load-research-fallback-projects.py \
      --input data/raw/il-mclean-research-fallback.json \
      --input data/raw/il-kendall-research-fallback.json \
      --output data/raw/il-research-fallback-corpus.json
  python3 scripts/load-corpus-to-postgres.py \
      --corpus data/raw/il-research-fallback-corpus.json --apply-migrations
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

STATE_CODE_FROM_NAME = {
    "illinois": "IL",
}

STATUS_MAP = {
    "completed": "completed",
    "completed / active operations": "completed",
    "under construction": "under_construction",
    "permitted": "permitting",
    "proposed": "planning",
    "planning": "planning",
    "planned": "planning",
    "cancelled": "cancelled",
    "withdrawn": "cancelled",
}

COST_RE = re.compile(r"\$?([\d,.]+)\s*(million|billion|m\b|b\b|k\b)?", re.IGNORECASE)
SF_RE = re.compile(r"([\d,]{4,})\s*sf\b", re.IGNORECASE)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "untitled"


def normalize_status(raw: str | None) -> str:
    if not raw:
        return "planning"
    low = raw.lower()
    for key, val in STATUS_MAP.items():
        if key in low:
            return val
    return "planning"


def parse_cost(raw: str | None) -> int | None:
    if not raw:
        return None
    low = raw.lower()
    if "not identified" in low:
        return None
    m = COST_RE.search(raw)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").lower()
    if unit.startswith("b"):
        num *= 1_000_000_000
    elif unit.startswith("m"):
        num *= 1_000_000
    elif unit.startswith("k"):
        num *= 1_000
    return int(num)


def parse_sf(raw: str | None) -> int | None:
    if not raw:
        return None
    m = SF_RE.search(raw.replace(",", ""))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def is_verified(project: dict[str, Any], include_unverified: bool) -> bool:
    if include_unverified:
        return True
    if not project.get("cross_checked"):
        return False
    result = (project.get("cross_check_result") or "").upper()
    return result.startswith("CONFIRMED")


def convert_project(project: dict[str, Any], county: str, state_code: str, county_slug: str, verified: bool) -> dict[str, Any]:
    slug = slugify(project["name"])
    project_id = f"{state_code.lower()}-{county_slug}-research-{slug}"

    sources: list[dict[str, str]] = []
    citation = project.get("source_citation")
    if citation:
        sources.append({"name": "Step 6 research fallback citation", "url": "", "note": citation})
    for doc in project.get("pullable_documents") or []:
        if doc.get("url"):
            sources.append({"name": doc.get("description", "Pullable document"), "url": doc["url"]})

    # PENDING_DEEP_AUDIT tag (2026-07-31, Asif: "we will do a deep audit
    # later") -- these rows skipped the per-project independent
    # cross-check pass to move faster. Not dropped, not treated as equal
    # to a confirmed row either -- tagged in both the description (so it
    # shows on the page itself) and sources (so it's a queryable marker,
    # not just prose) for a future audit pass to find and re-verify.
    audit_tag = "" if verified else " [PENDING DEEP AUDIT -- not independently cross-checked]"
    if not verified:
        sources.append({"name": "PENDING_DEEP_AUDIT", "url": "", "note": "Loaded without independent cross-check, per 2026-07-31 decision to move faster and audit later."})

    return {
        "id": project_id,
        "name": project["name"],
        "state": state_code,
        "city": project.get("city_address", "").split(",")[0] if project.get("city_address") else "",
        "county": county,
        "status": normalize_status(project.get("status")),
        "project_type": project.get("project_type") or "other",
        "estimated_value_usd": parse_cost(project.get("estimated_cost")),
        "square_footage": parse_sf(project.get("square_footage_or_acreage")),
        "owner": project.get("developer_owner") or "",
        "architect": project.get("architect") or "",
        "general_contractor": project.get("general_contractor") or "",
        "opened_or_announced_date": None,
        "description": (
            f"{project.get('project_type', 'Commercial')} project found via Step 6 direct research "
            f"(grounded search{'  + independent cross-check' if verified else ', NOT independently cross-checked'}, "
            f"not a structured permit feed).{audit_tag} "
            f"Key tenants: {project.get('key_tenants') or 'not identified'}. "
            f"Expected completion: {project.get('expected_completion') or 'not identified'}."
        ),
        "key_specs": [],
        "mentioned_brands": [],
        "competitor_watch": [],
        "sources": sources,
        "open_for": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", action="append", required=True, help="A data/raw/*-research-fallback*.json file (repeatable)")
    parser.add_argument("--output", required=True, help="Combined corpus-shaped JSON file to write")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help=(
            "Load projects that were never independently cross-checked too, tagged "
            "PENDING_DEEP_AUDIT (both in the description and as a sources row) instead "
            "of excluded. Per Asif's 2026-07-31 'we will do a deep audit later' decision -- "
            "this is a deliberate speed/rigor tradeoff, not the default."
        ),
    )
    args = parser.parse_args(argv)

    all_projects: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    skipped_unverified = 0
    included_unverified = 0

    for input_path in args.input:
        findings = json.loads(Path(input_path).read_text())
        county = findings.get("county", "Unknown")
        state_code = STATE_CODE_FROM_NAME.get((findings.get("state") or "").lower(), findings.get("state") or "")
        county_slug = slugify(county)

        projects = findings.get("projects") or []
        if not projects and "new_projects_from_3yr_extension" in findings:
            projects = findings["new_projects_from_3yr_extension"]
        if not projects and "new_project_not_in_broader_pass" in findings:
            projects = [findings["new_project_not_in_broader_pass"]]

        for p in projects:
            verified = is_verified(p, include_unverified=False)
            if not verified and not args.include_unverified:
                skipped_unverified += 1
                print(f"  [skip, unverified] {p.get('name')} ({input_path})", file=sys.stderr)
                continue
            row = convert_project(p, county, state_code, county_slug, verified)
            if row["id"] in seen_ids:
                print(f"  [dedup, same id already added] {row['id']}", file=sys.stderr)
                continue
            seen_ids.add(row["id"])
            all_projects.append(row)
            if verified:
                print(f"  [included, confirmed] {row['id']}", file=sys.stderr)
            else:
                included_unverified += 1
                print(f"  [included, PENDING_DEEP_AUDIT] {row['id']}", file=sys.stderr)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projects": all_projects,
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n")

    print(
        json.dumps(
            {
                "inputs": args.input,
                "projects_included": len(all_projects),
                "projects_included_pending_audit": included_unverified,
                "projects_skipped_unverified": skipped_unverified,
                "output": args.output,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
