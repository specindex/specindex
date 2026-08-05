"""Date plausibility validation.

FOUND 2026-08-05 from two live project pages showing wrong years. Traced to
the SOURCE, not the parser: data.nj.gov's own NJ DCA permit dataset publishes

    permitno 25CP000942  PLAINFIELD  permitdate 2925-08-15  processdate 2026-02-09
    permitno 25CP000942  NEWARK      permitdate 2025-05-09  processdate 2025-06-09

New Jersey has a data-entry typo (9 for 0 -- adjacent keys). We ingested it
faithfully, which is correct behaviour for a pipeline and wrong behaviour for
a product that sells cited facts.

THE HARD PART IS NOT DETECTING BAD DATES. It is NOT destroying good ones.
Corpus-wide, 3,693 of 584,760 dated projects (0.63%) fall outside 1990-2027,
and they are three different things:

  1978-1989  (~3,196)  San Francisco + prior research -- LEGITIMATE. SF has
                       digitised decades of historical planning records.
  2028-2036  (~490)    NYC CPDB, mostly 2035-06-01 -- LEGITIMATE. The Capital
                       Planning Database exists to track long-term future
                       commitments.
  2091, 2925 (2)       Actual typos.

A naive "reject anything outside 1990-2027" would delete 3,691 good rows to
catch 2 bad ones. That is the over-correction risk, and it would be silent.

So: WIDE hard bounds (1970-2050) catch egregious typos only, and relational
checks do the rest of the work -- a date is suspect when it contradicts
another field on the same record, which is far stronger evidence than the
value alone.

NEVER SILENTLY REWRITE A DATE. Flag it, record the original and the evidence,
and let a human or an explicit repair job decide. A silently corrected date is
indistinguishable from a correct one, which is how a wrong fact becomes
permanent.
"""
from __future__ import annotations

import datetime as _dt
import re

# Deliberately generous. Narrow bounds would delete legitimate historical and
# long-range-planning records to catch a handful of typos.
HARD_MIN_YEAR = 1970
HARD_MAX_YEAR = 2050

# A permit/case number very often encodes its year: 25CP000942 -> 2025,
# B24-1234 -> 2024. This is the single strongest corroborating signal
# available, and it is free.
_ID_YEAR_RE = re.compile(r"^(?:[A-Za-z]{0,4}[-_ ]?)(\d{2})(?=[A-Za-z]{1,3}\d)")


def year_from_identifier(pid: str | None) -> int | None:
    """Extract a 2-digit year prefix from a permit/case number, if present."""
    if not pid:
        return None
    m = _ID_YEAR_RE.match(pid.strip())
    if not m:
        return None
    yy = int(m.group(1))
    # 00-69 -> 2000s, 70-99 -> 1900s. Same convention as the rest of the
    # industry's two-digit permit series.
    return 2000 + yy if yy <= 69 else 1900 + yy


def check(date_value, *, identifier: str | None = None,
          upper_bound_date=None, upper_bound_name: str = "processdate") -> dict:
    """Assess one date. Returns a verdict dict; never mutates anything.

    verdict:
      ok            -- inside hard bounds and consistent with corroborators
      out_of_bounds -- outside 1970-2050; an egregious typo
      contradicted  -- inside bounds but contradicted by another field
      unparseable
    """
    if date_value in (None, ""):
        return {"verdict": "missing", "value": None}
    d = date_value
    if isinstance(d, str):
        try:
            d = _dt.date.fromisoformat(d[:10])
        except Exception:  # noqa: BLE001
            return {"verdict": "unparseable", "value": date_value}
    if isinstance(d, _dt.datetime):
        d = d.date()

    out: dict = {"value": d.isoformat(), "verdict": "ok", "evidence": []}

    if not (HARD_MIN_YEAR <= d.year <= HARD_MAX_YEAR):
        out["verdict"] = "out_of_bounds"
        out["evidence"].append(f"year {d.year} outside {HARD_MIN_YEAR}-{HARD_MAX_YEAR}")

    id_year = year_from_identifier(identifier)
    if id_year and abs(id_year - d.year) > 2:
        # >2 years apart is a contradiction; permits do occasionally straddle a
        # year boundary, so 1-2 years of slack is normal and must not be flagged.
        out["evidence"].append(f"identifier implies {id_year}, date says {d.year}")
        if out["verdict"] == "ok":
            out["verdict"] = "contradicted"
        out["suggested_year"] = id_year

    if upper_bound_date:
        ub = upper_bound_date
        if isinstance(ub, str):
            try:
                ub = _dt.date.fromisoformat(ub[:10])
            except Exception:  # noqa: BLE001
                ub = None
        if isinstance(ub, _dt.datetime):
            ub = ub.date()
        if ub and d > ub:
            out["evidence"].append(f"date is after {upper_bound_name} {ub.isoformat()}")
            if out["verdict"] == "ok":
                out["verdict"] = "contradicted"

    return out


def suggest_correction(date_value, identifier: str | None = None,
                       upper_bound_date=None):
    """Propose a corrected date -- for review, NOT for silent application.

    Only ever changes the YEAR, and only when a corroborating source says so.
    Month and day are left alone because nothing corroborates them, and a
    'correction' without evidence is just a different wrong answer.
    """
    res = check(date_value, identifier=identifier, upper_bound_date=upper_bound_date)
    if res["verdict"] in ("ok", "missing", "unparseable"):
        return None
    d = _dt.date.fromisoformat(res["value"])
    target = res.get("suggested_year")
    if target is None and res["verdict"] == "out_of_bounds":
        # No identifier to lean on. Try the common single-digit typo: 2925 ->
        # 2025, 2091 -> 2021. Only accept a candidate that lands in bounds AND
        # respects the upper bound.
        cands = []
        s = str(d.year)
        for i, _ in enumerate(s):
            for repl in "0123456789":
                c = int(s[:i] + repl + s[i + 1:])
                if HARD_MIN_YEAR <= c <= HARD_MAX_YEAR:
                    cands.append(c)
        if upper_bound_date:
            ub = upper_bound_date
            if isinstance(ub, str):
                ub = _dt.date.fromisoformat(ub[:10])
            if isinstance(ub, _dt.datetime):
                ub = ub.date()
            cands = [c for c in cands if c <= ub.year]
        # Ambiguity is a reason to abstain, not to pick. Only a UNIQUE
        # single-digit repair is trustworthy enough to propose.
        target = max(cands) if len(set(cands)) == 1 else None
    if target is None:
        return None
    try:
        return d.replace(year=target).isoformat()
    except ValueError:      # Feb 29 into a non-leap year
        return None
