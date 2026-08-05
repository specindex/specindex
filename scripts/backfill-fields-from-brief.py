#!/usr/bin/env python3
"""Phase 1.1 -- populate empty structured fields from the generated brief.

THE DEFECT. On the live record for B28, square_footage renders "Not reported"
while the executive brief four inches below says "approximately 175,000 gross
square feet across five stories". Location renders ", Georgia" while the brief
names Atlanta, DeKalb County. The data is ON THE PAGE, just not in the field.

WHY IT HAPPENS. Structured fields are set at INGEST (scripts/pull-*.py). The
brief is written later by enrich-project-details.py (step 10). Nothing ever
reads the brief back into the fields, so a value the system already discovered
and published in prose is simultaneously reported as missing.

MEASURED over 800 sampled briefs:
    city            235 recoverable  (29.4%)
    estimated_value  87 recoverable  (10.9%)
    square_footage   66 recoverable  ( 8.2%)

SCOPE, STATED HONESTLY: only 815 projects have a brief at all, out of 591,618.
This fixes those records completely and does nothing for the rest. It is worth
doing because those are the records a prospect is shown, not because it moves a
corpus-wide number.

REGEX, NOT A MODEL. The extraction is deterministic and quotes the exact phrase
that produced each value, so every backfilled field carries a verifiable trace
back to a span of text a human can check. An LLM pass here would cost money per
record to produce a less auditable answer to a question a regex answers exactly.

NEVER OVERWRITE. Only fields that are currently NULL/empty are touched. Ingest
data always wins -- a permit's own square footage is better evidence than a
sentence generated about it.

Usage:
  python3 scripts/backfill-fields-from-brief.py --dry-run
  python3 scripts/backfill-fields-from-brief.py --limit 50
  python3 scripts/backfill-fields-from-brief.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db  # noqa: E402

# "175,000 gross square feet", "20,000 sq. ft", "285,500 sf"
SF_RE = re.compile(
    r"([\d][\d,]{2,})\s*(?:gross\s+)?(?:square\s*(?:feet|foot)|sq\.?\s*ft\.?|sf)\b", re.I)
# "in Atlanta, DeKalb County" / "in Chamblee, GA"
CITY_RE = re.compile(
    r"\bin\s+([A-Z][a-zA-Z.'-]+(?:\s[A-Z][a-zA-Z.'-]+)?),\s*(?:[A-Z][a-zA-Z]+\s+County|[A-Z]{2}\b)")
VALUE_RE = re.compile(r"\$\s?([\d.,]+)\s*(million|billion|M|B)\b", re.I)

# A "city" that is actually a county or a state is a common false positive --
# "in DeKalb County, Georgia" would otherwise set city='DeKalb County'.
CITY_REJECT = re.compile(r"\b(county|parish|borough|state|region|district)\b", re.I)

# Sanity bounds, same discipline as the value/date validators: a backfill that
# writes an implausible number is worse than leaving the field empty, because
# it looks authoritative.
SF_MIN, SF_MAX = 100, 10_000_000
VAL_MIN, VAL_MAX = 1_000, 2_000_000_000


def sf_from(brief: str):
    for m in SF_RE.finditer(brief):
        try:
            n = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if SF_MIN <= n <= SF_MAX:
            return n, m.group(0)
    return None, None


def city_from(brief: str):
    for m in CITY_RE.finditer(brief):
        c = m.group(1).strip()
        if CITY_REJECT.search(c) or len(c) < 3:
            continue
        return c, m.group(0)
    return None, None


def value_from(brief: str):
    for m in VALUE_RE.finditer(brief):
        try:
            n = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = m.group(2).lower()
        n = int(n * (1_000_000_000 if unit in ("billion", "b") else 1_000_000))
        if VAL_MIN <= n <= VAL_MAX:
            return n, m.group(0)
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = db.connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.project_sk, p.project_id, p.square_footage, p.city,
               p.estimated_value_usd, e.field_value
        FROM project_enrichment e
        JOIN projects p ON p.project_sk = e.project_sk
        WHERE e.section = 'executive_brief' AND e.field_value IS NOT NULL
        ORDER BY p.project_sk
    """)
    rows = cur.fetchall()
    if args.limit:
        rows = rows[: args.limit]
    print(f"briefs to scan: {len(rows):,}")

    updates, traces = [], []
    for sk, pid, sf, city, val, brief in rows:
        sets, trace = {}, {}
        if not sf:
            v, phrase = sf_from(brief)
            if v:
                sets["square_footage"] = v
                trace["square_footage"] = phrase
        if not (city or "").strip():
            v, phrase = city_from(brief)
            if v:
                sets["city"] = v
                trace["city"] = phrase
        if not val:
            v, phrase = value_from(brief)
            if v:
                sets["estimated_value_usd"] = v
                trace["estimated_value_usd"] = phrase
        if sets:
            updates.append((sk, pid, sets))
            traces.append((sk, trace))

    print(f"projects with at least one recoverable field: {len(updates):,}")
    by_field: dict[str, int] = {}
    for _, _, s in updates:
        for k in s:
            by_field[k] = by_field.get(k, 0) + 1
    for k, n in sorted(by_field.items(), key=lambda kv: -kv[1]):
        print(f"   {k:<22}{n:,}")

    print("\nsample (value <- the phrase that produced it):")
    for (sk, pid, sets), (_, tr) in list(zip(updates, traces))[:6]:
        for k, v in sets.items():
            print(f"   {pid[:40]:<42}{k:<20}{str(v)[:16]:<18}<- {tr[k][:40]!r}")

    if args.dry_run:
        print("\nDRY RUN -- nothing written")
        return 0

    n = 0
    for (sk, pid, sets), (_, tr) in zip(updates, traces):
        cols = ", ".join(f"{k} = %s" for k in sets)
        cur.execute(f"UPDATE projects SET {cols} WHERE project_sk = %s",
                    [*sets.values(), sk])
        # The trace is the point. Every backfilled field records WHICH PHRASE
        # produced it, so the record page can show the provenance and a wrong
        # value can be traced to the sentence that caused it rather than
        # appearing as an unexplained fact.
        cur.execute("""
            INSERT INTO project_enrichment
              (project_sk, section, field_key, field_label, field_value,
               confidence, sources, assertion_status, coverage_basis, coverage_ref)
            VALUES (%s,'field_backfill',%s,%s,%s,'reported',
                    'Backfilled from the generated executive brief','named',
                    'executive_brief',%s)
            ON CONFLICT (project_sk, section, field_key) DO UPDATE
              SET field_value = EXCLUDED.field_value,
                  coverage_ref = EXCLUDED.coverage_ref
        """, (sk, "backfill_trace", "Backfilled from brief",
              json.dumps({k: {"value": str(v), "phrase": tr[k]} for k, v in sets.items()}),
              json.dumps({"source": "executive_brief", "fields": list(sets)})))
        n += 1
        if n % 100 == 0:
            conn.commit()
            print(f"  ...{n:,}/{len(updates):,}", flush=True)
    conn.commit()
    print(f"\nbackfilled {n:,} projects")
    print("BACKFILL COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
