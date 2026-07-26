#!/usr/bin/env python3
"""Shared Socrata SODA API adapter -- one query helper reused across every
Socrata-backed city (NYC, LA, Chicago, Seattle, New Orleans, etc.) instead of
a bespoke script per city. Mirrors the query_layer() helper already
duplicated in pull-nc-arcgis.py / pull-ga-municipal-commercial.py for
ArcGIS sources -- same idea (one adapter per platform, configured per
source), different platform.

Socrata SODA API reference: https://dev.socrata.com/docs/queries/
Pagination via $limit/$offset, filtering via $where (SQL-like) or $q
(full-text), unauthenticated by default -- pass an app token (free to
register, raises the per-IP rate limit) via the SOCRATA_APP_TOKEN env var
if a source starts throttling.

Per the standing verify-before-build discipline (see docs/states/ga.md
"Adding a new source: step-by-step"): before writing a real per-city pull
script against any dataset, use dataset_max_date() to confirm it's still
actively updated, inspect a sample row's fields to confirm a usable
commercial/non-residential filter exists, and check the location fields
land in the expected city/county -- the same liveness/schema/geography
checks already burned twice this session on ArcGIS sources (Forsyth
County GA vs NC; a source claimed as Hall County GA that was actually
Nashville/Davidson County TN).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def query_socrata(
    domain: str,
    dataset_id: str,
    where: str | None = None,
    q: str | None = None,
    select: str | None = None,
    order: str | None = None,
    page_size: int = 1000,
    app_token: str | None = None,
) -> list[dict]:
    """Query a Socrata dataset, paginating via $limit/$offset until exhausted.

    domain: host only, no scheme, e.g. "data.cityofnewyork.us"
    dataset_id: the dataset's 4-4 resource id, e.g. "ipu4-2q9a"
    where: SQL-like filter, e.g. "issue_date > '2025-01-01'"
    q: full-text search across all columns; alternative/complement to where
    select: SoQL $select clause, e.g. for an aggregate query
    order: SoQL $order clause
    app_token: optional; unauthenticated requests share a per-IP rate limit.
      Defaults to the SOCRATA_APP_TOKEN env var if set.
    """
    app_token = app_token or os.environ.get("SOCRATA_APP_TOKEN")
    base = f"https://{domain}/resource/{dataset_id}.json"
    out: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": str(page_size), "$offset": str(offset)}
        if where:
            params["$where"] = where
        if q:
            params["$q"] = q
        if select:
            params["$select"] = select
        if order:
            params["$order"] = order
        url = f"{base}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "specindex-pull/1.0"})
        if app_token:
            req.add_header("X-App-Token", app_token)
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.loads(resp.read())
        if not page:
            break
        out.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return out


def dataset_max_date(domain: str, dataset_id: str, date_field: str) -> str | None:
    """Freshness check: max value of date_field. Use this to confirm a
    dataset is still actively updated before trusting it enough to build a
    real per-city pull script -- an abandoned dataset with a clean schema
    is still useless."""
    rows = query_socrata(
        domain, dataset_id, select=f"max({date_field}) as max_date", page_size=1
    )
    if not rows:
        return None
    return rows[0].get("max_date")


def sample_fields(domain: str, dataset_id: str, n: int = 3) -> list[dict]:
    """Schema check: return n raw rows so field names/values (including
    location fields) can be inspected before committing to a filter or
    trusting the geography."""
    return query_socrata(domain, dataset_id, page_size=n)
