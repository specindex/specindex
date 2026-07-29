"""CKAN (datastore_search_sql) ingestion provider.

CKAN is a 5th open-data platform type seen this session (after Socrata/
ArcGIS/Accela/OpenDataSoft) -- Santa Monica, CA's portal (data.santamonica.
gov). Structurally close to Socrata: a resource id + a SQL-ish query
string + JSON response, no auth required for reads. `datastore_search_sql`
takes a single `sql` query param against a table literally named after the
resource's UUID (must be double-quoted since it starts with a digit-safe
but hyphenated identifier).
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


class CkanProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        base_url: str,
        resource_id: str,
        watermark_field: str,
        hash_fields_list: list[str] | None = None,
        commercial_where: str | None = None,
        date_field: str = "date_entered",
        lookback_days: int = 30,
        page_size: int = 2000,
        max_retries: int = 4,
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.resource_id = resource_id
        self.watermark_field = watermark_field
        self.hash_fields_list = hash_fields_list
        self.commercial_where = commercial_where
        self.date_field = date_field
        self.lookback_days = lookback_days
        self.page_size = page_size
        self.max_retries = max_retries
        self.hard_limit = hard_limit
        # Opt-in generic mapping (see generic_mapping.py) -- only used when
        # a config explicitly sets name_fields/address_fields, same pattern
        # as SocrataProvider/ArcGISProvider.
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

    def _build_where(self, last_watermark: str) -> str:
        clauses = [self.commercial_where] if self.commercial_where else []
        last = (last_watermark or "0").strip()
        if last.isdigit() and int(last) > 0:
            clauses.append(f"{self.watermark_field} > {last}")
        else:
            cutoff = (date.today() - timedelta(days=self.lookback_days)).isoformat()
            clauses.append(f"{self.date_field} >= '{cutoff}'")
        return " AND ".join(f"({c})" for c in clauses)

    def _fetch_with_retries(self, url: str) -> dict[str, Any]:
        last_err: Exception | None = None
        headers = {"Accept": "application/json", "User-Agent": "SpecIndex-StateAgent/0.2"}
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                last_err = e
                wait = min(60, (2**attempt) * 2)
                print(f"[ckan:{self.resource_id}] retry {attempt + 1}/{self.max_retries}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"CKAN fetch failed after {self.max_retries} retries: {last_err}")

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        where = self._build_where(last_watermark)
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            sql = (
                f'SELECT * FROM "{self.resource_id}" WHERE {where} '
                f"ORDER BY {self.watermark_field} ASC LIMIT {self.page_size} OFFSET {offset}"
            )
            url = f"{self.base_url}/api/3/action/datastore_search_sql?" + urllib.parse.urlencode({"sql": sql})
            print(f"[ckan:{self.resource_id}] sql={sql}", file=sys.stderr)
            data = self._fetch_with_retries(url)
            if not data.get("success"):
                raise RuntimeError(f"CKAN query failed: {data.get('error')}")
            records = data.get("result", {}).get("records", [])
            if not records:
                break
            out.extend(records)
            if self.hard_limit and len(out) >= self.hard_limit:
                out = out[: self.hard_limit]
                break
            if len(records) < self.page_size:
                break
            offset += self.page_size
            time.sleep(0.2)
        print(f"[ckan:{self.resource_id}] fetched {len(out)} rows", file=sys.stderr)
        return out

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.name_fields or not self.address_fields:
            raise NotImplementedError(
                "to_projects() requires name_fields/address_fields in state_config "
                "-- this state isn't opted into deterministic mapping, route through Flash/Sonnet instead"
            )
        from .generic_mapping import field_mapped_to_projects

        return field_mapped_to_projects(
            rows,
            feed_id=self.feed_id or "ckan",
            state_code=self.state_code or "",
            county=self.county or "",
            id_field=self.id_field or self.watermark_field,
            watermark_field=self.watermark_field,
            name_fields=self.name_fields,
            address_fields=self.address_fields,
            desc_fields=self.desc_fields,
            value_fields=self.value_fields,
            date_field=self.date_field,
            source_url=self.source_url or f"{self.base_url}/dataset/{self.resource_id}",
            city_fields=self.city_fields,
        )

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
