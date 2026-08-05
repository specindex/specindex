"""CI assertion: no scoring component may dominate or go inert.

Two failures this catches, both of which shipped and neither of which errored:

  INERT COMPONENT. news_score occupied 25 of 100 points and was non-zero on
  FIVE projects out of 591,618. A component that is zero nearly everywhere is
  not neutral -- it dilutes the components that work, because every project
  loses the same 25 points and the spread of the remaining 75 is compressed.

  DOMINANT COMPONENT. value_score is 71% of the average score today. A score
  that is mostly dollars is a sort the rep could have done unaided, and it is
  the specific thing a design review will call out.

The thresholds are deliberately loose. This is a smoke alarm for a component
that has stopped meaning anything, not a tuning target -- a score legitimately
weights its parts unevenly, and tightening this into a balance requirement
would produce churn rather than signal.

SPEC POSITION IS EXEMPT FROM THE INERT CHECK, on purpose. It is genuinely
near-zero right now (0.3% coverage) because document extraction has not run
across the corpus, not because it is broken. It is asserted separately: its
coverage must not go BACKWARDS, which would mean extraction regressed.

Run:  python3 tests/test_score_composition.py     (needs DATABASE_URL)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from specindex import db  # noqa: E402

# TARGET: no component above 60% of the average score. NOT MET TODAY --
# value_score is at 71%, which is a real condition and not a threshold to be
# argued away.
#
# The fix is COVERAGE, not tuning. Spec position is 45 of the 100 points and is
# non-zero on 0.3% of rows, so value dominates by default; running extraction
# across the corpus moves this without touching a single weight. Reweighting
# now would only redistribute value and recency and disguise the gap.
#
# So this asserts NO REGRESSION against a measured baseline rather than the
# target. A permanently-red test gets ignored, and an ignored assertion is
# worse than none -- but a silently-loosened one is worse still, so the target
# stays written down and the ceiling ratchets DOWN as coverage improves.
#
#   2026-08-05  value 71%   <- baseline recorded here
MAX_SHARE_TARGET = 0.60
MAX_SHARE = 0.75  # ratchet: lower this as spec-position coverage grows
# A component non-zero on fewer than this share of rows is inert and should be
# removed rather than left to dilute.
MIN_COVERAGE = 0.02
# Ratchet: spec-position coverage must never fall below what has been achieved.
MIN_POSITION_ROWS = 1_000


def composition():
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT count(*), avg(score),
               avg(value_score), avg(recency_score),
               avg(coalesce(position_score, 0)), avg(news_score),
               count(*) FILTER (WHERE value_score > 0),
               count(*) FILTER (WHERE recency_score > 0),
               count(*) FILTER (WHERE coalesce(position_score, 0) > 0)
        FROM project_scores
    """)
    (n, avg_total, av, ar, ap, an, cv, cr, cp) = cur.fetchone()
    return {
        "n": n, "avg_total": float(avg_total or 0),
        "components": {
            "value": {"avg": float(av or 0), "nonzero": cv},
            "recency": {"avg": float(ar or 0), "nonzero": cr},
            "position": {"avg": float(ap or 0), "nonzero": cp},
        },
        "news_avg": float(an or 0),
    }


def test_no_component_dominates():
    c = composition()
    for name, d in c["components"].items():
        share = d["avg"] / c["avg_total"] if c["avg_total"] else 0
        assert share <= MAX_SHARE, (
            f"{name} is {share:.0%} of the average score, past the {MAX_SHARE:.0%} "
            f"ceiling (target {MAX_SHARE_TARGET:.0%}). The ranking has become more "
            "single-axis, not less -- check spec-position coverage before "
            "raising this."
        )


def test_no_component_is_inert():
    c = composition()
    for name, d in c["components"].items():
        if name == "position":
            continue  # legitimately sparse today; ratcheted separately below
        cov = d["nonzero"] / c["n"] if c["n"] else 0
        assert cov >= MIN_COVERAGE, (
            f"{name} is non-zero on only {cov:.1%} of rows. An inert component "
            "dilutes the ones that work -- remove it or fix its input."
        )


def test_news_stays_removed():
    c = composition()
    assert c["news_avg"] == 0, (
        "news_score is contributing again. It fired on 5 of 591,618 projects "
        "and was removed from the composite; re-adding it needs new evidence."
    )


def test_spec_position_coverage_does_not_regress():
    c = composition()
    got = c["components"]["position"]["nonzero"]
    assert got >= MIN_POSITION_ROWS, (
        f"spec-position coverage fell to {got:,} rows (floor {MIN_POSITION_ROWS:,}). "
        "Extraction has regressed, or scores were recomputed without it."
    )


if __name__ == "__main__":
    c = composition()
    print(f"scored rows: {c['n']:,}   avg total: {c['avg_total']:.2f}\n")
    for name, d in c["components"].items():
        share = d["avg"] / c["avg_total"] if c["avg_total"] else 0
        cov = d["nonzero"] / c["n"] if c["n"] else 0
        flag = "  <- past target" if share > MAX_SHARE_TARGET else ""
        print(f"  {name:<10} avg {d['avg']:>6.2f}   {share:>5.0%} of score   "
              f"non-zero on {cov:>6.1%} of rows{flag}")
    print(f"\n  target: no component above {MAX_SHARE_TARGET:.0%}; "
          f"ratchet ceiling currently {MAX_SHARE:.0%}")
    print()
    fails = 0
    for fn in (test_no_component_dominates, test_no_component_is_inert,
               test_news_stays_removed, test_spec_position_coverage_does_not_regress):
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    raise SystemExit(1 if fails else 0)
