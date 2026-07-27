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
        hard_limit: int = 0,
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
        self.hard_limit = hard_limit
        # Most Socrata watermark fields (recordid, an autoincrementing pk)
        # sort correctly as plain ASC text; override if a state's field
        # needs different ordering.
        self.order_field = order_field or watermark_field

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
            clauses.append(f"processdate >= '{cutoff}T00:00:00'")
        return " AND ".join(f"({c})" for c in clauses)

    def _fetch_with_retries(self, url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
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
        def as_int(v: Any) -> int:
            try:
                return int(str(v).strip())
            except (TypeError, ValueError):
                return -1

        best = as_int(current)
        for r in rows:
            v = as_int(r.get(self.watermark_field))
            if v > best:
                best = v
        return str(best) if best >= 0 else current
