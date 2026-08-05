"""Flat CSV-download ingestion provider.

For sources that publish a plain CSV dump (no query API at all) --
e.g. San Diego's seshat.datasd.org development-permits export. Unlike
Socrata/ArcGIS, there's no server-side WHERE clause to push a commercial
filter into, so filtering happens client-side against a keyword
include/exclude list on a chosen field, same spirit as
AccelaProvider/EnerGovProvider's client-side commercial-keyword match.

No reliable incremental watermark either (the file is a full dump,
re-published in place) -- always re-scans the lookback window;
merge_into_state()'s id-exact-match dedup makes re-seeing already-
persisted rows a no-op, same pattern as every other no-server-side-filter
provider this session.
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields, hash_row


class CsvDownloadProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        csv_url: str,
        # Dataset page to visit before the file request, for portals that
        # gate the file endpoint behind a session cookie.
        referer_url: str | None = None,
        date_field: str,
        filter_field: str,
        include_keywords: list[str],
        exclude_keywords: list[str] | None = None,
        lookback_days: int = 30,
        hash_fields_list: list[str] | None = None,
        feed_id: str | None = None,
        state_code: str | None = None,
        county: str | None = None,
        id_field: str | None = None,
        name_fields: list[str] | None = None,
        address_fields: list[str] | None = None,
        desc_fields: list[str] | None = None,
        value_fields: list[str] | None = None,
        city_fields: list[str] | None = None,
        source_url: str | None = None,
    ) -> None:
        self.csv_url = csv_url
        self.referer_url = referer_url
        self.date_field = date_field
        self.filter_field = filter_field
        self.include_keywords = [k.lower() for k in include_keywords]
        self.exclude_keywords = [k.lower() for k in (exclude_keywords or [])]
        self.lookback_days = lookback_days
        self.hash_fields_list = hash_fields_list
        self.feed_id = feed_id
        self.state_code = state_code
        self.county = county
        self.id_field = id_field
        self.name_fields = name_fields
        self.address_fields = address_fields
        self.desc_fields = desc_fields
        self.value_fields = value_fields
        self.city_fields = city_fields
        self.source_url = source_url

    def _is_match(self, row: dict[str, Any]) -> bool:
        val = (row.get(self.filter_field) or "").lower()
        if any(k in val for k in self.exclude_keywords):
            return False
        return any(k in val for k in self.include_keywords)

    def _fetch_via_browser(self) -> str | None:
        """Re-fetch through a real browser session when plain HTTP is refused.

        Only used after urllib fails, so tenants that work over plain HTTP pay
        nothing for this. `referer_url` should be the dataset page the file
        belongs to -- visiting it first is what establishes the session cookie
        the file endpoint checks for.
        """
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"))
                try:
                    if self.referer_url:
                        page = ctx.new_page()
                        page.goto(self.referer_url, timeout=60000,
                                  wait_until="domcontentloaded")
                        page.wait_for_timeout(2000)
                    resp = ctx.request.get(self.csv_url, timeout=90000)
                    if not resp.ok:
                        print(f"[csv:{self.csv_url}] browser fetch {resp.status}", file=sys.stderr)
                        return None
                    print(f"[csv:{self.csv_url}] plain HTTP refused; fetched via browser",
                          file=sys.stderr)
                    return resp.body().decode("utf-8-sig", errors="replace")
                finally:
                    browser.close()
        except Exception as e:  # noqa: BLE001
            print(f"[csv:{self.csv_url}] browser fetch failed: {e}", file=sys.stderr)
            return None

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        cutoff = (date.today() - timedelta(days=self.lookback_days)).isoformat()
        try:
            req = urllib.request.Request(self.csv_url, headers={"User-Agent": "SpecIndex-StateAgent/0.2"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            # Some portals gate the FILE endpoint behind a JS/cookie challenge
            # even though the catalog API is wide open -- Denton's CKAN returns
            # 403 to urllib with full browser headers, but serves the identical
            # file to a request made through a real browser session. Falling
            # back rather than giving up turns a "dead source" into a live one.
            text = self._fetch_via_browser()
            if text is None:
                print(f"[csv:{self.csv_url}] fetch error: {e}", file=sys.stderr)
                return []

        reader = csv.DictReader(io.StringIO(text))
        out = []
        for row in reader:
            if not self._is_match(row):
                continue
            issue_date = (row.get(self.date_field) or "")[:10]
            if issue_date and issue_date >= cutoff:
                out.append(row)
        print(f"[csv:{self.csv_url}] {len(out)} rows matched filter + {self.lookback_days}-day window", file=sys.stderr)
        return out

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        if self.hash_fields_list:
            return hash_fields(row, self.hash_fields_list)
        return hash_row(row)

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        # Full-dump CSV, no incremental key -- always re-scan the lookback
        # window (see module docstring).
        return current or "0"

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.name_fields or not self.address_fields:
            raise NotImplementedError(
                "to_projects() requires name_fields/address_fields in state_config"
            )
        from .generic_mapping import field_mapped_to_projects

        return field_mapped_to_projects(
            rows,
            feed_id=self.feed_id or "csv",
            state_code=self.state_code or "",
            county=self.county or "",
            id_field=self.id_field or "id",
            watermark_field=self.id_field or "id",
            name_fields=self.name_fields,
            address_fields=self.address_fields,
            desc_fields=self.desc_fields,
            value_fields=self.value_fields,
            date_field=self.date_field,
            source_url=self.source_url or self.csv_url,
            city_fields=self.city_fields,
        )
