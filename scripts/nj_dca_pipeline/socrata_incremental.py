"""Incremental Socrata fetch for NJ DCA (w9se-dmra) by recordid watermark."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from .config import COMMERCIAL_USE_GROUPS, SOCRATA_DATASET, SOCRATA_DOMAIN
from .state import RunState


def _use_group_clause() -> str:
    return " OR ".join(f"usegroupdesc='{g}'" for g in COMMERCIAL_USE_GROUPS)


def _record_id_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return -1


def build_where(state: RunState, lookback_days: int, today: date | None = None) -> str:
    """SoQL $where: commercial rows only, incremental by recordid when possible.

    Dataset composite key is treasurycode + recordid. We watermark on recordid
    ASC (monotonic in practice for new SDL loads). First run (id=0) scopes to
    the last N days via processdate so we never full-scan ~2.7M rows.
    """
    today = today or date.today()
    commercial = f"({_use_group_clause()})"
    last_id = (state.last_processed_id or "0").strip()
    if last_id not in ("", "0"):
        # Text field comparison works for zero-padded-ish numeric strings on this feed;
        # also accept numeric SoQL when possible.
        return f"{commercial} AND recordid > '{last_id}'"
    cutoff = (today - timedelta(days=lookback_days)).isoformat()
    return f"{commercial} AND processdate >= '{cutoff}T00:00:00'"


def fetch_with_retries(
    url: str,
    headers: dict[str, str],
    max_retries: int = 4,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            wait = min(60, (2**attempt) * 2)
            print(f"[socrata] retry {attempt + 1}/{max_retries}: {e}; sleep {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Socrata fetch failed after {max_retries} retries: {last_err}")


def fetch_incremental(
    state: RunState,
    *,
    lookback_days: int = 30,
    page_size: int = 2000,
    hard_limit: int = 0,
    app_token: str | None = None,
    max_retries: int = 4,
) -> list[dict[str, Any]]:
    """Pull only NEW commercial permits since last_processed_id."""
    where = build_where(state, lookback_days)
    print(f"[socrata] where={where}", file=sys.stderr)
    base = f"https://{SOCRATA_DOMAIN}/resource/{SOCRATA_DATASET}.json"
    headers = {"Accept": "application/json", "User-Agent": "SpecIndex-NJDCA-Pipeline/0.1"}
    if app_token:
        headers["X-App-Token"] = app_token

    seen_pk = set(state.seen_pks)
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "$where": where,
            "$order": "recordid ASC",
            "$limit": str(page_size),
            "$offset": str(offset),
        }
        url = base + "?" + urllib.parse.urlencode(params)
        page = fetch_with_retries(url, headers, max_retries=max_retries)
        if not page:
            break
        for row in page:
            pk = str(row.get("pk") or "").strip()
            rid = str(row.get("recordid") or "").strip()
            if not rid:
                continue
            if pk and pk in seen_pk:
                continue
            if pk:
                seen_pk.add(pk)
            out.append(row)
            if hard_limit and len(out) >= hard_limit:
                print(f"[socrata] hard_limit={hard_limit} reached", file=sys.stderr)
                return out
        if len(page) < page_size:
            break
        offset += page_size
        time.sleep(0.2)
    print(f"[socrata] fetched {len(out)} new rows", file=sys.stderr)
    return out


def advance_watermark(state: RunState, rows: list[dict[str, Any]]) -> RunState:
    """After a successful AI pass, store the highest recordid processed."""
    if not rows:
        state.last_fetched_count = 0
        return state

    max_rid = _record_id_int(state.last_processed_id)
    max_row: dict[str, Any] | None = None
    max_pd = state.last_processdate or ""
    new_pks: list[str] = []

    for r in rows:
        rid = _record_id_int(r.get("recordid"))
        if rid > max_rid:
            max_rid = rid
            max_row = r
        pd = str(r.get("processdate") or "")
        if pd >= max_pd:
            max_pd = pd
        pk = str(r.get("pk") or "")
        if pk:
            new_pks.append(pk)

    if max_rid >= 0:
        state.last_processed_id = str(max_rid)
    if max_row is not None:
        tc = str(max_row.get("treasurycode") or "")
        rid = str(max_row.get("recordid") or "")
        state.last_composite_key = f"{tc}:{rid}" if tc and rid else rid
    if max_pd:
        state.last_processdate = max_pd
    state.seen_pks = list(dict.fromkeys(list(state.seen_pks) + new_pks))[-5000:]
    state.last_fetched_count = len(rows)
    return state
