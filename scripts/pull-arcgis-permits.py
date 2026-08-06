#!/usr/bin/env python3
"""A2 -- generic ArcGIS FeatureServer permit client. One YAML per layer.

Same argument as A1: the differences between metro feeds are field NAMES and a
filter, which is configuration. Together A1 and A2 cover roughly 20 of the top
30 metros -- A2 takes the ones with no Socrata feed (Denver, DC, Nashville,
Miami-Dade, Raleigh, Fort Worth, Las Vegas).

THREE WAYS ARCGIS DIFFERS FROM SOCRATA, each of which bit during the build:

  LAYER IDS ARE NOT ZERO. Denver's layer is 317. Querying /FeatureServer/0
  returned a metadata document with no fields and no error -- indistinguishable
  from a layer that exists and is empty. Every config names its layer and this
  script refuses to guess one.

  DATES ARE EPOCH MILLISECONDS in results but need `DATE 'YYYY-MM-DD'` literals
  in a where-clause. Passing an ISO string to the filter returns everything,
  silently, because the clause fails open.

  PAGING IS resultOffset/resultRecordCount AND SERVERS CAP IT. maxRecordCount is
  read from the layer rather than assumed; asking for 5,000 where the cap is
  1,000 yields 1,000 and no warning that the rest was dropped.

EVERY RECORD CARRIES source_url AND fetched_at, per skill rule 5.
"""
from __future__ import annotations
import argparse, datetime, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def get(url: str, params: dict, timeout: float = 90) -> dict:
    q = urllib.parse.urlencode({**params, "f": "json"})
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def count(layer_url: str, where: str) -> int:
    d = get(f"{layer_url}/query", {"where": where, "returnCountOnly": "true"})
    if "error" in d:
        raise RuntimeError(f"{where!r}: {d['error'].get('message') or d['error']}")
    return int(d.get("count", 0))


def esri_date(ms) -> str | None:
    """Results give epoch milliseconds; the corpus wants ISO."""
    if ms in (None, ""):
        return None
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).date().isoformat()
    except (ValueError, OSError, TypeError):
        return None


def main() -> int:
    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary = {}

    for cpath in args.configs:
        cfg = yaml.safe_load(open(cpath))
        f = cfg["fields"]
        layer_url = f"{cfg['service'].rstrip('/')}/{cfg['layer']}"
        meta = get(layer_url, {})
        if "error" in meta or not meta.get("fields"):
            print(f"[{cfg['jurisdiction']}] layer {cfg['layer']} returned no fields -- "
                  f"wrong layer id? {str(meta)[:120]}", flush=True)
            continue
        page = min(int(meta.get("maxRecordCount") or 1000), 2000)
        date_col = f["opened_date"]
        # ArcGIS wants a DATE literal here. An ISO string fails open and returns
        # the whole layer, which reads as a wildly successful pull.
        where_win = f"{cfg['commercial_filter']} AND {date_col} >= DATE '{args.since}'"

        total = count(layer_url, "1=1")
        comm = count(layer_url, cfg["commercial_filter"])
        win = count(layer_url, where_win)
        note = " (commercial-only by design)" if cfg.get("commercial_by_design") else ""
        print(f"[{cfg['jurisdiction']}] total={total:,}  commercial={comm:,}{note}  "
              f"since {args.since}={win:,}  page={page}", flush=True)
        if comm > total:
            print("  WARNING: commercial count exceeds total -- filter is inert", flush=True)

        out_fields = [v for v in f.values() if v]
        rows, offset = [], 0
        while offset < min(args.limit, win):
            d = get(f"{layer_url}/query", {
                "where": where_win, "outFields": ",".join(out_fields),
                "orderByFields": f"{date_col} DESC",
                "resultOffset": offset, "resultRecordCount": page,
                "returnGeometry": "false"})
            feats = d.get("features") or []
            if not feats:
                break
            for ft in feats:
                a = ft.get("attributes") or {}
                pid = str(a.get(f["permit_number"]) or "").strip()
                if not pid:
                    continue
                rows.append({
                    "project_id": f"{cfg['id_prefix']}-{pid.lower()}",
                    "name": str(a.get(f["description"]) or "")[:500],
                    "city": cfg["jurisdiction"], "state": cfg["state"], "county": cfg["county"],
                    "status": a.get(f.get("status")) if f.get("status") else None,
                    "opened_or_announced_date": esri_date(a.get(date_col)),
                    "estimated_value_usd": a.get(f["value"]) if f.get("value") else None,
                    "street_address": a.get(f.get("address")) if f.get("address") else None,
                    "source_url": layer_url,
                    "fetched_at": fetched_at,
                })
            offset += page
            time.sleep(args.pause)
            print(f"  [{cfg['jurisdiction']}] {len(rows):,} rows", flush=True)

        summary[cfg["jurisdiction"]] = {"total": total, "commercial": comm,
                                        "in_window": win, "pulled": len(rows)}
        if not args.dry_run:
            out = ROOT / "data" / "raw" / f"arcgis-{cfg['id_prefix']}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rows, indent=2))
            print(f"  wrote {out.relative_to(ROOT)} ({len(rows):,} records)", flush=True)

    print("\n[funnel]")
    for j, s in summary.items():
        pct = s["commercial"] / s["total"] * 100 if s["total"] else 0
        print(f"  {j:<10} total={s['total']:>9,}  commercial={s['commercial']:>8,} ({pct:4.1f}%)  "
              f"in-window={s['in_window']:>7,}  pulled={s['pulled']:>6,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
