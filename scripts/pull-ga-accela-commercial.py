#!/usr/bin/env python3
"""Pull commercial permits from Georgia Accela Citizen Access portals.

Canonical reference: docs/states/ga.md

Agencies:
  - Atlanta (ATLANTA_GA) Building module
  - Gwinnett (GWINNETT) Development + Building modules
  - Cobb (CitizenAccess) Permits module

Accela caps HTML search results at 10 rows per page and 100+ total. This script
works around that by splitting date windows until each query returns every row.

Usage:
    python3 scripts/pull-ga-accela-commercial.py --months 12
    python3 scripts/pull-ga-accela-commercial.py --months 12 --agency atlanta
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "ga-accela-commercial.json"
UA = {"User-Agent": "Mozilla/5.0 (SpecIndex research; +https://specindex.ai)"}

RESIDENTIAL = re.compile(
    r"\b(single[- ]family|townhome|townhouse|subdivision|duplex|triplex|"
    r"condo|dwelling|residential|apartment building|unit apartment)\b",
    re.I,
)
COMMERCIAL_TYPE = re.compile(
    r"commercial|industrial|office|retail|hotel|mixed|hospitality|warehouse|medical|lodging",
    re.I,
)
PRIMARY_TYPES = re.compile(
    r"commercial new|commercial addition|commercial alteration|commercial land development|"
    r"commercial express|commercial industrial|commercial retail|mixed use|commercial office|"
    r"commercial(?!\s*-)",
    re.I,
)

AGENCIES = [
    {
        "id": "atlanta",
        "host": "https://aca-prod.accela.com",
        "path": "/ATLANTA_GA/Cap/CapHome.aspx?module=Building&TabName=Building",
        "county": "Fulton",
        "default_city": "Atlanta",
    },
    {
        "id": "gwinnett",
        "host": "https://aca-prod.accela.com",
        "path": "/GWINNETT/Cap/CapHome.aspx?module=Building&TabName=Building",
        "county": "Gwinnett",
        "default_city": "Lawrenceville",
    },
    {
        "id": "cobb",
        "host": "https://cobbca.cobbcounty.gov",
        "path": "/CitizenAccess/Cap/CapHome.aspx?module=Permits&TabName=Permits",
        "county": "Cobb",
        "default_city": "Marietta",
    },
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:52] or "project"


def parse_form(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in re.finditer(r"<input[^>]+>", html, re.I):
        tag = m.group(0)
        name_m = re.search(r'name="([^"]+)"', tag)
        if not name_m:
            continue
        name = name_m.group(1)
        typ_m = re.search(r'type="([^"]+)"', tag, re.I)
        typ = typ_m.group(1).lower() if typ_m else "text"
        if typ in ("hidden", "text", "checkbox", "radio"):
            val_m = re.search(r'value="([^"]*)"', tag)
            fields[name] = val_m.group(1) if val_m else ""
    for sm in re.finditer(
        r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S | re.I
    ):
        name = sm.group(1)
        opts = re.findall(r"<option([^>]*)value=\"([^\"]*)\"[^>]*>([^<]*)", sm.group(2), re.I)
        chosen = opts[0][1] if opts else ""
        for attr, val, _text in opts:
            if "selected" in attr.lower():
                chosen = val
                break
        fields[name] = chosen
    return fields


def commercial_permit_types(html: str, *, primary_only: bool) -> list[tuple[str, str]]:
    m = re.search(
        r'name="ctl00\$PlaceHolderMain\$generalSearchForm\$ddlGSPermitType"[^>]*>(.*?)</select>',
        html,
        re.S | re.I,
    )
    if not m:
        return []
    out: list[tuple[str, str]] = []
    for attr, val, text in re.findall(r"<option([^>]*)value=\"([^\"]*)\"[^>]*>([^<]*)", m.group(1), re.I):
        label = text.strip()
        if not val or label.startswith("--"):
            continue
        if COMMERCIAL_TYPE.search(label):
            if primary_only and not PRIMARY_TYPES.search(label):
                continue
            out.append((val, label))
    return out


def parse_showing_total(html: str) -> int | None:
    m = re.search(r"Showing\s+\d+\s*-\s*\d+\s+of\s+(\d+|100\+)", html, re.I)
    if not m:
        return None
    val = m.group(1)
    if val.endswith("+"):
        return 101
    return int(val)


def parse_records(html: str, agency_url_prefix: str) -> list[dict]:
    records: list[dict] = []
    for tr in re.findall(r'<tr[^>]*class="[^"]*ACA[^"]*"[^>]*>(.*?)</tr>', html, re.S | re.I):
        detail = re.search(r"CapDetail\.aspx\?([^\"']+)", tr)
        cells = [
            re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c)).strip())
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        ]
        cells = [c for c in cells if c]
        if len(cells) < 4:
            continue
        rec_no = ""
        for c in cells:
            if re.match(r"^[A-Z0-9]{2,}-", c):
                rec_no = c
                break
        if not rec_no:
            continue
        detail_url = ""
        if detail:
            detail_url = f"{agency_url_prefix}/Cap/CapDetail.aspx?{detail.group(1)}"
        records.append(
            {
                "record_number": rec_no,
                "cells": cells,
                "detail_url": detail_url,
            }
        )
    return records


class AccelaClient:
    def __init__(self, host: str, path: str) -> None:
        self.base = f"{host}{path}"
        self.host = host
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def _post(self, fields: dict[str, str], tries: int = 4) -> str:
        data = urllib.parse.urlencode(fields).encode()
        last_exc: Exception | None = None
        for attempt in range(tries):
            try:
                req = urllib.request.Request(
                    self.base,
                    data=data,
                    headers={
                        **UA,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": self.base,
                    },
                )
                return self.opener.open(req, timeout=90).read().decode("utf-8", "replace")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(2 * (attempt + 1))
        raise last_exc or RuntimeError("Accela POST failed")

    def _get(self, tries: int = 4) -> str:
        last_exc: Exception | None = None
        for attempt in range(tries):
            try:
                req = urllib.request.Request(self.base, headers=UA)
                return self.opener.open(req, timeout=60).read().decode("utf-8", "replace")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(2 * (attempt + 1))
        raise last_exc or RuntimeError("Accela GET failed")

    def search_window(self, permit_value: str, start: dt.date, end: dt.date) -> str:
        html = self._get()
        fields = parse_form(html)
        fields["__EVENTTARGET"] = "ctl00$PlaceHolderMain$generalSearchForm$ddlGSPermitType"
        fields["__EVENTARGUMENT"] = ""
        fields["ctl00$PlaceHolderMain$generalSearchForm$ddlGSPermitType"] = permit_value
        html2 = self._post(fields)

        fields2 = parse_form(html2)
        fields2["ctl00$PlaceHolderMain$generalSearchForm$ddlGSPermitType"] = permit_value
        fields2["ctl00$PlaceHolderMain$generalSearchForm$txtGSStartDate"] = start.strftime(
            "%m/%d/%Y"
        )
        fields2["ctl00$PlaceHolderMain$generalSearchForm$txtGSEndDate"] = end.strftime("%m/%d/%Y")
        fields2["__EVENTTARGET"] = "ctl00$PlaceHolderMain$btnNewSearch"
        fields2["__EVENTARGUMENT"] = ""
        return self._post(fields2)


def iter_windows(start: dt.date, end: dt.date, days: int = 7):
    cur = start
    while cur <= end:
        win_end = min(cur + dt.timedelta(days=days - 1), end)
        yield cur, win_end
        cur = win_end + dt.timedelta(days=1)


def collect_type(
    client: AccelaClient,
    agency_host: str,
    permit_value: str,
    permit_label: str,
    start: dt.date,
    end: dt.date,
    seen: set[str],
) -> list[dict]:
    out: list[dict] = []
    for win_start, win_end in iter_windows(start, end, days=7):
        html = client.search_window(permit_value, win_start, win_end)
        total = parse_showing_total(html)
        parsed = parse_records(html, agency_host)

        if total is not None and total > len(parsed):
            for d_start, d_end in iter_windows(win_start, win_end, days=1):
                day_html = client.search_window(permit_value, d_start, d_end)
                parsed.extend(parse_records(day_html, agency_host))

        for row in parsed:
            key = row["record_number"]
            if key in seen:
                continue
            seen.add(key)
            row["permit_type"] = permit_label
            out.append(row)
    return out


def parse_address(address: str) -> tuple[str, str, str]:
    address = (address or "").strip()
    city = ""
    zip_code = ""
    m = re.search(r",\s*([^,]+?)\s+([A-Z]{2})\s+(\d{5})", address)
    if m:
        city = m.group(1).strip()
        zip_code = m.group(3)
    return address, city, zip_code


def project_type_from(text: str) -> str:
    t = text.lower()
    if "data center" in t or "data centre" in t:
        return "data_center"
    if "hotel" in t or "hospitality" in t:
        return "hospitality"
    if "industrial" in t or "warehouse" in t:
        return "industrial"
    if "office" in t:
        return "office"
    if "retail" in t:
        return "retail"
    if "mixed" in t:
        return "mixed_use"
    if "medical" in t or "hospital" in t:
        return "healthcare"
    return "commercial"


def is_residential_record(row: dict) -> bool:
    blob = " ".join(
        [
            row.get("permit_type") or "",
            " ".join(row.get("cells") or []),
        ]
    )
    if RESIDENTIAL.search(blob):
        return True
    if re.search(r"\bapartment\b", blob, re.I) and not re.search(
        r"\b(commercial|mixed|office|retail)\b", blob, re.I
    ):
        return True
    return False


def row_to_project(row: dict, agency: dict) -> dict | None:
    if is_residential_record(row):
        return None

    cells = row.get("cells") or []
    opened = cells[0] if cells else None
    rec_no = row["record_number"]
    permit_type = row.get("permit_type") or (cells[2] if len(cells) > 2 else "Commercial")
    address = cells[3] if len(cells) > 3 else ""
    description = cells[4] if len(cells) > 4 else ""
    name = cells[5] if len(cells) > 5 else rec_no
    status = cells[6] if len(cells) > 6 else "permitting"

    address, city, _zip = parse_address(address)
    if not city:
        city = agency["default_city"]

    opened_date = None
    if opened and re.match(r"\d{2}/\d{2}/\d{4}", opened):
        try:
            opened_date = dt.datetime.strptime(opened, "%m/%d/%Y").date().isoformat()
        except ValueError:
            opened_date = None

    detail_url = row.get("detail_url") or ""
    sources = []
    if detail_url:
        sources.append(
            {
                "title": f"{agency['id']} Accela permit {rec_no}: {name[:80]}",
                "url": detail_url,
            }
        )
    else:
        sources.append(
            {
                "title": f"{agency['id']} Accela permit {rec_no}: {name[:80]}",
                "url": f"{agency['host']}{agency['path']}",
            }
        )

    ptype = project_type_from(f"{permit_type} {name} {description}")
    agency_slug = agency["id"].replace("-dev", "")

    return {
        "id": f"ga-{agency_slug}-{slugify(rec_no)}",
        "name": (name or rec_no)[:120],
        "city": city[:80],
        "county": agency["county"],
        "status": "permitting"
        if re.search(r"issue|approved|active|review", status, re.I)
        else "planning",
        "project_type": ptype,
        "estimated_value_usd": None,
        "square_footage": None,
        "owner": "",
        "architect": "",
        "general_contractor": "",
        "opened_or_announced_date": opened_date,
        "description": (
            f"{agency['id']} Accela {permit_type} permit {rec_no}. "
            f"{description or 'No description published.'} Address: {address or 'not listed'}."
        )[:900],
        "key_specs": [s for s in [permit_type, address, f"Permit {rec_no}"] if s],
        "mentioned_brands": [],
        "competitor_watch": ["hvac", "roofing", "lighting", "glazing", "fire suppression"],
        "sources": sources,
        "open_for": "Active commercial permit from Accela Citizen Access.",
        "state": "GA",
    }


def pull_agency(agency: dict, cutoff: dt.date, end: dt.date, *, primary_only: bool) -> list[dict]:
    client = AccelaClient(agency["host"], agency["path"])
    html = client._get()
    types = commercial_permit_types(html, primary_only=primary_only)
    if not types:
        print(f"  {agency['id']}: no commercial permit types found")
        return []

    seen: set[str] = set()
    projects: list[dict] = []
    print(f"  {agency['id']}: {len(types)} commercial permit types", flush=True)

    for permit_value, permit_label in types:
        print(f"    searching {permit_label[:45]}...", flush=True)
        rows = collect_type(
            client,
            agency["host"],
            permit_value,
            permit_label,
            cutoff,
            end,
            seen,
        )
        added = 0
        for row in rows:
            project = row_to_project(row, agency)
            if project:
                projects.append(project)
                added += 1
        if added:
            print(f"    {permit_label[:40]}: +{added} (running total {len(projects)})")
        time.sleep(0.3)

    return projects


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument(
        "--agency",
        choices=[a["id"] for a in AGENCIES] + ["all"],
        default="all",
    )
    ap.add_argument("--all-types", action="store_true", help="Pull every commercial-ish type (slow)")
    args = ap.parse_args()

    end = dt.date.today()
    cutoff = end - dt.timedelta(days=int(args.months * 30.44))
    print(f"Accela commercial pull, {cutoff} to {end}")

    agencies = AGENCIES
    if args.agency != "all":
        agencies = [a for a in AGENCIES if a["id"] == args.agency]

    primary_only = not args.all_types

    all_projects: list[dict] = []
    for agency in agencies:
        try:
            rows = pull_agency(agency, cutoff, end, primary_only=primary_only)
            all_projects.extend(rows)
            print(f"  {agency['id']} subtotal: {len(rows)}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {agency['id']} ERROR: {str(exc)[:120]}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"projects": all_projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_projects)} projects to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
