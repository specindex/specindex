"""Accela Citizen Access ingestion provider (Playwright-based).

Accela's public "General Search" form has no date-range filter for
anonymous users (see docs/ROADMAP.md item 62 -- a logged-in account may
unlock one), but results come back sorted newest-first, which is enough
for a real incremental strategy: paginate from page 1 and stop as soon as
a row's date falls at/before the watermark, instead of needing an
explicit date filter.

Verified live 2026-07-28 against Gwinnett County
(aca-prod.accela.com/GWINNETT): searching permit_type="Building" returns
genuinely commercial permits (Gwinnett's own system prefixes them
COMBLD-, COMmercial-BuiLDing), with a clean, consistent results table --
Date/Permit Number/Permit Type/Project Name/Status/Short Notes/Address.
That table structure is deterministic enough to parse directly; no
Flash/Sonnet involved, same reasoning as sam_gov_provider.py /
usaspending_provider.py (real Node 1 fetch, not messy free text).

One real constraint: this is browser automation against a live
citizen-facing site, not a documented API -- the DOM element IDs
(#ctl00_PlaceHolderMain_...) are ASP.NET auto-generated and specific to
this exact Accela deployment/version. A different county's Accela
instance (even same vendor) may need different selectors; verify live
before assuming this class works unmodified elsewhere.
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields


class AccelaProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        state_code: str,
        county: str,
        base_url: str,
        permit_type_label: str = "Building",
        lookback_days: int = 30,
        max_pages: int = 30,
        headless: bool = True,
    ) -> None:
        self.state_code = state_code.upper()
        self.county = county
        self.base_url = base_url.rstrip("/")
        self.permit_type_label = permit_type_label
        self.lookback_days = lookback_days
        self.max_pages = max_pages
        self.headless = headless

    def _cutoff_date(self, last_watermark: str) -> date:
        if last_watermark and last_watermark not in ("0", ""):
            try:
                return datetime.strptime(last_watermark, "%m/%d/%Y").date()
            except ValueError:
                pass
        return date.today() - timedelta(days=self.lookback_days)

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        cutoff = self._cutoff_date(last_watermark)
        print(f"[accela:{self.county}] cutoff={cutoff.isoformat()} (watermark={last_watermark!r})", file=sys.stderr)

        rows_out: list[dict[str, Any]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page(user_agent="Mozilla/5.0 SpecIndex-StateAgent/0.2")
            try:
                page.goto(
                    f"{self.base_url}/Cap/CapHome.aspx?module=Building",
                    timeout=30000,
                    wait_until="networkidle",
                )
                page.select_option(
                    "#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType",
                    label=self.permit_type_label,
                )
                page.click("#ctl00_PlaceHolderMain_btnNewSearch")
                page.wait_for_load_state("networkidle", timeout=25000)

                stop = False
                for page_num in range(1, self.max_pages + 1):
                    trs = page.eval_on_selector_all(
                        "#ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList tr",
                        "trs => trs.map(tr => Array.from(tr.querySelectorAll('td,th'))"
                        ".map(td => td.innerText.trim()))",
                    )
                    data_rows = [
                        r for r in trs
                        if len(r) >= 9 and re.match(r"\d{2}/\d{2}/\d{4}", r[1] or "")
                    ]
                    if not data_rows and page_num == 1:
                        print(f"[accela:{self.county}] no results table found on page 1", file=sys.stderr)
                        break

                    for r in data_rows:
                        row_date = datetime.strptime(r[1], "%m/%d/%Y").date()
                        if row_date <= cutoff:
                            stop = True
                            break
                        rows_out.append(
                            {
                                "date": r[1],
                                "permit_number": r[2],
                                "permit_type": r[3],
                                "project_name": r[4],
                                "status": r[5],
                                "short_notes": r[7],
                                "address_raw": r[8] if len(r) > 8 else "",
                                "county": self.county,
                            }
                        )
                    print(f"[accela:{self.county}] page {page_num}: {len(data_rows)} rows, {len(rows_out)} kept so far", file=sys.stderr)
                    if stop:
                        break

                    next_link = page.query_selector("a:has-text('Next >')")
                    if not next_link:
                        break
                    next_link.click()
                    page.wait_for_load_state("networkidle", timeout=25000)
                    time.sleep(0.5)
            finally:
                browser.close()

        print(f"[accela:{self.county}] fetched {len(rows_out)} rows", file=sys.stderr)
        return rows_out

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        return hash_fields(row, ["permit_number"])

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        dates = [r["date"] for r in rows if r.get("date")]
        if not dates:
            return current
        parsed = [datetime.strptime(d, "%m/%d/%Y").date() for d in dates]
        best = max(parsed)
        best_str = best.strftime("%m/%d/%Y")
        if current and current not in ("0", ""):
            try:
                cur_date = datetime.strptime(current, "%m/%d/%Y").date()
                return best_str if best > cur_date else current
            except ValueError:
                pass
        return best_str

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from project_identity import slugify

        out = []
        for r in rows:
            addr = r.get("address_raw") or ""
            # "1008 INDUSTRIAL CT, SUWANEE GA 30024" -> city/zip split
            city, zip_code = "", ""
            m = re.search(r",\s*([A-Za-z .]+?)\s+[A-Z]{2}\s+(\d{5})\s*$", addr)
            if m:
                city, zip_code = m.group(1).strip(), m.group(2)

            permit_no = r["permit_number"]
            uid = slugify(f"{self.county}-{permit_no}")
            out.append(
                {
                    "id": f"{self.state_code.lower()}-{self.county.lower().replace(' ', '')}-accela-{uid}"[:80],
                    "name": (r.get("project_name") or permit_no)[:120],
                    "city": city,
                    "county": self.county,
                    "status": "permitting",
                    "project_type": "commercial",
                    "estimated_value_usd": None,
                    "square_footage": None,
                    "owner": "",
                    "architect": "",
                    "general_contractor": "",
                    "opened_or_announced_date": r.get("date", "").replace("/", "-") if r.get("date") else None,
                    "description": (r.get("short_notes") or r.get("project_name") or "Commercial building permit.")[:900],
                    "key_specs": [f"Permit type: {r.get('permit_type')}", f"Status: {r.get('status')}"],
                    "mentioned_brands": [],
                    "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression"],
                    "sources": [
                        {
                            "title": f"{self.county} County Accela permit {permit_no}",
                            "url": f"{self.base_url}/Cap/CapHome.aspx?module=Building",
                        }
                    ],
                    "open_for": "Active commercial building permit application. Early product/spec window.",
                    "state": self.state_code,
                    "zip": zip_code,
                }
            )
        return out
