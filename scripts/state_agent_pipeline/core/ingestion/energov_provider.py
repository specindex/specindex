"""Tyler EnerGov Citizen Self Service ingestion provider (Playwright-based).

EnerGov is a 6th platform type seen this session, recurring often enough
(Alhambra/Glendale/Carson/El Monte/Pomona in LA County; Waco/Seguin/
Sherman in TX) to be worth a dedicated provider rather than one-off work.

Unlike Accela (server-rendered HTML, no real backend API to speak of),
EnerGov's Angular SPA calls a real JSON API
(`POST /apps/selfservice/api/energov/search/search`) that returns clean
structured records -- CaseNumber/CaseType/CaseWorkclass/IssueDate/Address/
etc, no HTML-table parsing needed. But live testing (2026-07-28, against
El Monte) found the endpoint validates something about the request that
only a genuine Angular-originated XHR satisfies: a hand-crafted POST with
identical headers/body/cookies (via Playwright's session-bound
`page.request`, not just a bare `urllib` call) still 500s, while clicking
the real "Search" button in a real page succeeds. Root cause not fully
resolved -- possibly an Angular HttpClient behavior (header casing/order,
or a value computed client-side) that isn't visible in the captured
request. Rather than keep reverse-engineering that, this provider drives
the real UI (like Accela) but captures the resulting JSON response
instead of scraping HTML -- more reliable than a table-scrape, avoids the
unexplained 500.

The "Advanced" search panel (record-type + date-range filters) stays
`ng-hide`d in every state tried (fresh load, after typing a keyword,
after a search) on El Monte's theme -- so there is no confirmed way to
set a server-side date filter here. Node 1 delta filtering is therefore
entirely client-side: paginate the default/blank search a few pages and
keep only rows matching commercial keywords and a real date within the
lookback window, mirroring AccelaProvider's client-side-cutoff strategy
rather than SocrataProvider/ArcGISProvider's server-side WHERE clause.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields


class EnerGovProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        state_code: str,
        county: str,
        base_url: str,
        tenant_id: str = "1",
        tenant_name: str | None = None,
        commercial_keywords: list[str] | None = None,
        date_field: str = "IssueDate",
        lookback_days: int = 30,
        max_pages: int = 5,
        headless: bool = True,
        selfservice_path: str = "apps/selfservice",
    ) -> None:
        self.state_code = state_code.upper()
        self.county = county
        self.base_url = base_url.rstrip("/")
        # tylerhost.net tenants all use "apps/selfservice"; self-hosted
        # tenants can differ -- e.g. Pomona (connect.pomonaca.gov) serves
        # from "energov_prod/selfservice" instead ("apps/selfservice"
        # 404s there, confirmed live 2026-07-28).
        self.selfservice_path = selfservice_path.strip("/")
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        # Real category prefixes confirmed live (El Monte): "Commercial",
        # "Non-Residential" (e.g. "Business Occupancy Permit (Non-
        # Residential)"), "Mixed Use". Deployments vary; override per state.
        self.commercial_keywords = [
            k.lower() for k in (commercial_keywords or ["commercial", "non-residential", "non residential", "mixed use"])
        ]
        self.date_field = date_field
        self.lookback_days = lookback_days
        self.max_pages = max_pages
        self.headless = headless

    def _cutoff_date(self, last_watermark: str) -> date:
        if last_watermark and last_watermark not in ("0", ""):
            try:
                return datetime.strptime(last_watermark, "%Y-%m-%d").date()
            except ValueError:
                pass
        return date.today() - timedelta(days=self.lookback_days)

    def _is_commercial(self, row: dict[str, Any]) -> bool:
        haystack = f"{row.get('CaseType', '')} {row.get('CaseWorkclass', '')}".lower()
        return any(kw in haystack for kw in self.commercial_keywords)

    def _row_date(self, row: dict[str, Any]) -> date | None:
        raw = row.get(self.date_field)
        if not raw:
            return None
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        cutoff = self._cutoff_date(last_watermark)
        print(f"[energov:{self.county}] cutoff={cutoff.isoformat()} (watermark={last_watermark!r})", file=sys.stderr)

        captured: list[dict[str, Any]] = []

        def on_response(resp: Any) -> None:
            if resp.url.endswith("/api/energov/search/search") and resp.request.method == "POST":
                try:
                    data = resp.json()
                    result = data.get("Result")
                    if result is None:
                        # Seen intermittently right after a SearchModule
                        # change -- looks like a transient/error response
                        # (Result: null) distinct from a real empty-page
                        # response (which has Result.EntityResults: []).
                        # Ignore it and keep waiting for a real response
                        # rather than short-circuiting the poll loop on it.
                        print(f"[energov:{self.county}] response had null Result, ignoring", file=sys.stderr)
                        return
                    captured.append(result.get("EntityResults", []))
                except Exception as e:  # noqa: BLE001
                    print(f"[energov:{self.county}] response parse error: {e}", file=sys.stderr)

        rows_out: list[dict[str, Any]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page(user_agent="Mozilla/5.0 SpecIndex-StateAgent/0.2")
            page.on("response", on_response)
            try:
                page.goto(
                    f"{self.base_url}/{self.selfservice_path}/#/search",
                    timeout=45000,
                    wait_until="networkidle",
                )
                page.wait_for_timeout(1500)
                # Some tenants (confirmed live 2026-07-28: Carson) default
                # the "SearchModule" dropdown to something other than
                # "Permit" (Carson defaults to License, returning only
                # business-license records for the blank search) --
                # explicitly select "Permit" where the selector exists.
                # Angular ignores Playwright's select_option() alone here
                # (it doesn't fire ngModel's change binding), so dispatch a
                # real "change" event too. No-op / safe to skip on tenants
                # (El Monte, Glendale) where this selector isn't present or
                # already defaults to Permit.
                module_select = page.locator("#SearchModule")
                if module_select.count() > 0:
                    try:
                        module_select.select_option(value="Permit", timeout=5000)
                        page.eval_on_selector(
                            "#SearchModule", "el => el.dispatchEvent(new Event('change', {bubbles: true}))"
                        )
                        page.wait_for_timeout(300)
                    except Exception as e:  # noqa: BLE001
                        print(f"[energov:{self.county}] SearchModule select failed: {e}", file=sys.stderr)
                page.locator("button:has-text('Search')").first.click(timeout=15000)
                # Fires anywhere from ~3s to ~6s+ depending on tenant --
                # confirmed live (2026-07-28) Glendale's SPA is meaningfully
                # slower than El Monte's for the same click. Poll for the
                # captured response instead of guessing a fixed timeout.
                for _ in range(20):
                    if captured:
                        break
                    page.wait_for_timeout(500)
                # Real intermittent flakiness confirmed live on Carson
                # (2026-07-28, ~50% of runs): the first Search click's
                # response comes back with a null Result (silently
                # ignored by on_response, so `captured` stays empty) and
                # no second response ever fires within the poll window.
                # One retry click resolves it every time observed. Cheap
                # and safe -- a no-op if the first click already worked.
                if not captured:
                    print(f"[energov:{self.county}] no response captured, retrying Search click", file=sys.stderr)
                    page.locator("button:has-text('Search')").first.click(timeout=15000)
                    for _ in range(20):
                        if captured:
                            break
                        page.wait_for_timeout(500)

                for page_num in range(1, self.max_pages + 1):
                    if page_num > 1:
                        next_link = page.locator("#link-NextPage")
                        if next_link.count() == 0 or "disabled" in (
                            page.eval_on_selector("#link-NextPage", "el => el.closest('li').className") or ""
                        ):
                            break
                        before = len(captured)
                        next_link.click(timeout=10000)
                        for _ in range(20):
                            if len(captured) > before:
                                break
                            page.wait_for_timeout(500)
                        if len(captured) == before:
                            break

                    if not captured:
                        continue
                    batch = captured[-1]
                    print(f"[energov:{self.county}] page {page_num}: {len(batch)} rows", file=sys.stderr)
                    if not batch:
                        break
                    rows_out.extend(batch)
            except Exception as e:  # noqa: BLE001
                print(f"[energov:{self.county}] navigation/search error: {e}", file=sys.stderr)
            finally:
                browser.close()

        commercial = [r for r in rows_out if self._is_commercial(r)]
        in_window = []
        for r in commercial:
            d = self._row_date(r)
            if d is not None and d >= cutoff:
                in_window.append(r)
        print(
            f"[energov:{self.county}] fetched {len(rows_out)} total, "
            f"{len(commercial)} commercial, {len(in_window)} within lookback window",
            file=sys.stderr,
        )

        out = []
        for r in in_window:
            addr = r.get("Address") or {}
            out.append(
                {
                    "case_number": r.get("CaseNumber"),
                    "case_type": r.get("CaseType"),
                    "case_workclass": r.get("CaseWorkclass"),
                    "case_status": r.get("CaseStatus"),
                    "apply_date": r.get("ApplyDate"),
                    "issue_date": r.get("IssueDate"),
                    "description": r.get("Description"),
                    "address": r.get("AddressDisplay") or addr.get("FullAddress"),
                    "project_name": r.get("ProjectName"),
                }
            )
        return out

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        return hash_fields(row, ["case_number"])

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        # No reliable server-side incremental key here (see module
        # docstring) -- always re-scan the lookback window, same as
        # AccelaProvider's date-based approach. Downstream dedup handles
        # re-seeing already-persisted rows.
        return current or "0"

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from project_identity import slugify

        out = []
        for r in rows:
            addr = r.get("address") or ""
            city, zip_code = "", ""
            m = re.search(r",?\s*([A-Za-z .]+?)\s+CA\s+(\d{5})\s*$", addr)
            if m:
                city, zip_code = m.group(1).strip(), m.group(2)

            case_no = r.get("case_number") or ""
            uid = slugify(f"{self.county}-{case_no}")
            date_val = r.get("issue_date") or r.get("apply_date")
            out.append(
                {
                    "id": f"{self.state_code.lower()}-{self.county.lower().replace(' ', '')}-energov-{uid}"[:80],
                    "name": (r.get("project_name") or case_no)[:120],
                    "city": city,
                    "county": self.county,
                    "status": "permitting",
                    "project_type": "commercial",
                    "estimated_value_usd": None,
                    "square_footage": None,
                    "owner": "",
                    "architect": "",
                    "general_contractor": "",
                    "opened_or_announced_date": date_val[:10] if date_val else None,
                    "description": (r.get("description") or r.get("case_workclass") or "Commercial building permit.")[:900],
                    "key_specs": [f"Case type: {r.get('case_type')}", f"Status: {r.get('case_status')}"],
                    "mentioned_brands": [],
                    "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression"],
                    "sources": [
                        {
                            "title": f"{self.county} County EnerGov permit {case_no}",
                            "url": f"{self.base_url}/apps/selfservice/#/search",
                        }
                    ],
                    "open_for": "Active commercial building permit application. Early product/spec window.",
                    "state": self.state_code,
                    "zip": zip_code,
                }
            )
        return out
