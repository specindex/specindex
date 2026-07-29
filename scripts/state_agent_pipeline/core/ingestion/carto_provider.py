"""CARTO SQL API ingestion provider.

CARTO (used by Philadelphia's open-data portal, phl.carto.com) exposes a
raw SQL-over-HTTP endpoint (`GET /api/v2/sql?q=...`) rather than a
Socrata/ArcGIS-style filtered REST query -- the where-clause is just SQL,
built by the caller and passed as part of the query string. No OBJECTID/
recordid-style incrementing watermark exists generically across CARTO
tables, so this always re-scans the lookback window on every run and
relies on merge_into_state()'s id-exact-match dedup to make re-runs a
no-op, same pattern as AccelaProvider/EnerGovProvider.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields, hash_row


class CartoProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        base_url: str,
        table: str,
        select_fields: str,
        where_sql: str,
        date_field: str,
        lookback_days: int = 30,
        row_limit: int = 5000,
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
        self.base_url = base_url.rstrip("/")
        self.table = table
        self.select_fields = select_fields
        self.where_sql = where_sql
        self.date_field = date_field
        self.lookback_days = lookback_days
        self.row_limit = row_limit
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

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        cutoff = (date.today() - timedelta(days=self.lookback_days)).isoformat()
        sql = (
            f"SELECT {self.select_fields} FROM {self.table} "
            f"WHERE {self.date_field} >= '{cutoff}' AND ({self.where_sql}) "
            f"LIMIT {self.row_limit}"
        )
        url = f"{self.base_url}?{urllib.parse.urlencode({'q': sql})}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SpecIndex-StateAgent/0.2"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            print(f"[carto:{self.table}] fetch error: {e}", file=sys.stderr)
            return []
        rows = data.get("rows") or []
        print(f"[carto:{self.table}] fetched {len(rows)} rows", file=sys.stderr)
        return rows

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        if self.hash_fields_list:
            return hash_fields(row, self.hash_fields_list)
        return hash_row(row)

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        # No reliable server-side incremental key -- always re-scan the
        # lookback window; merge_into_state()'s id-exact-match dedup
        # handles re-seeing already-persisted rows.
        return current or "0"

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.name_fields or not self.address_fields:
            raise NotImplementedError(
                "to_projects() requires name_fields/address_fields in state_config"
            )
        from .generic_mapping import field_mapped_to_projects

        return field_mapped_to_projects(
            rows,
            feed_id=self.feed_id or "carto",
            state_code=self.state_code or "",
            county=self.county or "",
            id_field=self.id_field or "id",
            watermark_field=self.id_field or "id",
            name_fields=self.name_fields,
            address_fields=self.address_fields,
            desc_fields=self.desc_fields,
            value_fields=self.value_fields,
            date_field=self.date_field,
            source_url=self.source_url or self.base_url,
            city_fields=self.city_fields,
        )
