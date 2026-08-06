#!/usr/bin/env python3
"""Write the city onto NYC DOB rows that never got one.

THE FINDING. 213,199 New York projects carry a blank city, which is 43% of the
in-window zero-document gap and the single biggest blocker on city-based
document crawling -- a crawler keyed on city simply cannot see them.

They are not missing their jurisdiction. 209,978 of them come from one source,
NYC DOB, and their county is 100% populated with exactly the five New York City
boroughs:

    New York   116,359      Bronx      20,732
    Kings       44,078      Richmond    4,370
    Queens      24,439

Every one of those boroughs IS New York City. The city was never missing from
the source; the loader never wrote it. So this is a relabel from data already
held -- the endorsed repair -- not a re-pull and emphatically not a delete.

DELIBERATELY NARROW. Only rows matching ALL of: state NY, blank city, a
`ny-nycdob-` project_id, and a county in the five-borough list. The residue is
left alone on purpose:

    Erie 2,791    Buffalo is the obvious guess and a guess is exactly what this
                  script must not make. A county is not a city; Erie County
                  contains Buffalo plus dozens of other municipalities, and
                  writing "Buffalo" onto all of them would be inventing a fact
                  that then looks indistinguishable from a sourced one.
    430 blank     no county either; nothing to derive from.

REVERSIBLE BY CONSTRUCTION. The predicate that selects the rows also identifies
them afterwards, so the change can be undone exactly. Counts are printed before
and after and the row count must not change -- a shrinking corpus is a
stop-everything signal.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from specindex.db import connect  # noqa: E402

BOROUGHS = ("New York", "Kings", "Queens", "Bronx", "Richmond")

PREDICATE = """
    state = 'NY'
    AND (city IS NULL OR city = '')
    AND project_id LIKE 'ny-nycdob-%%'
    AND county = ANY(%s)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the change; default is a dry run")
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM projects")
    total_before = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM projects WHERE {PREDICATE}", ([*BOROUGHS],))
    target = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM projects WHERE state='NY' AND (city IS NULL OR city='')")
    blank_before = cur.fetchone()[0]

    print(f"corpus rows            {total_before:>10,}")
    print(f"NY blank-city rows     {blank_before:>10,}")
    print(f"  -> will be relabeled {target:>10,}  (NYC DOB, five boroughs)")
    print(f"  -> left alone        {blank_before - target:>10,}  (Erie + no-county residue)")

    if not args.apply:
        print("\nDRY RUN -- nothing written. Re-run with --apply.")
        return 0

    cur.execute(
        f"UPDATE projects SET city = 'New York', last_updated_at = now() WHERE {PREDICATE}",
        ([*BOROUGHS],),
    )
    changed = cur.rowcount
    conn.commit()

    cur.execute("SELECT count(*) FROM projects")
    total_after = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM projects WHERE state='NY' AND (city IS NULL OR city='')")
    blank_after = cur.fetchone()[0]

    print(f"\nrelabeled              {changed:>10,}")
    print(f"NY blank-city now      {blank_after:>10,}")
    print(f"corpus rows            {total_after:>10,}")

    # A relabel must never change how many rows exist. If it did, something
    # other than an UPDATE ran and the result is not to be trusted.
    if total_after != total_before:
        print(f"\nSTOP: corpus count changed {total_before:,} -> {total_after:,}", file=sys.stderr)
        return 1
    print("row count unchanged -- OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
