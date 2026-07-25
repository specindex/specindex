#!/usr/bin/env python3
"""Pull Georgia commercial projects from the state DRI database.

Canonical reference: docs/states/ga.md
Rule: .cursor/rules/georgia-commercial-pull.mdc

Georgia's Planning Act requires local governments to file a Development of
Regional Impact review for large projects, which makes apps.dca.ga.gov the only
statewide, structured, pre-construction source for Georgia commercial work. DRI
filings happen before construction starts, so these are projects where the
specification window is still open.

Residential is excluded: the Housing development type is dropped, and so are
withdrawn and terminated filings.

Usage:
    python3 scripts/pull-ga-dri.py --months 12 [--limit N] [--out FILE]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://apps.dca.ga.gov/DRI/"
UA = {"User-Agent": "Mozilla/5.0 (SpecIndex research; +https://specindex.ai)"}

# Development types that are not commercial construction for our purposes.
EXCLUDED_TYPES = {"housing"}
# Review outcomes that mean the project is not going forward.
EXCLUDED_STATUS = {"withdrawn", "terminated"}

# Product categories a building type will plausibly need. Keyed off the DRI
# development type, which is the only classification the state publishes.
CATEGORIES = {
    "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression", "switchgear", "insulation"],
    "technological facility (including data centers)": ["switchgear", "generators", "cooling", "ups", "fire suppression", "structured cabling", "concrete"],
    "mixed use": ["glazing", "hvac", "elevators", "roofing", "lighting", "flooring", "plumbing fixtures", "fire suppression"],
    "commercial": ["glazing", "hvac", "roofing", "lighting", "flooring", "doors and hardware", "fire suppression"],
    "office": ["glazing", "hvac", "elevators", "lighting", "flooring", "acoustic ceilings", "fire suppression"],
    "hotels": ["hvac", "elevators", "flooring", "plumbing fixtures", "lighting", "ff&e", "fire suppression"],
    "hospitals and health care facilities": ["hvac", "medical gas", "elevators", "flooring", "lighting", "fire suppression", "medical equipment"],
    "post-secondary schools": ["hvac", "roofing", "glazing", "lighting", "flooring", "fire suppression"],
    "wholesale & distribution": ["roofing", "dock equipment", "lighting", "concrete", "fire suppression", "hvac"],
    "intermodal terminals": ["paving", "concrete", "lighting", "site civil", "dock equipment"],
    "truck stops": ["paving", "concrete", "lighting", "plumbing fixtures", "roofing", "fuel systems"],
    "quarries, asphalt & cement plants": ["process equipment", "concrete", "site civil", "conveyors", "switchgear"],
    "attractions & recreational facilities": ["site civil", "lighting", "paving", "concrete", "roofing"],
    "solar power generation facility": ["switchgear", "trackers", "site civil", "transformer"],
    "waste handling facilities": ["process equipment", "concrete", "site civil", "switchgear"],
    "wastewater treatment facilities": ["process piping", "concrete", "switchgear", "site civil", "pumps"],
    "petroleum storage facilities": ["tank farm", "fire suppression", "concrete", "switchgear"],
    "airports": ["paving", "concrete", "lighting", "hvac", "glazing"],
    "water supply intakes/reservoirs": ["process piping", "concrete", "site civil", "switchgear"],
}

PROJECT_TYPE = {
    "industrial": "industrial",
    "technological facility (including data centers)": "data_center",
    "mixed use": "mixed_use",
    "commercial": "commercial",
    "office": "office",
    "hotels": "hospitality",
    "hospitals and health care facilities": "healthcare",
    "post-secondary schools": "education",
    "wholesale & distribution": "industrial",
    "intermodal terminals": "infrastructure",
    "truck stops": "retail",
    "quarries, asphalt & cement plants": "industrial",
    "attractions & recreational facilities": "recreation",
    "solar power generation facility": "energy",
    "waste handling facilities": "infrastructure",
    "wastewater treatment facilities": "infrastructure",
    "petroleum storage facilities": "industrial",
    "airports": "infrastructure",
    "water supply intakes/reservoirs": "infrastructure",
}


def fetch(url: str, tries: int = 3) -> str:
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            print(f"    retry {attempt + 1} for {url}: {str(exc)[:70]}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return ""


def visible_lines(raw: str) -> list[str]:
    t = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    return [x for x in (re.sub(r"\s+", " ", l).strip() for l in t.split("\n")) if x]


def parse_submissions(raw: str) -> list[dict]:
    """Read the submissions grid, pairing each row with its driid link."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, flags=re.S):
        m = re.search(r"AppSummary\.aspx\?driid=(\d+)", tr)
        if not m:
            continue
        cells = [
            re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        ]
        if len(cells) < 8:
            continue
        try:
            filed = dt.datetime.strptime(cells[6], "%m/%d/%Y").date()
        except ValueError:
            continue
        rows.append(
            {
                "driid": m.group(1),
                "project": cells[1],
                "dev_type": cells[2],
                "county": cells[3],
                "city": cells[4],
                "rdc": cells[5],
                "filed": filed,
                "status": cells[7],
            }
        )
    return rows


def field_after(lines: list[str], label: str, stop_at: tuple[str, ...] = ()) -> str:
    """Value that follows a label line, skipping ASP.NET's empty select markers."""
    for i, line in enumerate(lines):
        if line.rstrip(":").lower() != label.rstrip(":").lower():
            continue
        for nxt in lines[i + 1 : i + 4]:
            low = nxt.rstrip(":").lower()
            if low in ("(not selected)", "yes", "no"):
                continue
            if any(low.startswith(s.lower()) for s in stop_at):
                return ""
            if nxt.endswith(":"):
                return ""
            return nxt
        return ""
    return ""


SF_RE = re.compile(r"([\d,]{3,})\s*(?:sf|s\.f\.|square feet|sq\.? ?ft)", re.I)


def parse_sf(size_text: str) -> int | None:
    """Largest explicit square footage figure, or None. Never guesses."""
    best = None
    for m in SF_RE.finditer(size_text):
        try:
            v = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if v >= 1000 and (best is None or v > best):
            best = v
    return best


def scrape_detail(driid: str) -> dict:
    out = {}
    summary = visible_lines(fetch(f"{BASE}AppSummary.aspx?driid={driid}"))
    out["developer"] = field_after(summary, "Developer")
    out["dri_status"] = field_after(summary, "Current Status")

    form = visible_lines(fetch(f"{BASE}InitialForm.aspx?driid={driid}"))
    out["location"] = field_after(form, "Location (Street Address, GPS Coordinates, or Legal Land Lot Description)")
    out["description"] = field_after(form, "Brief Description of Project")
    out["size_text"] = field_after(form, "Project Size (# of units, floor area, acreage etc.)")
    if not out["developer"]:
        out["developer"] = field_after(form, "Developer")
    # Two "Estimated Project Completion Dates" values appear, phase then overall.
    out["completion"] = field_after(form, "This phase")
    return out


def to_project(row: dict, detail: dict) -> dict:
    dev_type = row["dev_type"].strip().lower()
    city = row["city"] if row["city"].lower() != "unincorporated" else f"{row['county']} County"
    slug = re.sub(r"[^a-z0-9]+", "-", row["project"].lower()).strip("-")[:52]

    desc_parts = []
    if detail.get("description"):
        desc_parts.append(detail["description"].rstrip("."))
    if detail.get("size_text"):
        desc_parts.append(f"Project size as filed: {detail['size_text'].rstrip('.')}")
    if detail.get("completion"):
        desc_parts.append(f"Estimated completion {detail['completion']}")
    desc_parts.append(
        f"Filed as Georgia DRI #{row['driid']} on {row['filed'].strftime('%B %d, %Y')}, "
        f"review status {detail.get('dri_status') or row['status']}"
    )

    key_specs = []
    if detail.get("size_text"):
        key_specs.append(detail["size_text"][:180])
    if detail.get("location"):
        key_specs.append(f"Site: {detail['location'][:150]}")

    return {
        "id": f"ga-dri-{row['driid']}-{slug}",
        "name": row["project"][:120],
        "city": city,
        "county": row["county"],
        "status": "planning",
        "project_type": PROJECT_TYPE.get(dev_type, "commercial"),
        "estimated_value_usd": None,
        "square_footage": parse_sf(detail.get("size_text") or ""),
        "owner": detail.get("developer") or "",
        "architect": "",
        "general_contractor": "",
        "opened_or_announced_date": row["filed"].isoformat(),
        "description": ". ".join(desc_parts) + ".",
        "key_specs": key_specs,
        "mentioned_brands": [],
        "competitor_watch": CATEGORIES.get(dev_type, ["hvac", "roofing", "lighting", "concrete"]),
        "sources": [
            {
                "title": f"Georgia DRI #{row['driid']} application summary, Department of Community Affairs",
                "url": f"{BASE}AppSummary.aspx?driid={row['driid']}",
            },
            {
                "title": f"Georgia DRI #{row['driid']} initial information form, filed by {row['city'] if row['city'].lower() != 'unincorporated' else row['county'] + ' County'}",
                "url": f"{BASE}InitialForm.aspx?driid={row['driid']}",
            },
        ],
        "open_for": (
            "Filed for regional review before construction, so product selections are "
            "not locked. Early design and specification window."
        ),
        "state": "GA",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "ga-dri-projects.json"))
    ap.add_argument("--delay", type=float, default=0.6)
    args = ap.parse_args()

    cutoff = dt.date.today() - dt.timedelta(days=int(args.months * 30.44))
    print(f"Fetching DRI submissions index, cutoff {cutoff}")
    rows = parse_submissions(fetch(f"{BASE}Submissions.aspx"))
    print(f"  parsed {len(rows)} total submissions")

    recent = [r for r in rows if r["filed"] >= cutoff]
    print(f"  {len(recent)} filed since {cutoff}")

    kept = [
        r
        for r in recent
        if r["dev_type"].strip().lower() not in EXCLUDED_TYPES
        and r["status"].strip().lower() not in EXCLUDED_STATUS
    ]
    dropped_res = sum(1 for r in recent if r["dev_type"].strip().lower() in EXCLUDED_TYPES)
    dropped_dead = sum(1 for r in recent if r["status"].strip().lower() in EXCLUDED_STATUS)
    print(f"  dropped {dropped_res} residential, {dropped_dead} withdrawn or terminated")
    print(f"  {len(kept)} commercial projects to detail")

    if args.limit:
        kept = kept[: args.limit]

    projects = []
    for i, row in enumerate(kept, 1):
        try:
            detail = scrape_detail(row["driid"])
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(kept)}] FAILED {row['driid']}: {str(exc)[:70]}")
            continue
        projects.append(to_project(row, detail))
        sf = projects[-1]["square_footage"]
        print(
            f"  [{i}/{len(kept)}] {row['driid']} {row['project'][:44]:46} "
            f"{row['county']:12} sf={sf if sf else '-'}"
        )
        time.sleep(args.delay)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(projects)} projects to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
