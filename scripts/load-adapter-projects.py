#!/usr/bin/env python3
"""Merge adapter output into the projects index. Step 2's missing half.

THE GAP. A1/A2/A5 each wrote data/raw/*.json and nothing read it. Measured:
Austin 2,000 records on disk and ZERO rows in projects; Raleigh 2,517 and zero.
The adapters worked, the pulls were real, and the index never moved -- the same
seam that left 78% of captured documents invisible downstream and that
project_csi_divisions sat empty for.

ADDITIVE AND ID-DEDUPED, NEVER A REPLACE. project_id is the natural key and
ON CONFLICT UPDATE refreshes a row in place. Nothing is deleted, so a rerun
cannot shrink the corpus.

A DECREASING COUNT IS A STOP-EVERYTHING SIGNAL, so the count is printed before
and after and the script exits non-zero if it fell. That has cost real data in
this repo before; it is cheaper to assert it than to discover it.

FIELDS ARE ONLY OVERWRITTEN WHEN THE NEW VALUE IS NON-NULL. An adapter that
cannot see a value column (Denver has no project cost, only a permit fee) must
not blank a value another source already supplied.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

COLS = ["project_id", "name", "city", "state", "county", "status",
        "opened_or_announced_date", "estimated_value_usd", "street_address"]

# projects.status is NOT NULL with a controlled vocabulary -- permitting,
# completed, under_construction, planning, bidding, cancelled. Portals emit
# their own words ("Issued", "Finaled", "In Review"), so passing them through
# would either violate the constraint or quietly invent a seventh status that
# every existing filter misses.
#
# Default is `permitting`: all three adapters read permit records, which is what
# 572,653 of the existing rows already are. Mapping to a status we cannot
# support -- "under_construction" from an issued permit -- would be a guess
# dressed as a fact.
_STATUS = {
    "issued": "permitting", "active": "permitting", "in review": "permitting",
    "pending": "permitting", "submitted": "permitting", "approved": "permitting",
    "finaled": "completed", "final": "completed", "closed": "completed",
    "complete": "completed", "completed": "completed", "co issued": "completed",
    "withdrawn": "cancelled", "cancelled": "cancelled", "canceled": "cancelled",
    "void": "cancelled", "expired": "cancelled", "revoked": "cancelled",
}


def money(raw):
    """projects.estimated_value_usd is BIGINT; sources send strings with
    decimals ("500000.0000") and occasionally junk. A failed cast aborts the
    whole load, and silently dropping the value is worse -- value is what the
    corpus ranks on. Coerce, and only give up when it truly is not a number.
    """
    if raw in (None, ""):
        return None
    try:
        v = int(round(float(str(raw).replace(",", "").replace("$", "").strip())))
    except (TypeError, ValueError):
        return None
    # Negative or absurd values are source errors, not projects. Miami-Dade once
    # reported $7.86B for a beauty-salon alteration.
    return v if 0 < v < 10_000_000_000 else None


def map_status(raw) -> str:
    s = (raw or "").strip().lower()
    if not s:
        return "permitting"
    for k, v in _STATUS.items():
        if k in s:
            return v
    return "permitting"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="data/raw/{socrata,arcgis,accela}-*.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = [Path(f) for f in args.files] or sorted(
        p for pat in ("socrata-*.json", "arcgis-*.json", "accela-*.json")
        for p in (ROOT / "data" / "raw").glob(pat))
    if not files:
        print("no adapter output found"); return 1

    # RECONNECT ON A DROPPED CONNECTION. Cloud SQL closed the connection under
    # three separate long jobs today -- the NYC backfill, the Legistar pull and
    # this loader. A load that dies at file 4 of 5 leaves the index half-moved
    # and reports a traceback, which is indistinguishable from "the adapter
    # found nothing" once the log scrolls.
    def db():
        for attempt in range(6):
            try:
                c = connect()
                c.cursor().execute("SELECT 1")
                return c
            except Exception:  # noqa: BLE001
                if attempt == 5:
                    raise
                time.sleep(5 * (attempt + 1))
        raise RuntimeError("unreachable")

    conn = db(); cur = conn.cursor()
    cur.execute("SELECT count(*) FROM projects")
    before = cur.fetchone()[0]
    print(f"[before] corpus {before:,} projects", flush=True)

    inserted = updated = skipped = 0
    for f in files:
        rows = json.loads(f.read_text())
        new_here = 0
        for r in rows:
            pid = (r.get("project_id") or "").strip()
            if not pid:
                skipped += 1
                continue
            if args.dry_run:
                continue
            cur.execute("SELECT 1 FROM projects WHERE project_id = %s", (pid,))
            exists = cur.fetchone() is not None
            cur.execute(
                """
                INSERT INTO projects
                    (project_id, name, city, state, county, status,
                     opened_or_announced_date, estimated_value_usd, street_address,
                     first_seen_at, last_updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now())
                ON CONFLICT (project_id) DO UPDATE SET
                    -- COALESCE(new, old): an adapter with no value column must
                    -- never blank a value another source already supplied.
                    name        = COALESCE(NULLIF(EXCLUDED.name, ''), projects.name),
                    city        = COALESCE(NULLIF(EXCLUDED.city, ''), projects.city),
                    county      = COALESCE(NULLIF(EXCLUDED.county, ''), projects.county),
                    status      = COALESCE(NULLIF(EXCLUDED.status, ''), projects.status),
                    opened_or_announced_date =
                        COALESCE(EXCLUDED.opened_or_announced_date, projects.opened_or_announced_date),
                    estimated_value_usd =
                        COALESCE(EXCLUDED.estimated_value_usd, projects.estimated_value_usd),
                    street_address =
                        COALESCE(NULLIF(EXCLUDED.street_address, ''), projects.street_address),
                    last_updated_at = now()
                """,
                (pid, r.get("name"), r.get("city"), r.get("state"), r.get("county"),
                 map_status(r.get("status")), r.get("opened_or_announced_date"),
                 money(r.get("estimated_value_usd")), r.get("street_address")),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
                new_here += 1
        try:
            conn.commit()
        except Exception:  # noqa: BLE001
            print(f"  connection lost committing {f.name} -- reconnecting", flush=True)
            conn = db(); cur = conn.cursor()
        print(f"  {f.name:<34}{len(rows):>7,} records, {new_here:>6,} new", flush=True)

    cur.execute("SELECT count(*) FROM projects")
    after = cur.fetchone()[0]
    print(f"\n[after] corpus {after:,} projects  (+{after - before:,})")
    print(f"[detail] inserted={inserted:,} updated={updated:,} skipped_no_id={skipped:,}")
    if after < before:
        print(f"STOP: corpus DECREASED {before:,} -> {after:,}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
