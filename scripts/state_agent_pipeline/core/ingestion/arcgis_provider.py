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
        lookback_days: int = 30,
        hard_limit: int = 0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
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
