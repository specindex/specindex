#!/usr/bin/env python3
"""Backfill street address and BBL onto NYC DOB projects.

THE BLOCKER THIS REMOVES. 209,978 NYC DOB projects -- 43% of the in-window
zero-document gap -- carry NO address of any kind. `name` and `description` hold
the WORK description ("INSTALLATION OF ONE THRU THE WALL AC UNIT"), zip is
empty, lat/lon is null, external_ids is null. So a Legistar land-use document
titled

    "310 East 4th Street, Block 373, Lot 8, Manhattan"

has nothing to join against, and the 149 NYC documents already captured cannot
be attached to anything. Matching was proposed on the assumption the address was
there; checking first showed it was not.

THE SOURCE HAS IT ALL ALONG: NYC Open Data ic3t-wcy2 exposes house__,
street_name, block, lot, bin__ and borough per job filing. Our ingestion simply
did not map them. So this is a backfill keyed on the job number already in
project_id, not a re-pull, and it cannot create or destroy projects.

BBL IS THE REAL KEY, NOT THE STREET STRING. Borough-Block-Lot is the canonical
NYC parcel identifier and it is what Legistar titles quote. Street matching is
fuzzy and full of "E 4th St" vs "East 4th Street"; BBL is exact. Both are
stored -- BBL for the join, street for display and for the record page's
location line, which currently has nothing to show.
"""
from __future__ import annotations
import argparse, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

# DOB NOW Build -- Job Application Filings. NOT ic3t-wcy2 (BIS Job Application
# Filings), which was the first attempt: its job__ is a numeric BIS number
# ("100321046") while our project_ids carry DOB NOW filing numbers with a
# borough letter ("b00005342-p2"). Different numbering systems, so that backfill
# would have scanned for hours and reported updated=0 -- a confident zero that
# reads as "the source has no addresses" rather than "wrong dataset".
#
# Verified before writing this: 6 of 6 randomly drawn real project_ids joined
# exactly, e.g. ny-nycdob-kings-b01122409-s2 -> 266 BANKER STREET, Blk 2592
# Lot 26, Brooklyn.
SODA = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"
UA = "SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"
BORO_CODE = {"MANHATTAN": "1", "BRONX": "2", "BROOKLYN": "3",
             "QUEENS": "4", "STATEN ISLAND": "5"}

def get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001
        print(f"  [api] {type(e).__name__}", flush=True); return []

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200000)
    ap.add_argument("--page", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = connect(); cur = conn.cursor()
    if not args.dry_run:
        cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS street_address text")
        cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS bbl text")
        cur.execute("CREATE INDEX IF NOT EXISTS projects_bbl_idx ON projects (bbl) WHERE bbl IS NOT NULL")
        conn.commit()

    cur.execute("SELECT count(*) FROM projects WHERE project_id LIKE 'ny-nycdob-%%'")
    total_before = cur.fetchone()[0]
    print(f"[scope] {total_before:,} NYC DOB projects", flush=True)

    updated = seen = 0; offset = 0; t0 = time.time()
    while offset < args.limit:
        q = urllib.parse.urlencode({
            "$select": "job_filing_number,borough,house_no,street_name,block,lot,bin",
            "$limit": args.page, "$offset": offset, # DESCENDING. Ascending pulls the oldest filings first, and our corpus is
            # anchored at 2025-01-01 -- a 500-row ascending test returned
            # updated=0 and looked like a broken join when it was simply
            # scanning filings we do not hold. The same SQL matched 1/1 on a
            # known-current project.
            "$order": "job_filing_number DESC"})
        rows = get(f"{SODA}?{q}")
        if not rows:
            break
        # ONE statement per page, joined on an indexed key -- not one UPDATE per
        # source row. The first version issued a LIKE with a LEADING WILDCARD
        # per row against 209,978 projects: a full table scan each time, 1,000
        # per page. It burned 8 minutes producing no output and would never
        # have finished.
        batch = []
        for r in rows:
            seen += 1
            jfn = (r.get("job_filing_number") or "").strip().lower()
            if not jfn:
                continue
            house = (r.get("house_no") or "").strip()
            street = (r.get("street_name") or "").strip()
            addr = f"{house} {street}".strip() or None
            boro = (r.get("borough") or "").strip().upper()
            blk, lot = (r.get("block") or "").strip(), (r.get("lot") or "").strip()
            bbl = None
            if BORO_CODE.get(boro) and blk.isdigit() and lot.isdigit():
                bbl = f"{BORO_CODE[boro]}{int(blk):05d}{int(lot):04d}"
            if not addr and not bbl:
                continue
            batch.append((jfn, addr, bbl, (r.get("bin") or "").strip() or None))

        if args.dry_run:
            for b in batch[:5]:
                print(f"  {b[0]}: addr={b[1]!r} bbl={b[2]} bin={b[3]}", flush=True)
        elif batch:
            # project_id is 'ny-nycdob-[<county>-]<jfn>'. Match on the SUFFIX,
            # which is anchored on the right, so the index-friendly form is a
            # join against a VALUES list rather than a per-row scan.
            cur.execute("""
                UPDATE projects p
                   SET street_address = COALESCE(v.addr, p.street_address),
                       bbl            = COALESCE(v.bbl,  p.bbl),
                       last_updated_at = now()
                  FROM (VALUES %s) AS v(jfn, addr, bbl, bin)
                 WHERE p.project_id = 'ny-nycdob-' || v.jfn
                    OR p.project_id LIKE 'ny-nycdob-%%-' || v.jfn
            """ % ",".join(cur.mogrify("(%s,%s,%s,%s)", b).decode() for b in batch))
            updated += cur.rowcount

        conn.commit()
        offset += args.page
        el = time.time()-t0
        print(f"[{seen:,} source rows] updated={updated:,} {seen/el*60 if el else 0:,.0f} rows/min", flush=True)
        if len(rows) < args.page:
            break

    cur.execute("SELECT count(*) FROM projects WHERE project_id LIKE 'ny-nycdob-%%'")
    total_after = cur.fetchone()[0]
    # In --dry-run the columns were never added, so asking about them errors --
    # a crash at the end of a successful dry run reads as a failure of the run.
    with_bbl = 0
    if not args.dry_run:
        cur.execute("SELECT count(*) FROM projects WHERE bbl IS NOT NULL")
        with_bbl = cur.fetchone()[0]
    print(f"\n[done] source rows={seen:,} updated={updated:,}")
    print(f"[verify] projects with BBL: {with_bbl:,}")
    print(f"[verify] NYC project count {total_before:,} -> {total_after:,} "
          f"{'UNCHANGED - OK' if total_before==total_after else 'CHANGED - STOP'}")
    return 0 if total_before == total_after else 1

if __name__ == "__main__":
    raise SystemExit(main())
