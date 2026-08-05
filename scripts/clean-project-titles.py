#!/usr/bin/env python3
"""Phase 1.5 -- strip order/RFP/solicitation numbers from project titles.

The identifier is MOVED, not deleted: it lands in project_enrichment as a
compliance fact, where EO 14398 is genuinely useful information about that
contract rather than noise in a building name.

Usage:
  python3 scripts/clean-project-titles.py --dry-run
  python3 scripts/clean-project-titles.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db, titles as T  # noqa: E402

LABELS = {"executive_order": "Executive order", "solicitation": "Solicitation",
          "rfp": "Solicitation", "contract": "Contract", "project_no": "Project number",
          "gov_id": "Source identifier"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT project_sk, project_id, name FROM projects WHERE name IS NOT NULL AND name <> ''")
    rows = cur.fetchall()

    changed, kept = [], []
    for sk, pid, name in rows:
        cleaned, found = T.clean_title(name)
        if not found:
            continue
        (changed if cleaned != name else kept).append((sk, pid, name, cleaned, found))

    print(f"titles scanned : {len(rows):,}")
    print(f"carry an identifier: {len(changed) + len(kept):,}")
    print(f"  cleanable    : {len(changed):,}")
    print(f"  kept as-is   : {len(kept):,}  (cleaning would empty the title)")
    print("\nsample:")
    for _, pid, old, new, f in changed[:8]:
        print(f"   {old[:48]:<50} -> {new[:38]:<40} {list(f.values())}")

    if args.dry_run:
        print("\nDRY RUN -- nothing written")
        return 0

    n = 0
    for sk, pid, old, new, found in changed:
        cur.execute("UPDATE projects SET name = %s WHERE project_sk = %s", (new, sk))
        # The identifier survives as a compliance fact rather than being lost.
        cur.execute("""
            INSERT INTO project_enrichment
              (project_sk, section, field_key, field_label, field_value,
               confidence, sources, assertion_status, coverage_basis, coverage_ref)
            VALUES (%s,'compliance',%s,%s,%s,'confirmed',
                    'Extracted from the source-supplied project title','named',
                    'source_title',%s)
            ON CONFLICT (project_sk, section, field_key) DO UPDATE
              SET field_value = EXCLUDED.field_value
        """, (sk, "title_identifiers",
              ", ".join(LABELS.get(k, k) for k in found),
              "; ".join(f"{LABELS.get(k, k)}: {v}" for k, v in found.items()),
              json.dumps({"original_title": old, "identifiers": found})))
        n += 1
        if n % 100 == 0:
            conn.commit()
            print(f"  ...{n:,}/{len(changed):,}", flush=True)
    conn.commit()
    print(f"\ncleaned {n:,} titles; identifiers preserved as compliance facts")
    print("TITLE CLEAN COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
