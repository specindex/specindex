#!/usr/bin/env python3
"""Create or refresh docs/states/{code}.md playbooks from data/states/*.json.

Preserves manual sections outside AUTO blocks. Run after corpus changes or data pulls.

Usage:
    python3 scripts/sync-state-playbooks.py
    python3 scripts/sync-state-playbooks.py --state ga
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES_DIR = ROOT / "data" / "states"
PLAYBOOKS_DIR = ROOT / "docs" / "states"
RULES_DIR = ROOT / ".cursor" / "rules"

STATE_NAMES = {
    "ak": "Alaska",
    "al": "Alabama",
    "ar": "Arkansas",
    "az": "Arizona",
    "ca": "California",
    "co": "Colorado",
    "ct": "Connecticut",
    "de": "Delaware",
    "fl": "Florida",
    "ga": "Georgia",
    "hi": "Hawaii",
    "ia": "Iowa",
    "id": "Idaho",
    "il": "Illinois",
    "in": "Indiana",
    "ks": "Kansas",
    "ky": "Kentucky",
    "la": "Louisiana",
    "ma": "Massachusetts",
    "md": "Maryland",
    "me": "Maine",
    "mi": "Michigan",
    "mn": "Minnesota",
    "mo": "Missouri",
    "ms": "Mississippi",
    "mt": "Montana",
    "nc": "North Carolina",
    "nd": "North Dakota",
    "ne": "Nebraska",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "nm": "New Mexico",
    "nv": "Nevada",
    "ny": "New York",
    "oh": "Ohio",
    "ok": "Oklahoma",
    "or": "Oregon",
    "pa": "Pennsylvania",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "sd": "South Dakota",
    "tn": "Tennessee",
    "tx": "Texas",
    "ut": "Utah",
    "va": "Virginia",
    "vt": "Vermont",
    "wa": "Washington",
    "wi": "Wisconsin",
    "wv": "West Virginia",
    "wy": "Wyoming",
}


def load_state(path: Path) -> dict:
    data = json.loads(path.read_text())
    code = path.stem.lower()
    projects = data.get("projects") or []
    counties = {p.get("county") for p in projects if p.get("county")}
    cities = {p.get("city") for p in projects if p.get("city")}
    statuses = Counter(p.get("status") or "unknown" for p in projects)
    return {
        "code": code,
        "state": (data.get("state") or code.upper()).upper(),
        "state_name": data.get("state_name") or STATE_NAMES.get(code, code.upper()),
        "generated_at": data.get("generated_at") or "unknown",
        "date_range": data.get("date_range") or "Not recorded",
        "capture_method": data.get("capture_method") or "Web research",
        "project_count": len(projects),
        "county_count": len(counties),
        "city_count": len(cities),
        "status_breakdown": ", ".join(f"{k} {v}" for k, v in statuses.most_common(5)),
    }


def auto_header(meta: dict) -> str:
    return f"""<!-- AUTO:HEADER START -->
**State:** {meta["state"]} ({meta["state_name"]})  
**Corpus file:** `data/states/{meta["code"]}.json`  
**Last corpus update:** {meta["generated_at"]}  
**Projects in corpus:** {meta["project_count"]}  
**Counties:** {meta["county_count"]} · **Cities:** {meta["city_count"]}  
**Date range:** {meta["date_range"]}  
**Capture method:** {meta["capture_method"]}  
**Status mix:** {meta["status_breakdown"] or "none"}
<!-- AUTO:HEADER END -->"""


def stub_body(meta: dict) -> str:
    return f"""
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- Update after each pull with endpoints, scripts, and filters that produced clean records.

## What failed last time

- Update after each pull with dead links, wrong layers, residential noise, and dedupe traps.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers {meta["state_name"]}.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| {date.today().isoformat()} | Stub synced from corpus | {meta["project_count"]} projects |
"""


def replace_auto_block(text: str, marker: str, content: str) -> str:
    pattern = rf"<!-- AUTO:{marker} START -->.*?<!-- AUTO:{marker} END -->"
    block = content.strip()
    if re.search(pattern, text, flags=re.S):
        return re.sub(pattern, block, text, count=1, flags=re.S)
    return f"{block}\n\n{text}"


def write_playbook(meta: dict) -> None:
    PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    path = PLAYBOOKS_DIR / f"{meta['code']}.md"
    header = auto_header(meta)

    if path.exists():
        existing = path.read_text()
        body = replace_auto_block(existing, "HEADER", header)
    else:
        title = f"# {meta['state_name']} Commercial Source Playbook\n\n"
        intro = (
            f"Read this file before refreshing `data/states/{meta['code']}.json`. "
            "Keep it current so the next pull starts from what already worked.\n\n"
        )
        body = title + intro + header + stub_body(meta)

    path.write_text(body.rstrip() + "\n")


def write_cursor_rule(meta: dict) -> None:
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    code = meta["code"]
    name = meta["state_name"]
    path = RULES_DIR / f"state-{code}-commercial-pull.mdc"
    path.write_text(
        f"""---
description: {name} commercial project capture — read the playbook before any pull
globs: data/states/{code}.json,data/raw/{code}-*.json,scripts/pull-{code}*.py,docs/states/{code}.md
alwaysApply: false
---

# {name} Commercial Pulls

Before capturing or refreshing {name}, read **`docs/states/{code}.md`** in full.

After the pull, update that playbook:

1. **What works** and **What failed last time**
2. **Pull log** with date, source, and outcome
3. The AUTO header stats (run `python3 scripts/sync-state-playbooks.py --state {code}`)

Follow `.cursor/rules/state-data-pull-review.mdc` for the review checklist.
"""
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="Sync one state code (e.g. ga)")
    args = ap.parse_args()

    paths = sorted(STATES_DIR.glob("*.json"))
    if args.state:
        paths = [p for p in paths if p.stem.lower() == args.state.lower()]
        if not paths:
            raise SystemExit(f"No state file for {args.state}")

    for path in paths:
        meta = load_state(path)
        write_playbook(meta)
        write_cursor_rule(meta)
        print(f"Synced {meta['code']}: {meta['project_count']} projects → docs/states/{meta['code']}.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
