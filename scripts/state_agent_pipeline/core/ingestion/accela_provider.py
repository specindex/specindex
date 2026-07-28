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


# Header text -> canonical field name. Different Accela deployments show
# different column sets/orders (confirmed live 2026-07-28: Gwinnett's
# General Search/Short Notes vs El Paso's Action/Status/Building Number/
# Building Type/Description) -- parse by header text every time, never
# assume a fixed column index.
HEADER_ALIASES = {
    "date": "date",
    "permit number": "permit_number",
    "building number": "permit_number",
    "record number": "permit_number",
    "permit type": "permit_type",
    "building type": "permit_type",
    "record type": "permit_type",
    "project name": "project_name",
    "status": "status",
    "short notes": "description",
    "description": "description",
    "address": "address_raw",
}


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
        start_date_field_id: str | None = None,
        end_date_field_id: str | None = None,
    ) -> None:
        self.state_code = state_code.upper()
        self.county = county
        self.base_url = base_url.rstrip("/")
        self.permit_type_label = permit_type_label
        self.lookback_days = lookback_days
        self.max_pages = max_pages
        self.headless = headless
        # Some Accela deployments (El Paso) require Start/End Date to
        # return any results at all; others (Gwinnett) have no usable
        # date filter on the anonymous General Search form. Only filled
        # in if the config provides real field ids for this deployment.
        self.start_date_field_id = start_date_field_id
        self.end_date_field_id = end_date_field_id

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
                if self.start_date_field_id and self.end_date_field_id:
                    start = cutoff.strftime("%m/%d/%Y")
                    end = date.today().strftime("%m/%d/%Y")
                    page.fill(f"#{self.start_date_field_id}", start)
                    page.fill(f"#{self.end_date_field_id}", end)
                page.select_option(
                    "#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType",
                    label=self.permit_type_label,
                )
                page.click("#ctl00_PlaceHolderMain_btnNewSearch")
                page.wait_for_load_state("networkidle", timeout=25000)

                col_map: dict[int, str] | None = None
                stop = False
                for page_num in range(1, self.max_pages + 1):
                    trs = page.eval_on_selector_all(
                        "#ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList tr",
                        "trs => trs.map(tr => Array.from(tr.querySelectorAll('td,th'))"
                        ".map(td => td.innerText.trim()))",
                    )
                    if col_map is None:
                        col_map = self._build_column_map(trs)
                        if col_map is None:
                            print(f"[accela:{self.county}] no results table/header found on page 1", file=sys.stderr)
                            break
                        print(f"[accela:{self.county}] column map: {col_map}", file=sys.stderr)

                    date_idx = next((i for i, f in col_map.items() if f == "date"), None)
                    data_rows = [
                        r for r in trs
                        if date_idx is not None
                        and len(r) > date_idx
                        and re.match(r"\d{2}/\d{2}/\d{4}", r[date_idx] or "")
                    ]
                    if not data_rows and page_num == 1:
                        print(f"[accela:{self.county}] no data rows found on page 1", file=sys.stderr)
                        break

                    for r in data_rows:
                        row_date = datetime.strptime(r[date_idx], "%m/%d/%Y").date()
                        if row_date <= cutoff:
                            stop = True
                            break
                        parsed = {field: r[i] for i, field in col_map.items() if i < len(r)}
                        # Some deployments (COSA/San Antonio) have an
                        # explicit "Address" header, already captured
                        # above via col_map; others (Gwinnett/El Paso)
                        # leave it blank but consistently put it in the
                        # last cell -- only fall back to that guess if the
                        # header-based map didn't already find it.
                        if "address_raw" not in parsed:
                            parsed["address_raw"] = r[-1] if r else ""
                        parsed["county"] = self.county
                        rows_out.append(parsed)
                    print(f"[accela:{self.county}] page {page_num}: {len(data_rows)} rows, {len(rows_out)} kept so far", file=sys.stderr)
                    if stop:
                        break

                    next_link = page.locator("a:has-text('Next >')").first
                    if next_link.count() == 0:
                        break
                    # locator.click() auto-waits/re-queries internally,
                    # unlike query_selector().click() -- confirmed live
                    # 2026-07-28 that the latter throws "element is not
                    # attached to the DOM" on this exact ASP.NET postback
                    # pattern (the grid re-renders between select and click).
                    next_link.click()
                    page.wait_for_load_state("networkidle", timeout=25000)
                    time.sleep(0.5)
            finally:
                browser.close()

        print(f"[accela:{self.county}] fetched {len(rows_out)} rows", file=sys.stderr)
        return rows_out

    @staticmethod
    def _build_column_map(trs: list[list[str]]) -> dict[int, str] | None:
        """Find the header row (matches >=2 known column names) and map
        column index -> canonical field name, so row parsing never
        depends on a fixed position that might differ between Accela
        deployments."""
        for row in trs:
            lowered = [c.strip().lower() for c in row]
            hits = {i: HEADER_ALIASES[c] for i, c in enumerate(lowered) if c in HEADER_ALIASES}
            if len(hits) >= 2:
                return hits
        return None

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
            # "1008 INDUSTRIAL CT, SUWANEE GA 30024" (Gwinnett),
            # "7006 COMMERCE AVE, 0, EL PASO TX 79915 United States"
            # (El Paso, trailing country + inline unit-number segment), or
            # "4849 ROOSEVELT AVE City of San Antonio, TX 78214" (COSA --
            # city sits BEFORE the comma here, not after) -- try the
            # comma-then-city pattern first, fall back to "City of X,".
            addr = re.sub(r"\s+United States\s*$", "", r.get("address_raw") or "")
            city, zip_code = "", ""
            m = re.search(r",\s*([A-Za-z .]+?)\s+[A-Z]{2}\s+(\d{5})\s*$", addr)
            if m:
                city, zip_code = m.group(1).strip(), m.group(2)
            else:
                m2 = re.search(r"City of ([A-Za-z .]+?),\s*[A-Z]{2}\s+(\d{5})", addr)
                if m2:
                    city, zip_code = m2.group(1).strip(), m2.group(2)

            permit_no = r.get("permit_number") or ""
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
                    "description": (r.get("description") or r.get("project_name") or "Commercial building permit.")[:900],
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
