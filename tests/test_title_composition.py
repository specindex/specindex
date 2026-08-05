"""CI assertion: no project title may contain an order/RFP/solicitation number.

From 01_build_order.md, assertion 3. The live record read "B28 High Containment
Lab Eo 14398" -- an executive-order number fused into a building name and
sentence-cased into "Eo". Titles are composed from whatever string the source
supplied, which for federal records is frequently a solicitation line rather
than a project name.

Titles that are ONLY an identifier are exempt: cleaning them leaves nothing,
and a blank title breaks the row, the tab title and every link. Those are
counted and reported so the exemption cannot quietly grow.

Run:  python3 tests/test_title_composition.py     (needs DATABASE_URL)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from specindex import db, titles as T  # noqa: E402

# Titles that are only an identifier and cannot be cleaned without emptying.
UNCLEANABLE_CEILING = 15


def scan():
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT project_id, name FROM projects WHERE name IS NOT NULL AND name <> ''")
    bad, uncleanable = [], []
    for pid, name in cur.fetchall():
        frag = T.title_has_identifier(name)
        if not frag:
            continue
        cleaned, _ = T.clean_title(name)
        (uncleanable if cleaned == name else bad).append((pid, name, frag))
    return bad, uncleanable


def test_no_title_contains_an_identifier():
    bad, _ = scan()
    assert not bad, (
        f"{len(bad)} title(s) contain an order/RFP/solicitation number and ARE "
        f"cleanable. First: {[(p, f) for p, _, f in bad[:3]]}. "
        "Fix: python3 scripts/clean-project-titles.py"
    )


def test_uncleanable_titles_do_not_grow():
    _, unclean = scan()
    assert len(unclean) <= UNCLEANABLE_CEILING, (
        f"{len(unclean)} titles are nothing but an identifier (ceiling "
        f"{UNCLEANABLE_CEILING}). These cannot be cleaned without emptying them, "
        "so the source needs a real project name instead."
    )


if __name__ == "__main__":
    bad, unclean = scan()
    print(f"cleanable titles still carrying an identifier: {len(bad)}")
    for pid, name, frag in bad[:10]:
        print(f"   [{frag[:20]:<22}] {name[:48]}  ({pid[:30]})")
    print(f"uncleanable (identifier IS the title): {len(unclean)} (ceiling {UNCLEANABLE_CEILING})")
    for pid, name, frag in unclean[:5]:
        print(f"   {name[:52]}")
    raise SystemExit(1 if bad or len(unclean) > UNCLEANABLE_CEILING else 0)
