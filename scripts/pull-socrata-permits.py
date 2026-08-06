#!/usr/bin/env python3
"""A1 -- generic Socrata (SODA) permit client. One YAML config per dataset.

WHY GENERIC. Adapter-per-jurisdiction does not scale: the coverage plan lists 29
metro permit feeds and most run Socrata. The differences between them are field
NAMES and a commercial filter, which is configuration, not code. Adding a city
is a YAML file.

FIELD NAMES COME FROM THE DATASET METADATA, NEVER FROM A SAMPLE ROW. Seattle's
first record has no date fields at all -- they are null on that row -- so a
mapping inferred from `?$limit=1` silently drops issueddate, applieddate and
estprojectcost. `/api/views/<id>.json` lists all 40 columns with their types.
That is how the configs here were built.

A BROWSER USER-AGENT IS REQUIRED, not optional. Both data.seattle.gov and
data.austintexas.gov return a connection failure to a bare urllib client and 200
to the same request with a UA. Permitted under skill rule 2 (v2.1): these are
public, unauthenticated datasets and nothing is being bypassed.

EVERY RECORD CARRIES ITS SOURCE URL AND FETCH DATE, per skill rule 5.
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.parse, urllib.request, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAGE = 1000


def soda(domain: str, resource: str, params: dict, timeout: float = 90) -> list:
    url = f"https://{domain}/resource/{resource}.json?" + urllib.parse.urlencode(params, safe="$'()=,")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def count(cfg: dict, where: str) -> int:
    r = soda(cfg["domain"], cfg["resource"], {"$select": "count(1)", "$where": where})
    return int(r[0].get("count_1") or r[0].get("count") or 0)


def main() -> int:
    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+", help="paths to config/socrata/*.yaml")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    grand = {}

    for cpath in args.configs:
        cfg = yaml.safe_load(open(cpath))
        f = cfg["fields"]
        date_col = f["opened_date"]
        v = f["value"]
        vcols = v if isinstance(v, list) else [v]

        # Two controls, because a filter that silently does nothing returns MORE
        # rows and still looks like success.
        total = count(cfg, "1=1")
        commercial = count(cfg, cfg["commercial_filter"])
        windowed = count(cfg, f"{cfg['commercial_filter']} AND {date_col} >= '{args.since}'")
        print(f"[{cfg['jurisdiction']}] total={total:,}  commercial={commercial:,}  "
              f"commercial since {args.since}={windowed:,}", flush=True)
        if commercial >= total:
            print(f"  WARNING: commercial filter is inert ({commercial:,} >= {total:,})", flush=True)

        rows, offset = [], 0
        while offset < min(args.limit, windowed):
            batch = soda(cfg["domain"], cfg["resource"], {
                "$where": f"{cfg['commercial_filter']} AND {date_col} >= '{args.since}'",
                "$order": f"{date_col} DESC", "$limit": PAGE, "$offset": offset})
            if not batch:
                break
            for b in batch:
                pid = (b.get(f["permit_number"]) or "").strip()
                if not pid:
                    continue
                rows.append({
                    "project_id": f"{cfg['id_prefix']}-{pid.lower()}",
                    "name": (b.get(f["description"]) or "")[:500],
                    "city": b.get(f["city"]) or cfg["jurisdiction"],
                    "state": cfg["state"], "county": cfg["county"],
                    "status": b.get(f["status"]),
                    "opened_or_announced_date": (b.get(date_col) or "")[:10] or None,
                    # Coalesce across the config's value columns in order.
                    # Austin has no single well-populated valuation field, so a
                    # scalar mapping reports 9% coverage where the source can
                    # actually answer ~28%.
                    "estimated_value_usd": next(
                        (b.get(c) for c in vcols if b.get(c) not in (None, "")), None),
                    "street_address": b.get(f["address"]),
                    "zip": b.get(f["zip"]),
                    "latitude": b.get(f["latitude"]), "longitude": b.get(f["longitude"]),
                    # Rule 5: every record keeps where it came from and when.
                    "source_url": f"https://{cfg['domain']}/resource/{cfg['resource']}.json",
                    "fetched_at": fetched_at,
                })
            offset += PAGE
            time.sleep(args.pause)
            print(f"  [{cfg['jurisdiction']}] {len(rows):,} rows", flush=True)

        grand[cfg["jurisdiction"]] = {"total": total, "commercial": commercial,
                                      "in_window": windowed, "pulled": len(rows)}
        out = ROOT / "data" / "raw" / f"socrata-{cfg['id_prefix']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not args.dry_run:
            out.write_text(json.dumps(rows, indent=2))
            print(f"  wrote {out.relative_to(ROOT)} ({len(rows):,} records)", flush=True)

    print("\n[funnel]")
    for j, s in grand.items():
        pct = s["commercial"] / s["total"] * 100 if s["total"] else 0
        print(f"  {j:<10} total={s['total']:>9,}  commercial={s['commercial']:>8,} ({pct:4.1f}%)  "
              f"in-window={s['in_window']:>7,}  pulled={s['pulled']:>6,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
