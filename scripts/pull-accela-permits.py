#!/usr/bin/env python3
"""A5 -- generic Accela Citizen Access adapter. One YAML per tenant.

WHY THIS IS THE HIGHEST-LEVERAGE ADAPTER. Accela Citizen Access runs 900-1,500
agencies on one URL pattern, and it is where the metros with NO open data live:
Dallas (its Socrata feed froze in Aug 2020), Houston-area agencies, Clark County
NV (which publishes nothing at all, including the Strip), King County WA outside
Seattle city limits, Maricopa-area cities.

THIS GENERALISES pull-ga-accela-commercial.py RATHER THAN REPLACING IT. That
script already solved the hard parts against live portals, and its AGENCIES
constant is a hardcoded list of exactly what a config file should hold. Rewriting
from scratch would re-derive the same defects:

  * ACA is an ASP.NET WebForms app driven by __VIEWSTATE and __doPostBack, so a
    plain GET of a search URL returns the empty form. Every request must carry
    the form state parsed from the previous response.
  * The HTML search caps at 10 rows per page and refuses to page past ~100
    records, so a wide date range silently truncates. The fix is DATE WINDOWING:
    7-day windows, subdivided to single days whenever the "showing N of M"
    total exceeds the rows actually returned. That check is the only thing
    standing between a full pull and a quiet 100-record ceiling.
  * The portal 403s non-browser clients, so browser headers are required --
    permitted under skill rule 2 (v2.1) since these are public, unauthenticated
    record searches. No account is created, nothing is submitted.

CONFIG IS DELIBERATELY THIN. host/path/county/default_city is all that differs
between tenants; the permit-type list is discovered per tenant from the form,
because "commercial" is spelled differently in every jurisdiction.
"""
from __future__ import annotations
import argparse, datetime as dt, importlib.util, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Load the Georgia module by path (hyphens are not importable) and reuse its
# proven pieces: the session client, form parsing, type discovery, the windowed
# collector and the residential filter.
_spec = importlib.util.spec_from_file_location(
    "ga_accela", ROOT / "scripts" / "pull-ga-accela-commercial.py")
ga = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ga)


def main() -> int:
    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--until", default=None)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--primary-only", action="store_true",
                    help="only the top-level commercial permit types")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    start = dt.date.fromisoformat(args.since)
    end = dt.date.fromisoformat(args.until) if args.until else dt.date.today()
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    summary = {}

    for cpath in args.configs:
        cfg = yaml.safe_load(open(cpath))
        agency_url = cfg["host"].rstrip("/") + cfg["path"]
        print(f"[{cfg['jurisdiction']}] {agency_url}", flush=True)

        client = ga.AccelaClient(cfg["host"], cfg["path"])
        try:
            home = client._get()
        except Exception as e:  # noqa: BLE001
            # DISTINGUISH OUR BUG FROM THEIR PORTAL. The first version called a
            # method that does not exist and reported Dallas as a "dead link" --
            # a portal that had answered with a valid __VIEWSTATE minutes
            # earlier. Logging our own AttributeError as a source failure is how
            # a live source gets written off, so an internal error is named as
            # one and never as a blocker.
            kind = "adapter error" if isinstance(e, (AttributeError, TypeError, NameError)) \
                   else "dead link"
            print(f"  {kind}: {type(e).__name__}: {e}", flush=True)
            summary[cfg["jurisdiction"]] = {"types": 0, "records": 0, "status": kind}
            continue

        # Permit types come from the tenant's own form. "Commercial" is spelled
        # differently everywhere, so a hardcoded list would silently miss most
        # of them.
        types = ga.commercial_permit_types(home, primary_only=args.primary_only)
        print(f"  commercial permit types offered: {len(types)}", flush=True)
        for _, label in types[:6]:
            print(f"    {label[:70]}", flush=True)
        if not types:
            summary[cfg["jurisdiction"]] = {"types": 0, "records": 0,
                                            "status": "no commercial types in form"}
            continue

        seen: set[str] = set()
        rows: list[dict] = []
        for value, label in types:
            try:
                got = ga.collect_type(client, cfg["host"], value, label, start, end, seen)
            except Exception as e:  # noqa: BLE001
                print(f"    [{label[:40]}] failed: {type(e).__name__}", flush=True)
                continue
            kept = [r for r in got if not ga.is_residential_record(r)]
            rows.extend(kept)
            print(f"    [{label[:44]:<46}] {len(got):>4} found, {len(kept):>4} commercial",
                  flush=True)
            time.sleep(args.pause)

        # NORMALISE TO THE SHARED PROJECT SCHEMA. The reused Georgia collector
        # returns its own shape (record_number / cells / detail_url), which is
        # right for that script and wrong for the corpus -- A1 and A2 both write
        # project_id / name / opened_or_announced_date / street_address. Three
        # adapters writing three shapes is three loaders to maintain, and the
        # brief is explicit that results go to the SHARED schema.
        #
        # `cells` is the search-results row in portal column order:
        #   [date, record_number, permit_type, address, status, ...]
        # Positions are read defensively -- a tenant with a different column
        # layout must yield a null, never a value from the wrong column.
        norm = []
        for r in rows:
            cells = r.get("cells") or []
            def cell(i):
                v = cells[i].strip() if len(cells) > i and cells[i] else ""
                return v or None
            raw_date = cell(0)
            iso = None
            if raw_date:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        iso = dt.datetime.strptime(raw_date, fmt).date().isoformat()
                        break
                    except ValueError:
                        continue
            rec = (r.get("record_number") or "").strip()
            if not rec:
                continue
            norm.append({
                "project_id": f"{cfg['id_prefix']}-{rec.lower()}",
                "name": r.get("permit_type") or "",
                "city": r.get("city") or cfg.get("default_city"),
                "state": cfg["state"], "county": cfg["county"],
                "status": cell(4),
                "opened_or_announced_date": iso,
                "street_address": cell(3),
                # No value column in ACA search results. Stated absent rather
                # than filled from an adjacent column that happens to be numeric.
                "estimated_value_usd": None,
                "permit_type": r.get("permit_type"),
                "detail_url": r.get("detail_url"),
                "source_url": agency_url,          # rule 5: cite the source
                "fetched_at": fetched_at,
            })
        rows = norm

        summary[cfg["jurisdiction"]] = {"types": len(types), "records": len(rows),
                                        "status": "ok"}
        if not args.dry_run and rows:
            out = ROOT / "data" / "raw" / f"accela-{cfg['id_prefix']}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rows, indent=2))
            print(f"  wrote {out.relative_to(ROOT)} ({len(rows):,} records)", flush=True)

    print("\n[funnel]")
    for j, s in summary.items():
        print(f"  {j:<16} types={s['types']:>3}  commercial_records={s['records']:>6}  {s['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
