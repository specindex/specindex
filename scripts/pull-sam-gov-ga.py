#!/usr/bin/env python3
"""Pull Georgia construction opportunities from SAM.gov's Opportunities API.

SAM.gov is federal contracting data (courthouses, VA hospitals, Corps of
Engineers work, military base construction, GSA buildings) — a source the
existing corpus doesn't have at all, since the other GA pulls
(scripts/pull-ga-dri.py, pull-ga-accela-commercial.py, pull-ga-municipal-
commercial.py) only cover state/county/city permit and DRI data, not federal
solicitations.

Requires SAM_API_KEY in the environment (see .env). Public SAM.gov API keys
carry a low, undocumented daily quota until the key is linked to an active
SAM.gov entity registration — this script is written to be resumable across
multiple days of throttling rather than assuming one run completes the pull:
each (naics, date-window) request is checkpointed to --state-file as it
succeeds, so a re-run skips work already done and only issues the calls still
outstanding.

Usage:
    python3 scripts/pull-sam-gov-ga.py --years 2 [--limit N] [--out FILE]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import assign_unique_ids, slugify  # noqa: E402

API_BASE = "https://api.sam.gov/prod/opportunities/v2/search"

# NAICS codes relevant to building-product spec work. Excludes highway/civil
# codes (237310, 237990, etc.) since those aren't building-envelope/MEP spec
# opportunities for the manufacturers SpecIndex serves.
NAICS_CODES = {
    "236220": "commercial",  # Commercial and Institutional Building Construction
    "236210": "industrial",  # Industrial Building Construction
}

# Presolicitation (spec window still open) + Solicitation (active bid, spec
# package usually attached). Combined into one comma-separated call per SAM.gov
# v2 API support for multi-value ptype, to conserve daily quota.
PTYPE = "p,o"

COMPETITOR_WATCH_DEFAULT = {
    "commercial": ["glazing", "hvac", "roofing", "lighting", "flooring", "doors and hardware", "fire suppression"],
    "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression", "switchgear"],
}

STATUS_BY_TYPE = {
    "Presolicitation": "planning",
    "Solicitation": "bidding",
}


def api_get(params: dict) -> dict:
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from None


def date_windows(years: int) -> list[tuple[str, str]]:
    """Split the lookback into <=1-year windows (SAM.gov's documented cap)."""
    today = dt.date.today()
    windows = []
    end = today
    for _ in range(years):
        start = end - dt.timedelta(days=364)
        windows.append((start, end))
        end = start - dt.timedelta(days=1)
    return [(s.strftime("%m/%d/%Y"), e.strftime("%m/%d/%Y")) for s, e in reversed(windows)]


def load_state(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"done_windows": [], "notices": {}}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def to_project(notice: dict) -> dict:
    notice_id = notice["noticeId"]
    naics = notice.get("naicsCode", "")
    project_type = NAICS_CODES.get(naics, "commercial")
    notice_type = notice.get("type", "")
    slug = slugify(notice.get("title", "untitled"))[:50]

    pop = notice.get("placeOfPerformance") or {}
    city = ((pop.get("city") or {}).get("name") or "").strip()
    county = ((pop.get("county") or {}).get("name") or "") if isinstance(pop.get("county"), dict) else ""

    desc_parts = [
        f"Federal {notice_type.lower()} {notice.get('solicitationNumber', '')}".strip(),
        notice.get("title", ""),
    ]
    if notice.get("responseDeadLine"):
        desc_parts.append(f"Response deadline {notice['responseDeadLine'][:10]}")
    description = ". ".join(p.rstrip(".") for p in desc_parts if p) + "."

    key_specs = [f"NAICS {naics}", f"Notice type: {notice_type}"]
    if notice.get("typeOfSetAsideDescription"):
        key_specs.append(notice["typeOfSetAsideDescription"])
    if notice.get("classificationCode"):
        key_specs.append(f"Classification code {notice['classificationCode']}")

    sources = [
        {
            "title": f"SAM.gov {notice_type} {notice.get('solicitationNumber', notice_id)}",
            "url": notice.get("uiLink", ""),
        }
    ]
    for i, link in enumerate(notice.get("resourceLinks") or [], 1):
        sources.append({"title": f"Attachment {i} (spec/drawing package)", "url": link})

    return {
        "id": f"ga-sam-{notice_id[:16]}-{slug}",
        "name": notice.get("title", "Untitled")[:120],
        "city": city,
        "county": county,
        "status": STATUS_BY_TYPE.get(notice_type, "planning"),
        "project_type": project_type,
        "estimated_value_usd": None,
        "square_footage": None,
        "owner": notice.get("fullParentPathName", "").split(".")[0].title(),
        "architect": "",
        "general_contractor": "",
        "opened_or_announced_date": notice.get("postedDate"),
        "description": description,
        "key_specs": key_specs,
        "mentioned_brands": [],
        "competitor_watch": COMPETITOR_WATCH_DEFAULT.get(project_type, ["hvac", "roofing", "lighting", "concrete"]),
        "sources": sources,
        "open_for": (
            "Federal solicitation with spec/drawing attachments — bid package is open, "
            "product substitution requests may still be possible before award."
            if notice_type == "Solicitation"
            else "Presolicitation notice — spec window not yet finalized, earliest point to reach the design team."
        ),
        "state": "GA",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="cap total notices fetched, for testing")
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "sam-gov-ga-construction.json"))
    ap.add_argument("--state-file", default=str(ROOT / "data" / "raw" / ".sam-gov-ga-pull-state.json"))
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    api_key = os.environ.get("SAM_API_KEY", "")
    if not api_key:
        print("SAM_API_KEY not set (add it to .env and export it, or run: export SAM_API_KEY=...)", file=sys.stderr)
        return 1

    state = load_state(Path(args.state_file))
    windows = date_windows(args.years)

    for naics in NAICS_CODES:
        for posted_from, posted_to in windows:
            window_key = f"{naics}|{posted_from}|{posted_to}"
            if window_key in state["done_windows"]:
                print(f"skip (already done): {window_key}")
                continue

            offset = 0
            window_total = None
            try:
                while True:
                    params = {
                        "api_key": api_key,
                        "ncode": naics,
                        "ptype": PTYPE,
                        "postedFrom": posted_from,
                        "postedTo": posted_to,
                        "state": "GA",
                        "limit": args.page_size,
                        "offset": offset,
                    }
                    data = api_get(params)
                    window_total = data.get("totalRecords", 0)
                    batch = data.get("opportunitiesData", [])
                    for notice in batch:
                        state["notices"][notice["noticeId"]] = notice
                    print(
                        f"naics={naics} {posted_from}-{posted_to} offset={offset} "
                        f"got={len(batch)}/{window_total}"
                    )
                    offset += len(batch)
                    time.sleep(args.delay)
                    if not batch or offset >= window_total:
                        break
                    if args.limit and len(state["notices"]) >= args.limit:
                        break
                state["done_windows"].append(window_key)
                save_state(Path(args.state_file), state)
            except RuntimeError as exc:
                print(f"STOPPED on {window_key}: {exc}", file=sys.stderr)
                save_state(Path(args.state_file), state)
                print(
                    f"\nCheckpointed {len(state['notices'])} notices so far, "
                    f"{len(state['done_windows'])}/{len(NAICS_CODES) * len(windows)} windows done. "
                    "Re-run this script later (e.g. after the daily quota resets) to continue — "
                    "completed windows are skipped automatically."
                )
                return 2
            if args.limit and len(state["notices"]) >= args.limit:
                break

    projects = [to_project(n) for n in state["notices"].values()]
    projects, _ = (
        assign_unique_ids(projects, "GA"),
        None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(projects)} projects to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
