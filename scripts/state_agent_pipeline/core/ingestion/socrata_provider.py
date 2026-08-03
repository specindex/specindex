"""Socrata SODA API ingestion provider.

Refactor of the pipeline's original NJ-specific socrata_incremental.py
into the generic BaseIngestionProvider interface -- same proven fetch/
retry/pagination logic (verified live against NJ DCA, w9se-dmra), now
parameterized by a StateConfig instead of hardcoded to one dataset.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields, hash_row


class SocrataProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        domain: str,
        dataset: str,
        watermark_field: str,
        hash_fields_list: list[str] | None = None,
        commercial_where: str | None = None,
        lookback_days: int = 30,
        page_size: int = 2000,
        app_token: str | None = None,
        max_retries: int = 4,
        order_field: str | None = None,
        date_field: str = "processdate",
        hard_limit: int = 0,
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
        join_address_fields: bool = False,
        default_city: str | None = None,
    ) -> None:
        self.domain = domain
        self.dataset = dataset
        self.watermark_field = watermark_field
        self.hash_fields_list = hash_fields_list
        self.commercial_where = commercial_where
        self.lookback_days = lookback_days
        self.page_size = page_size
        self.app_token = app_token
        self.max_retries = max_retries
        # First-run cutoff field for the initial lookback window --
        # defaults to NJ's "processdate" for backward compat, but every
        # other state's dataset needs its own real date field name here
        # (e.g. LA's "issue_date"); this used to be hardcoded, which would
        # silently 400 or scan unbounded on any non-NJ dataset.
        self.date_field = date_field
        self.hard_limit = hard_limit
        # Most Socrata watermark fields (recordid, an autoincrementing pk)
        # sort correctly as plain ASC text; override if a state's field
        # needs different ordering.
        self.order_field = order_field or watermark_field
        # Opt-in generic mapping (see generic_mapping.py) -- only used
        # when a config explicitly sets name_fields/address_fields;
        # states that don't set these keep going through Flash/Sonnet
        # exactly as before.
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
        self.join_address_fields = join_address_fields
        self.default_city = default_city

    def _build_where(self, last_watermark: str) -> str:
        clauses = [self.commercial_where] if self.commercial_where else []
        last = (last_watermark or "0").strip()
        if last not in ("", "0"):
            clauses.append(f"{self.watermark_field} > '{last}'")
        else:
            cutoff = (date.today() - timedelta(days=self.lookback_days)).isoformat()
            # First run: bound by a date-ish field if the caller didn't
            # give us a numeric watermark to start from -- never an
            # unbounded scan of a multi-million-row dataset.
            clauses.append(f"{self.date_field} >= '{cutoff}T00:00:00'")
        return " AND ".join(f"({c})" for c in clauses)

    def _fetch_with_retries(self, url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            # OSError covers ConnectionResetError/BrokenPipeError, which
            # Socrata throws mid-body on long backfills (a 579-day
            # Manhattan pull, ~86k rows / 44 pages, died on page ~30 with
            # "[Errno 54] Connection reset by peer" on 2026-08-03). Those
            # are NOT URLErrors -- they surface from resp.read() after the
            # response headers are already in -- so the old tuple let a
            # purely transient reset abort an entire multi-page backfill
            # with zero rows merged, despite retry logic being right here.
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
                last_err = e
                wait = min(60, (2**attempt) * 2)
                print(f"[socrata:{self.dataset}] retry {attempt + 1}/{self.max_retries}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"Socrata fetch failed after {self.max_retries} retries: {last_err}")

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        where = self._build_where(last_watermark)
        print(f"[socrata:{self.dataset}] where={where}", file=sys.stderr)
        base = f"https://{self.domain}/resource/{self.dataset}.json"
        headers = {"Accept": "application/json", "User-Agent": "SpecIndex-StateAgent/0.2"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            params = {
                "$where": where,
                "$order": f"{self.order_field} ASC",
                "$limit": str(self.page_size),
                "$offset": str(offset),
            }
            url = base + "?" + urllib.parse.urlencode(params)
            page = self._fetch_with_retries(url, headers)
            if not page:
                break
            out.extend(page)
            if self.hard_limit and len(out) >= self.hard_limit:
                out = out[: self.hard_limit]
                break
            if len(page) < self.page_size:
                break
            offset += self.page_size
            time.sleep(0.2)
        print(f"[socrata:{self.dataset}] fetched {len(out)} rows", file=sys.stderr)
        return out

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        if self.hash_fields_list:
            return hash_fields(row, self.hash_fields_list)
        return hash_row(row)

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        def as_int(v: Any) -> int | None:
            try:
                return int(str(v).strip())
            except (TypeError, ValueError):
                return None

        # Real bug found 2026-07-28: for a non-numeric watermark_field
        # (e.g. Cook County's `pin`, an alphanumeric parcel id), every
        # row's as_int() silently returned a sentinel, so `best` never
        # advanced past its starting value -- next_watermark() always
        # returned "0", meaning _build_where() always took the
        # first-run/date-cutoff branch and rescanned the full lookback
        # window on every run instead of ever narrowing to only-new rows.
        # Safe in practice (merge_into_state()'s exact-id dedup makes
        # re-seeing already-persisted rows a no-op) but silently wasteful.
        # Made explicit here rather than fixed silently: a numeric
        # watermark_field (recordid-style) still advances normally; a
        # non-numeric one intentionally always rescans, since a string
        # `>` comparison on something like a parcel id wouldn't track
        # real-world chronological order anyway.
        current_int = as_int(current)
        row_ints = [v for v in (as_int(r.get(self.watermark_field)) for r in rows) if v is not None]
        if current_int is None and not row_ints:
            return current or "0"
        best = max([current_int] + row_ints) if current_int is not None else max(row_ints)
        return str(best) if best >= 0 else current

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.name_fields or not self.address_fields:
            raise NotImplementedError(
                "to_projects() requires name_fields/address_fields in state_config "
                "-- this state isn't opted into deterministic mapping, route through Flash/Sonnet instead"
            )
        from .generic_mapping import field_mapped_to_projects

        return field_mapped_to_projects(
            rows,
            feed_id=self.feed_id or "socrata",
            state_code=self.state_code or "",
            county=self.county or "",
            id_field=self.id_field or self.watermark_field,
            watermark_field=self.watermark_field,
            name_fields=self.name_fields,
            address_fields=self.address_fields,
            desc_fields=self.desc_fields,
            value_fields=self.value_fields,
            date_field=self.date_field,
            source_url=self.source_url or f"https://{self.domain}/resource/{self.dataset}.json",
            city_fields=self.city_fields,
            join_address_fields=self.join_address_fields,
            default_city=self.default_city,
        )
