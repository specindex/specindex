"""ArcGIS REST (FeatureServer/MapServer) ingestion provider.

Incremental delta via `OBJECTID > {last_watermark}` -- OBJECTID is an
Esri-managed autoincrementing integer present on essentially every
ArcGIS layer, making it a reliable watermark field independent of
whatever business/date fields a given state's layer happens to expose
(unlike Socrata, where the watermark field varies dataset to dataset).

Pagination and the "+"-vs-"%20" space-encoding gotcha are inherited
lessons from tonight's scripts/pull-county-arcgis.py query_layer() --
some ArcGIS servers reject a `+`-encoded space inside a quoted string
literal, so this always encodes via `urllib.parse.quote`, not the
urlencode default.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields, hash_row


class ArcGISProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        base_url: str,
        layer: int = 0,
        out_fields: str = "*",
        commercial_where: str | None = None,
        watermark_field: str = "OBJECTID",
        hash_fields_list: list[str] | None = None,
        page_size: int = 1000,
        max_retries: int = 4,
        include_geometry: bool = True,
        date_field: str | None = None,
        date_field_is_string: bool = False,
        date_literal_style: str = "date",
        lookback_days: int = 30,
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
        self.layer = layer
        self.out_fields = out_fields
        self.commercial_where = commercial_where
        self.watermark_field = watermark_field
        self.hash_fields_list = hash_fields_list
        self.page_size = page_size
        self.max_retries = max_retries
        self.include_geometry = include_geometry
        # Unlike Socrata's recordid (small monotonic ids on incremental
        # daily-load datasets), OBJECTID on a long-lived ArcGIS layer can
        # already be in the tens/hundreds of thousands -- "OBJECTID > 0"
        # on a fresh watermark means "the entire layer's history," not
        # "since yesterday." Bound the first run by a real date field,
        # same principle as SocrataProvider's lookback_days.
        self.date_field = date_field
        # A handful of ArcGIS layers (e.g. Pearland's Commercial_Permits)
        # store their date column as esriFieldTypeString ("2021-02-23 0:00")
        # rather than a real Esri Date field -- `DATE '...'` literal syntax
        # 400s against those, so fall back to a plain string comparison,
        # which works because the stored format is zero-padded YYYY-MM-DD.
        self.date_field_is_string = date_field_is_string
        # Some SQL-Server-backed ArcGIS Servers (e.g. Beaumont's Cityworks
        # FeatureServer) reject the standard `DATE '...'` literal with a
        # "Missing operand" error and require `TIMESTAMP '... 00:00:00'`
        # instead -- verified by direct query against both variants.
        self.date_literal_style = date_literal_style
        self.lookback_days = lookback_days
        self.hard_limit = hard_limit

    def _build_where(self, last_watermark: str) -> str:
        clauses = [self.commercial_where] if self.commercial_where else []
        last = (last_watermark or "0").strip()
        if last.isdigit() and int(last) > 0:
            clauses.append(f"{self.watermark_field} > {last}")
        elif self.date_field:
            import datetime as _dt

            cutoff = (_dt.date.today() - _dt.timedelta(days=self.lookback_days)).isoformat()
            if self.date_literal_style == "string_slash":
                # Some layers store a text-typed date field as "YYYY/MM/DD"
                # (e.g. Virginia Beach's IssueDate, sqlTypeNVarchar) --
                # lexicographic string comparison only works if the cutoff
                # is formatted to match exactly; the plain ISO cutoff
                # ("YYYY-MM-DD") silently returns 0 rows against a slash-
                # formatted column instead of erroring.
                clauses.append(f"{self.date_field} >= '{cutoff.replace('-', '/')}'")
            elif self.date_field_is_string:
                clauses.append(f"{self.date_field} >= '{cutoff}'")
            elif self.date_literal_style == "timestamp":
                clauses.append(f"{self.date_field} >= TIMESTAMP '{cutoff} 00:00:00'")
            elif self.date_literal_style == "yyyymmdd_int":
                # Some older ArcGIS Server instances store a "date" field as
                # a plain esriFieldTypeDouble in YYYYMMDD form (e.g.
                # Greenville SC's APPLICDATE) and reject DATE/TIMESTAMP
                # literals on the real date-typed field entirely (a genuine
                # server-side bug, not a syntax issue -- confirmed by the
                # same "Failed to execute query" error on every literal
                # style tried against every date field on that layer).
                clauses.append(f"{self.date_field} >= {cutoff.replace('-', '')}")
            else:
                clauses.append(f"{self.date_field} >= DATE '{cutoff}'")
        else:
            clauses.append(f"{self.watermark_field} > 0")
        return " AND ".join(f"({c})" for c in clauses) if len(clauses) > 1 else clauses[0]

    def _fetch_page(self, where: str, offset: int) -> dict[str, Any]:
        params: dict[str, str] = {
            "where": where,
            "outFields": self.out_fields,
            "f": "json",
            "resultOffset": str(offset),
            "resultRecordCount": str(self.page_size),
            "orderByFields": f"{self.watermark_field} ASC",
        }
        if self.include_geometry:
            params["returnGeometry"] = "true"
            params["outSR"] = "4326"
        else:
            params["returnGeometry"] = "false"
        url = f"{self.base_url}/{self.layer}/query?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SpecIndex-StateAgent/0.2"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if "error" in data:
                    raise RuntimeError(str(data["error"])[:300])
                return data
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as e:
                last_err = e
                wait = min(60, (2**attempt) * 2)
                print(f"[arcgis:{self.base_url}] retry {attempt + 1}/{self.max_retries}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"ArcGIS fetch failed after {self.max_retries} retries: {last_err}")

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        where = self._build_where(last_watermark)
        print(f"[arcgis:{self.base_url}] where={where}", file=sys.stderr)
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self._fetch_page(where, offset)
            feats = data.get("features") or []
            for f in feats:
                attrs = dict(f.get("attributes") or {})
                geom = f.get("geometry") or {}
                if "x" in geom and "y" in geom:
                    attrs["_lon"], attrs["_lat"] = geom["x"], geom["y"]
                out.append(attrs)
            if self.hard_limit and len(out) >= self.hard_limit:
                out = out[: self.hard_limit]
                break
            if len(feats) < self.page_size or not data.get("exceededTransferLimit"):
                break
            offset += self.page_size
            time.sleep(0.2)
        print(f"[arcgis:{self.base_url}] fetched {len(out)} rows", file=sys.stderr)
        return out

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        if self.hash_fields_list:
            return hash_fields(row, self.hash_fields_list)
        return hash_row(row)

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        def as_int(v: Any) -> int:
            try:
                return int(v)
            except (TypeError, ValueError):
                return -1

        best = as_int(current)
        for r in rows:
            v = as_int(r.get(self.watermark_field))
            if v > best:
                best = v
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
            feed_id=self.feed_id or "arcgis",
            state_code=self.state_code or "",
            county=self.county or "",
            id_field=self.id_field or "OBJECTID",
            watermark_field=self.watermark_field,
            name_fields=self.name_fields,
            address_fields=self.address_fields,
            desc_fields=self.desc_fields,
            value_fields=self.value_fields,
            date_field=self.date_field,
            source_url=self.source_url or self.base_url,
            city_fields=self.city_fields,
        )
