"""CI assertion: a field must never read "Not reported" when its value is on the page.

From 01_build_order.md, assertion 2. This is the test form of the defect on the
live B28 record: square_footage rendered "Not reported" while the executive
brief four inches below said "approximately 175,000 gross square feet across
five stories", and location rendered ", Georgia" while the brief named Atlanta.

The data was already discovered and published in prose, and simultaneously
reported as missing. That is worse than genuinely not knowing, because it tells
a prospect the index is thin when it is not.

Run:  python3 tests/test_no_not_reported.py            (needs DATABASE_URL)
      python3 tests/test_no_not_reported.py --sample 200
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "bf", ROOT / "scripts" / "backfill-fields-from-brief.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)

from specindex import db  # noqa: E402


def find_violations(sample: int = 200):
    """A violation is an EMPTY field whose value is recoverable from that same
    record's brief -- i.e. the page would render "Not reported" beside its own
    answer."""
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.project_id, p.square_footage, p.city, p.estimated_value_usd,
               e.field_value
        FROM project_enrichment e
        JOIN projects p ON p.project_sk = e.project_sk
        WHERE e.section = 'executive_brief' AND e.field_value IS NOT NULL
        ORDER BY p.project_sk
        LIMIT %s
    """, (sample,))
    out = []
    for pid, sf, city, val, brief in cur.fetchall():
        if not sf:
            v, phrase = bf.sf_from(brief)
            if v:
                out.append((pid, "square_footage", v, phrase))
        if not (city or "").strip():
            v, phrase = bf.city_from(brief)
            if v:
                out.append((pid, "city", v, phrase))
        if not val:
            v, phrase = bf.value_from(brief)
            if v:
                out.append((pid, "estimated_value_usd", v, phrase))
    return out


def test_no_field_is_empty_when_its_value_is_in_the_brief():
    v = find_violations(200)
    assert not v, (
        f"{len(v)} field(s) would render 'Not reported' while their value "
        f"appears in the same record's brief. First: {v[:3]}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200)
    a = ap.parse_args()
    viol = find_violations(a.sample)
    print(f"sampled {a.sample} records with a brief")
    if not viol:
        print("PASS - no field is empty while its value sits in the brief")
        raise SystemExit(0)
    print(f"FAIL - {len(viol)} recoverable empty field(s):")
    for pid, field, value, phrase in viol[:20]:
        print(f"   {pid[:40]:<42}{field:<20}{str(value)[:14]:<16}<- {phrase!r}")
    print("\nFix: python3 scripts/backfill-fields-from-brief.py")
    raise SystemExit(1)
