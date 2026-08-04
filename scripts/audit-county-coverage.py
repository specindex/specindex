#!/usr/bin/env python3
"""Audit corpus coverage against LIVE source counts, county by county, in parallel.

Why this exists (2026-08-03): five subagents were launched to audit the top-50
counties and all five were killed by the ~600s no-output watchdog before
finishing. Long-running work belongs in a script, not an agent. This does the
same job deterministically, in parallel, in seconds, and cannot stall.

The single most valuable comparison in this repo is **live source count vs
corpus count for the same window**. That one number surfaces every failure mode
we have hit:

  * **Stale ID watermark** -- `last_processed_id` non-zero in
    data/pipeline/{feed_id}/state-*.json makes `--lookback-days` a complete
    no-op, so only newly-appearing records arrive and the historical window is
    never fetched. Signature: large historical total, ~zero rows in-window.
  * **Truncated backfill** -- Accela throttles long anonymous paging (~40-60
    pages), so a pull silently stops partway. Signature: corpus << live.
  * **Geography mislabel** -- a config pulling a wider feed than its hardcoded
    `county` (see check-config-geography.py). Signature: corpus >> live.
  * **Date bug** -- unusable dates drop rows from every windowed query.
    Signature: big total, ~zero in-window, but the watermark looks fine.

Counts are fetched concurrently (default 12 workers) because these are
independent read-only HTTP calls against different hosts -- serialising them
wastes minutes for no benefit.

Only Socrata and ArcGIS configs can be counted server-side cheaply; Accela and
EnerGov are browser-driven and are reported as "manual" rather than guessed at.

Usage:
    python3 scripts/audit-county-coverage.py --top 50
    python3 scripts/audit-county-coverage.py --state-key CA-VENTURA --state-key NY-QUEENS
    python3 scripts/audit-county-coverage.py --top 50 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "state_agent_pipeline"))

from core.state_configs import STATE_CONFIGS  # noqa: E402

WINDOW_START = "2025-01-01"
UA = {"User-Agent": "SpecIndex-CoverageAudit/1.0"}
COUNTABLE = {"socrata", "arcgis"}


def _get_json(url: str, timeout: int = 45) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def live_count(cfg: dict) -> tuple[int | None, str]:
    """Return (count, note). None means not countable / failed."""
    ptype = cfg.get("provider_type")
    where = cfg.get("commercial_where") or "1=1"
    date_field = cfg.get("date_field")

    try:
        if ptype == "socrata":
            clause = where
            if date_field:
                clause = f"({where}) AND {date_field} >= '{WINDOW_START}'"
            q = urllib.parse.urlencode({"$select": "count(1)", "$where": clause})
            data = _get_json(f"{cfg['endpoint']}?{q}")
            if isinstance(data, list) and data:
                v = data[0]
                return int(next(iter(v.values()))), ""
            return 0, ""

        if ptype == "arcgis":
            clause = where
            if date_field:
                clause = f"({where}) AND {date_field} >= DATE '{WINDOW_START}'"
            layer = cfg.get("layer", 0)
            base = str(cfg["endpoint"]).rstrip("/")
            q = urllib.parse.urlencode({"where": clause, "returnCountOnly": "true", "f": "json"})
            data = _get_json(f"{base}/{layer}/query?{q}")
            if "count" in data:
                return int(data["count"]), ""
            return None, str(data.get("error", {}).get("message", "no count"))[:60]

        return None, f"{ptype}: browser-driven, count manually"
    except Exception as e:  # noqa: BLE001 - report, never abort the whole audit
        return None, f"{type(e).__name__}: {str(e)[:50]}"


def watermark_for(cfg: dict, key: str | None = None) -> str | None:
    """Read last_processed_id for a config.

    Watermarks live in data/pipeline/nj-dca/state-{lowercased-config-key}.json
    -- NOT under data/pipeline/{feed_id}/, which is what this originally
    guessed. That mistake made every config report "0 (no state dir)" and led
    to the wrong conclusion that no watermarks were stale. In fact OH-FRANKLIN
    sat at 676269, NC-WAKE at 284309, TX-ECTOR at 18328915 -- and a non-zero
    watermark makes --lookback-days a complete no-op, so the historical window
    is never fetched no matter how large the gap.
    """
    if key:
        f = ROOT / "data" / "pipeline" / "nj-dca" / f"state-{key.lower()}.json"
        if f.is_file():
            try:
                return str(json.loads(f.read_text()).get("last_processed_id"))
            except Exception:  # noqa: BLE001
                return "unreadable"
    return "0 (none found)"


def corpus_counts() -> dict[tuple[str, str], tuple[int, int]]:
    """(county_lower, state) -> (total, in_window)."""
    corpus = json.loads((ROOT / "data" / "national-commercial-projects.json").read_text())
    out: dict[tuple[str, str], list[int]] = {}
    for p in corpus["projects"]:
        c = (p.get("county") or "").strip().lower()
        st = (p.get("state") or "").strip().upper()
        if not c:
            continue
        e = out.setdefault((c, st), [0, 0])
        e[0] += 1
        if str(p.get("opened_or_announced_date") or "") >= WINDOW_START:
            e[1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def diagnose(live: int | None, total: int, in_window: int, wm: str | None,
             windowed: bool = True, county: str | None = None) -> str:
    if live is None:
        return "manual-check"
    # A config with no date_field yields an ALL-TIME live count, which then gets
    # compared against an in-window corpus count -- a guaranteed phantom gap.
    # NJ reported 194,801 vs 0 this way; its real in-window count is 39,322
    # against 42,537 held, i.e. complete. Don't verdict those.
    if not windowed:
        return "no-date-field"
    # A config with no `county` can't be matched against the corpus county
    # index at all, so corpus counts read 0 regardless of reality.
    if not county:
        return "no-county-on-config"
    if in_window == 0 and total > 50:
        return "STALE-WATERMARK/DATE-BUG"
    if live > 0 and in_window < live * 0.5:
        return "TRUNCATED"
    if in_window > live * 1.2 and live > 0:
        return "OVER-COUNT/MISLABEL"
    if live > 0 and in_window >= live * 0.9:
        return "complete"
    return "review"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=50, help="Audit configs for the top-N counties by population.")
    ap.add_argument("--state-key", action="append", default=[], help="Audit specific STATE_CONFIGS keys instead.")
    ap.add_argument("--workers", type=int, default=12, help="Parallel live-count fetches (default 12).")
    ap.add_argument("--json", help="Also write the full result as JSON to this path.")
    args = ap.parse_args(argv)

    keys = args.state_key or sorted(STATE_CONFIGS)
    keys = [k for k in keys if STATE_CONFIGS[k].get("provider_type") in COUNTABLE or args.state_key]

    print(f"Auditing {len(keys)} configs, window >= {WINDOW_START}, {args.workers} workers "
          f"(lookback would be {(date.today() - date(2025, 1, 1)).days} days)\n", flush=True)

    cc = corpus_counts()
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(live_count, STATE_CONFIGS[k]): k for k in keys}
        for fut in as_completed(futs):
            k = futs[fut]
            cfg = STATE_CONFIGS[k]
            live, note = fut.result()
            county = (cfg.get("county") or "").strip().lower()
            st = (cfg.get("state_code") or "").strip().upper()
            total, in_win = cc.get((county, st), (0, 0))
            wm = watermark_for(cfg, k)
            results.append({
                "key": k, "county": cfg.get("county"), "state": st,
                "live_since_2025": live, "corpus_total": total, "corpus_in_window": in_win,
                "watermark": wm,
                "verdict": diagnose(live, total, in_win, wm,
                                    windowed=bool(cfg.get("date_field")),
                                    county=cfg.get("county")),
                "note": note,
            })

    # Several configs can legitimately share one county (four LA-area city
    # configs all map to Los Angeles). Comparing each one against the county's
    # full corpus total produces a bogus OVER-COUNT. Aggregate live counts per
    # (county, state) first, then re-verdict on the summed figure.
    agg: dict[tuple[str, str], int] = {}
    for r in results:
        if r["live_since_2025"] is not None:
            k2 = ((r["county"] or "").lower(), r["state"])
            agg[k2] = agg.get(k2, 0) + r["live_since_2025"]
    for r in results:
        k2 = ((r["county"] or "").lower(), r["state"])
        if k2 in agg:
            r["live_county_total"] = agg[k2]
            cfg2 = STATE_CONFIGS[r["key"]]
            r["verdict"] = diagnose(agg[k2], r["corpus_total"], r["corpus_in_window"],
                                    r["watermark"], windowed=bool(cfg2.get("date_field")),
                                    county=cfg2.get("county"))

    order = {"STALE-WATERMARK/DATE-BUG": 0, "TRUNCATED": 1, "OVER-COUNT/MISLABEL": 2,
             "review": 3, "no-date-field": 4, "no-county-on-config": 5,
             "manual-check": 6, "complete": 7}
    results.sort(key=lambda r: (order.get(r["verdict"], 9), -(r["live_since_2025"] or 0)))

    print(f"{'config':<26}{'county':<18}{'live':>9}{'corpus':>9}{'gap':>9}  verdict")
    print("-" * 92)
    for r in results:
        live = r["live_since_2025"]
        gap = (live - r["corpus_in_window"]) if live is not None else None
        print(f"{r['key']:<26}{(r['county'] or '-')[:17]:<18}"
              f"{(live if live is not None else '-'):>9}{r['corpus_in_window']:>9}"
              f"{(gap if gap is not None else '-'):>9}  {r['verdict']}"
              + (f"  [{r['note']}]" if r["note"] else ""))

    tally: dict[str, int] = {}
    total_gap = 0
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
        # Only count gaps we actually believe: no-date-field / no-county-on-config
        # rows compare an all-time or unmatchable live count against an in-window
        # corpus count, so their "gap" is meaningless (NJ inflated this by 194,801).
        if r["live_since_2025"] is not None and r["verdict"] not in (
            "no-date-field", "no-county-on-config", "manual-check"
        ):
            total_gap += max(0, r["live_since_2025"] - r["corpus_in_window"])
    print("\nverdicts:", ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print(f"total recoverable gap (live - corpus, in-window): {total_gap:,} projects")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
