"""Tests for the pure functions whose failures are SILENT.

This repo's defining failure mode is not a crash -- it is a plausible wrong
answer. A broken date filter returns MORE rows. A soft-404 returns HTTP 200. A
misclassified document ranks 5 instead of 1 and is dropped by a cap. An
expired credential reports "0 documents". Every one of those looked like
success.

So these tests target the functions where a wrong answer is invisible, and
each one encodes a defect that ACTUALLY OCCURRED rather than a hypothetical.

Run:  python3 -m pytest tests/ -q      (or)  python3 tests/test_pure_functions.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import document_classifier as dc          # noqa: E402
from specindex import dates as D          # noqa: E402


# --------------------------------------------------------------------------
# Dates. Real incident: data.nj.gov publishes permitdate 2925-08-15 for
# permit 25CP000942 (Plainfield). We ingested it faithfully and rendered it.
# --------------------------------------------------------------------------

def test_nj_2925_typo_is_caught_and_corrected():
    r = D.check("2925-08-15", identifier="25CP000942", upper_bound_date="2026-02-09")
    assert r["verdict"] == "out_of_bounds"
    assert D.suggest_correction("2925-08-15", "25CP000942", "2026-02-09") == "2025-08-15"


def test_legitimate_old_and_future_dates_are_NOT_flagged():
    # The over-correction risk: a naive 1990-2027 window would delete ~3,691
    # good rows to catch 2 bad ones. San Francisco digitises historical
    # planning records; NYC CPDB tracks long-range capital commitments.
    assert D.check("1985-04-11")["verdict"] == "ok"      # SF historical
    assert D.check("2035-06-01")["verdict"] == "ok"      # NYC CPDB planned
    assert D.check("2025-05-09")["verdict"] == "ok"


def test_ambiguous_typo_abstains_rather_than_guessing():
    # 2091 has several plausible single-digit repairs and nothing to
    # disambiguate. A confident wrong date is worse than a flagged one.
    assert D.suggest_correction("2091-06-23") is None


def test_identifier_year_and_relational_contradiction():
    assert D.year_from_identifier("25CP000942") == 2025
    assert D.year_from_identifier("99CP000123") == 1999
    # In-bounds but contradicted by the permit series.
    assert D.check("2028-05-09", identifier="25CP000942")["verdict"] == "contradicted"
    # 1-2 years of slack is normal: permits straddle year boundaries.
    assert D.check("2026-05-09", identifier="25CP000942")["verdict"] == "ok"


# --------------------------------------------------------------------------
# Document classification. Real defect: `\bamd\b` does not match "Amd_1.pdf"
# because underscore is a word character -- the file ranked 5 and would have
# been dropped by a download cap as low value.
# --------------------------------------------------------------------------

def test_amd_underscore_variants_rank_as_addenda():
    for name in ("Amd_1.pdf", "AMD 2.pdf", "amd3.pdf",
                 "AMEND0005_70Z08725.pdf", "Addendum 2.pdf"):
        assert dc.rank_of(dc.classify(name)) == 1, name


def test_amd_substring_does_not_false_positive():
    for name in ("Amdahl Corp Report.pdf", "camd_report.pdf"):
        assert dc.rank_of(dc.classify(name)) != 1, name


def test_page_text_overrides_a_lying_filename():
    # The D1 failure: SAM.gov serves Attachment_A.pdf that is really an
    # addendum. Filename-only classification drops it under a cap.
    assert dc.classify("Attachment_A.pdf", "", "ADDENDUM NO. 3\nThe following changes") == dc.ADDENDA
    assert dc.classify("Doc_001.pdf", "", "SECTION 23 05 00 - COMMON WORK RESULTS") == dc.SPEC_BOOK


def test_unknown_is_not_conflated_with_other():
    # "no signal" and "confirmed low value" must differ: the cap treats them
    # differently, and conflating them silently discards unclassified files.
    assert dc.classify_name("qqqq_zzz.pdf") == dc.UNKNOWN


def test_addenda_also_get_spec_extraction():
    # Addenda rewrite whole sections: "Delete Section 23 05 00 and replace".
    assert dc.wants_spec_extraction(dc.ADDENDA) is True
    assert dc.wants_spec_extraction(dc.DRAWINGS,
                                    "SECTION 26 05 19 - LOW-VOLTAGE CONDUCTORS") is True


def test_cap_drops_lowest_value_first():
    items = [{"name": n, "doc_class": dc.classify(n)} for n in
             ("Wage Determination.pdf", "Addendum 2.pdf", "Drawings Vol1.pdf",
              "Specifications.pdf", "Sign-in sheet.pdf")]
    kept, dropped = dc.apply_cap(items, 2)
    kept_names = {i["name"] for i in kept}
    assert "Addendum 2.pdf" in kept_names          # rank 1 always survives
    assert "Wage Determination.pdf" in {i["name"] for i in dropped}


def test_cap_is_stable_across_runs():
    # A non-deterministic cap would make two runs of one source disagree about
    # which documents exist.
    items = [{"name": f"f{i}.pdf", "doc_class": dc.OTHER} for i in range(10)]
    a, _ = dc.apply_cap(list(items), 4)
    b, _ = dc.apply_cap(list(items), 4)
    assert [i["name"] for i in a] == [i["name"] for i in b]


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL  {name}: {e}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{'FAILURES: ' + str(fails) if fails else 'all passed'}")
    sys.exit(1 if fails else 0)
