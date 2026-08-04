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
from .generic_mapping import _iso_date
from .hashing import hash_fields


# Header text -> canonical field name. Different Accela deployments show
# different column sets/orders (confirmed live 2026-07-28: Gwinnett's
# General Search/Short Notes vs El Paso's Action/Status/Building Number/
# Building Type/Description) -- parse by header text every time, never
# assume a fixed column index.
HEADER_ALIASES = {
    "date": "date",
    # Buncombe County NC (BUNCOMBECONC) uses "App Date" for the same
    # column -- confirmed live 2026-07-31, real 100+ commercial rows
    # were silently reported as 0 because date_idx never matched.
    "app date": "date",
    "permit number": "permit_number",
    # Cabarrus County NC (CABARRUS, module=Permits) uses "Permits Number"
    # (plural) for the same column -- confirmed live 2026-07-31. Without
    # this alias, permit_number never gets mapped, every row falls back
    # to the same synthetic hash, and 19 real distinct rows collapse to
    # 1 on merge (same failure class as the Indianapolis "Case Number"
    # bug documented above).
    "permits number": "permit_number",
    "building number": "permit_number",
    "record number": "permit_number",
    # Indianapolis's Accela deployment (IN-INDIANAPOLIS) uses "Case
    # Number" for the same column -- confirmed live 2026-07-29 via the
    # search form's own field label ("Case Number:"). Every row got the
    # identical fallback ID before this was added (permit_number was
    # never populated, so 326 real rows collapsed into 1 on merge --
    # caught and fixed same day, no bad data survived past the initial
    # test run).
    "case number": "permit_number",
    # Allen County/Fort Wayne, IN's ACFW deployment (Planning module,
    # used since Building/Permits modules are login-gated) uses
    # "Application Number" for the same column -- confirmed live
    # 2026-07-31. Without this alias every row falls back to an
    # identical id and 192 real rows collapse into 1 on merge, the same
    # failure mode documented above for Indianapolis's "Case Number".
    "application number": "permit_number",
    # Oklahoma City's deployment (OK-OKLAHOMA) uses the bare headers
    # "Number"/"Type"/"Application Name" instead of the longer
    # "Permit Number"/"Permit Type"/"Project Name" -- confirmed live
    # 2026-08-02 against aca-prod.accela.com/OKC (header row reads
    # Date | Number | Type | Application Name | Status | Address |
    # Action | Short Notes).
    "number": "permit_number",
    "permit type": "permit_type",
    "permits type": "permit_type",  # Cabarrus County NC plural header
    "type": "permit_type",
    "application name": "project_name",
    "building type": "permit_type",
    "record type": "permit_type",
    "application type": "permit_type",
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
        module: str = "Building",
        lookback_days: int = 30,
        max_pages: int = 30,
        # Days per search window. 90 keeps each search to a page count that
        # completes before ACA's loading mask starts intercepting clicks --
        # the failure that killed deep runs at page 37 and beyond.
        chunk_days: int = 90,
        headless: bool = True,
        start_date_field_id: str | None = None,
        end_date_field_id: str | None = None,
    ) -> None:
        self.state_code = state_code.upper()
        self.county = county
        self.base_url = base_url.rstrip("/")
        self.permit_type_label = permit_type_label
        # Most deployments call the building-permits module "Building",
        # but some (Lancaster, CA -- confirmed live: module=Building
        # 404s/errors, only module=Permits exists) name it differently.
        self.module = module
        self.lookback_days = lookback_days
        self.max_pages = max_pages
        self.chunk_days = max(1, chunk_days)
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

    def _date_chunks(self, cutoff: date) -> list[tuple[date, date]]:
        """Split [cutoff, today] into windows of `chunk_days`.

        Why chunk at all: paging deeper is NOT a substitute for a narrower
        search. Raising max_pages 60 -> 120 on 2026-08-04 looked like a win by
        fetched-row count (Pinellas 600 -> 1,164) but moved its in-window total
        not at all -- 1,044 of its 1,144 held rows are pre-2025, i.e. the extra
        pages reached further BACK in time, not further into the window. Two
        configs also broke at depth: Pima's pagination died at page 37 on an
        intercepted Next click, Salt Lake's loading mask detached the element.

        A short window returns few enough pages that the search completes
        before the UI gets flaky, and every page of it is in-window by
        construction. Chunking is only possible when the tenant exposes the
        date inputs; without them there is one unbounded search and nothing to
        split, so this returns a single window.
        """
        if not (self.start_date_field_id and self.end_date_field_id):
            return [(cutoff, date.today())]
        chunks: list[tuple[date, date]] = []
        start = cutoff
        today = date.today()
        while start <= today:
            end = min(start + timedelta(days=self.chunk_days - 1), today)
            chunks.append((start, end))
            start = end + timedelta(days=1)
        return chunks

    @staticmethod
    def _set_date(page: Any, field_id: str, value: date) -> str:
        """Set a masked ACA date input and return what actually landed in it.

        `page.fill()` is wrong here. These inputs carry a date mask and are
        often pre-populated, and fill() APPENDS rather than replaces --
        verified live 2026-08-04 on Pinellas, where filling "01/02/2025" into a
        field already holding "08/04/2024" produced "08/04/202401/02/2025".
        The portal treats an unparseable value as no filter at all and quietly
        returns the whole result set, so the search looks like it worked while
        being completely unfiltered.

        Setting .value directly and dispatching input+change bypasses the mask's
        keystroke handling while still notifying the ASP.NET validators. The
        resulting value is returned so the caller can verify rather than assume.
        """
        s = value.strftime("%m/%d/%Y")
        try:
            page.eval_on_selector(
                f"#{field_id}",
                """(el, v) => {
                    el.value = '';
                    el.value = v;
                    el.dispatchEvent(new Event('input',  {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('blur',   {bubbles: true}));
                }""",
                s,
            )
            return page.input_value(f"#{field_id}")
        except Exception as e:  # noqa: BLE001
            print(f"[accela] date set failed on #{field_id}: {str(e)[:60]}", file=sys.stderr)
            return ""

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        cutoff = self._cutoff_date(last_watermark)
        print(f"[accela:{self.county}] cutoff={cutoff.isoformat()} (watermark={last_watermark!r})", file=sys.stderr)

        chunks = self._date_chunks(cutoff)
        if len(chunks) > 1:
            print(
                f"[accela:{self.county}] searching in {len(chunks)} x {self.chunk_days}-day "
                f"windows (deep paging alone reaches older data, not more in-window data)",
                file=sys.stderr,
            )

        rows_out: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page(user_agent="Mozilla/5.0 SpecIndex-StateAgent/0.2")
            try:
                for chunk_i, (c_start, c_end) in enumerate(chunks, 1):
                    before_chunk = len(rows_out)
                    try:
                        self._search_window(page, c_start, c_end, cutoff, rows_out, seen_ids)
                    except Exception as e:  # noqa: BLE001
                        # One bad window must not discard the others. Losing a
                        # quarter is far better than losing the whole backfill,
                        # which is exactly what happened when a single click
                        # timeout killed a 60-page OKC run.
                        print(
                            f"[accela:{self.county}] window {c_start}..{c_end} failed "
                            f"({type(e).__name__}: {str(e)[:70]}) -- continuing",
                            file=sys.stderr,
                        )
                    if len(chunks) > 1:
                        print(
                            f"[accela:{self.county}] window {chunk_i}/{len(chunks)} "
                            f"{c_start}..{c_end}: +{len(rows_out) - before_chunk} "
                            f"({len(rows_out)} total)",
                            file=sys.stderr,
                        )
            finally:
                browser.close()
        print(f"[accela:{self.county}] fetched {len(rows_out)} rows", file=sys.stderr)
        return rows_out

    def _search_window(
        self,
        page: Any,
        window_start: date,
        window_end: date,
        cutoff: date,
        rows_out: list[dict[str, Any]],
        seen_ids: set[str],
    ) -> None:
        """Run one search over [window_start, window_end] and page through it."""
        if True:
            try:
                page.goto(
                    f"{self.base_url}/Cap/CapHome.aspx?module={self.module}",
                    timeout=30000,
                    wait_until="networkidle",
                )
                # ORDER MATTERS: select the permit type FIRST, then set dates.
                #
                # The permit-type <select> fires an ASP.NET postback that wipes
                # both date inputs. Filling dates first -- which this did until
                # 2026-08-04 -- means the search runs with EMPTY dates, i.e.
                # completely unfiltered, silently. Verified live on Pinellas:
                # three different 90-day windows returned byte-identical
                # results ("Showing 1-10 of 100", same Aug-2026 rows).
                page.select_option(
                    "#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType",
                    label=self.permit_type_label,
                )
                page.wait_for_load_state("networkidle", timeout=25000)
                page.wait_for_timeout(800)

                if self.start_date_field_id and self.end_date_field_id:
                    got_s = self._set_date(page, self.start_date_field_id, window_start)
                    got_e = self._set_date(page, self.end_date_field_id, window_end)
                    want_s = window_start.strftime("%m/%d/%Y")
                    want_e = window_end.strftime("%m/%d/%Y")
                    # Read the fields back. A mismatch means the search is about
                    # to run UNFILTERED, which is indistinguishable from success
                    # by row count alone -- it just returns everything. Say so
                    # loudly rather than reporting a large number as a win.
                    if got_s != want_s or got_e != want_e:
                        print(
                            f"[accela:{self.county}] WARNING date filter did not take "
                            f"(wanted {want_s}..{want_e}, field holds {got_s!r}..{got_e!r}) "
                            "-- this search is UNFILTERED",
                            file=sys.stderr,
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
                            # Real bug found live 2026-07-28 (Dallas,
                            # "Commercial Alteration Addition Permit",
                            # 100+ results): "networkidle" can return
                            # before the results grid actually finishes
                            # rendering on a larger result set -- the
                            # header row genuinely wasn't in the DOM yet
                            # on the first read, not a real "no results"
                            # case. Poll for up to 5s instead of giving
                            # up on the first miss, same pattern as
                            # EnerGovProvider's response-capture retry.
                            for _ in range(10):
                                page.wait_for_timeout(500)
                                trs = page.eval_on_selector_all(
                                    "#ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList tr",
                                    "trs => trs.map(tr => Array.from(tr.querySelectorAll('td,th'))"
                                    ".map(td => td.innerText.trim()))",
                                )
                                col_map = self._build_column_map(trs)
                                if col_map is not None:
                                    break
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

                    # Sort-order sanity check -- everything below assumes
                    # newest-first (confirmed live on Gwinnett/El Paso),
                    # but that's a per-deployment default, not a platform
                    # guarantee. Confirmed live 2026-07-31 on Broward
                    # (FTL): results came back oldest-first (page 1's
                    # first row was from 2023), and neither a single nor
                    # a double click on the "Date" column's sort link
                    # changed the order -- this deployment's General
                    # Search doesn't actually support client-triggerable
                    # re-sorting the way the ASP.NET postback link
                    # implies. Silently running the newest-first "stop at
                    # first old row" logic against ascending data means
                    # it stops on row 1 and reports 0 results for a
                    # county that actually has recent permits -- a false
                    # "no data" that's worse than an error, since nothing
                    # downstream would ever notice. Fail loud instead:
                    # detect the order from the first page and abort
                    # cleanly rather than fetch wrong data. Real fix for
                    # ascending deployments (reverse pagination from the
                    # last page, since newest are at the end) is
                    # unbuilt -- real remaining scope.
                    if page_num == 1 and len(data_rows) >= 2:
                        first_date = datetime.strptime(data_rows[0][date_idx], "%m/%d/%Y").date()
                        last_date = datetime.strptime(data_rows[-1][date_idx], "%m/%d/%Y").date()
                        if first_date < last_date:
                            print(
                                f"[accela:{self.county}] ABORT: results are sorted oldest-first "
                                f"(page 1 runs {first_date.isoformat()} -> {last_date.isoformat()}), "
                                "not newest-first as this provider assumes -- the incremental "
                                "cutoff logic would silently under-report. Needs reverse-pagination "
                                "support (real remaining scope), not implemented yet.",
                                file=sys.stderr,
                            )
                            stop = True
                            break

                    # Filter per row; do NOT stop the whole pull at the first
                    # out-of-window row.
                    #
                    # This used to `break` on the first row older than the
                    # cutoff, which assumes results are strictly newest-first.
                    # The oldest-first ABORT guard above catches only the fully
                    # reversed case -- it does nothing for UNSORTED results,
                    # where a single old row early in page 1 truncates the
                    # entire pull. Measured live 2026-08-03: Broward kept 2 of
                    # 20 rows on page 1 and stopped, and Hillsborough, Pinellas,
                    # Polk, El Paso and Bexar all showed the same 0-2 row
                    # signature. (EnerGov had the identical defect: its result
                    # sets are not date-ordered at all.)
                    #
                    # Instead, keep every in-window row on the page and let the
                    # page-level staleness check below decide when to stop.
                    kept_this_page = 0
                    newest_this_page: date | None = None
                    for r in data_rows:
                        try:
                            row_date = datetime.strptime(r[date_idx], "%m/%d/%Y").date()
                        except (ValueError, IndexError, TypeError):
                            # An unparseable date is not evidence the row is old.
                            # Keep it -- a null date is recoverable downstream,
                            # a dropped row is not.
                            row_date = None
                        if row_date is not None:
                            if newest_this_page is None or row_date > newest_this_page:
                                newest_this_page = row_date
                            if row_date <= cutoff:
                                continue
                        kept_this_page += 1
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
                        # Dedupe across date windows: adjacent windows share a
                        # boundary day, and some tenants return a record under
                        # more than one of its dates, so the same permit can
                        # legitimately appear in two searches.
                        rid = parsed.get("permit_number") or parsed.get("record_number")
                        if rid:
                            if rid in seen_ids:
                                kept_this_page -= 1
                                continue
                            seen_ids.add(rid)
                        rows_out.append(parsed)
                    print(
                        f"[accela:{self.county}] page {page_num}: {len(data_rows)} rows, "
                        f"{kept_this_page} in-window, {len(rows_out)} kept so far",
                        file=sys.stderr,
                    )
                    # Stop only when a page is ENTIRELY out of window -- i.e. it
                    # kept nothing AND its newest row predates the cutoff. That
                    # is real evidence we have paged past the window, unlike a
                    # single old row, which proves only that the results are not
                    # sorted the way this provider once assumed.
                    if (
                        kept_this_page == 0
                        and newest_this_page is not None
                        and newest_this_page <= cutoff
                    ):
                        print(
                            f"[accela:{self.county}] page {page_num} fully out of window "
                            f"(newest {newest_this_page.isoformat()} <= cutoff "
                            f"{cutoff.isoformat()}) -- stopping",
                            file=sys.stderr,
                        )
                        break
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
                    # ACA's #divGlobalLoadingMask overlay intermittently
                    # stays in the DOM intercepting pointer events even
                    # after the grid has rendered -- hit live 2026-08-03
                    # on OKC at page 62 of a 60+-page run (610 rows in,
                    # then a hard 30s click timeout that killed the whole
                    # fetch). Real click first (keeps the existing
                    # auto-wait/re-query behaviour), then fall back to a
                    # DOM-level click that bypasses hit-testing rather
                    # than losing every row collected so far.
                    try:
                        next_link.click(timeout=15000)
                    except Exception:
                        print(
                            f"[accela:{self.county}] page {page_num}: Next click intercepted, "
                            "retrying via DOM click",
                            file=sys.stderr,
                        )
                        try:
                            next_link.evaluate("el => el.click()")
                        except Exception as exc:
                            print(
                                f"[accela:{self.county}] pagination stopped at page {page_num}: {exc}",
                                file=sys.stderr,
                            )
                            break
                    try:
                        page.wait_for_load_state("networkidle", timeout=25000)
                    except Exception:
                        page.wait_for_timeout(2000)
                    time.sleep(0.5)
            finally:
                # The browser is owned by fetch_delta and reused across every
                # date window -- closing it here would kill the remaining
                # windows. Nothing to release per-window.
                pass

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
                    # Accela's grid renders MM/DD/YYYY. A bare slash->dash
                    # swap produced "01-05-2026", which is NOT ISO and sorts
                    # wrong: every windowed query compares strings against
                    # "2025-01-01", so "01-05-2026" < "2025-..." and EVERY
                    # Accela row fell outside the window. That is why counties
                    # showed a few hundred in-window rows against thousands
                    # held -- Pima had 4,914 rows and 281 in-window, and the
                    # 281 came from other sources entirely.
                    # _iso_date already handles MM/DD/YYYY (and MM-DD-YYYY,
                    # epoch ms, YYYY/MM/DD) -- use it rather than reimplementing.
                    "opened_or_announced_date": _iso_date(r.get("date")) if r.get("date") else None,
                    "description": (r.get("description") or r.get("project_name") or "Commercial building permit.")[:900],
                    "key_specs": [f"Permit type: {r.get('permit_type')}", f"Status: {r.get('status')}"],
                    "mentioned_brands": [],
                    "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression"],
                    "sources": [
                        {
                            "title": f"{self.county} County Accela permit {permit_no}",
                            "url": f"{self.base_url}/Cap/CapHome.aspx?module={self.module}",
                        }
                    ],
                    "open_for": "Active commercial building permit application. Early product/spec window.",
                    "state": self.state_code,
                    "zip": zip_code,
                }
            )
        return out
