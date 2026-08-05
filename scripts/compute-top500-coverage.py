#!/usr/bin/env python3
"""Build data/top500-coverage.json: the top-500 US counties with what we hold.

Why this exists (2026-08-03): the coverage page shows counties we HAVE, which
answers "what did we collect" but not "how are we doing against the target."
The standing goal is breadth AND depth for the largest counties, so the number
that matters is per-county coverage measured against the population ranking --
including the counties with ZERO projects, which by definition never appear in
a table built from the corpus.

That gap hid real problems for a long time. A 560K-project corpus read as
healthy while Santa Clara (rank 18) held 1 in-window project and Broward
(rank 17) held 2 -- both misconfigurations, not thin sources.

Three inputs, joined on (county, state):
  * docs/us_counties_by_population.md -- rank + population (real Census data)
  * data/national-commercial-projects.json -- project counts, total and
    in-window (2025-01-01+, the standing pull anchor)
  * Postgres project_document_files -- document counts, the depth axis

Documents are the differentiator, not permit-metadata breadth, so a county with
projects and no documents is a partial win and is shown as such.

Output is a static JSON file read at build time by the Next.js coverage page --
no API deploy needed, same spirit as the existing build-time coverage fetch.

Usage:
    python3 scripts/compute-top500-coverage.py            # needs DATABASE_URL
    python3 scripts/compute-top500-coverage.py --no-docs  # skip document counts
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW_START = "2025-01-01"


def load_ranking(limit: int) -> list[dict]:
    """Rank/population from the Census-derived markdown."""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    src = ROOT / "docs" / "us_counties_by_population.md"
    for line in src.read_text().splitlines():
        m = re.match(
            r"\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*([A-Z]{2})\s*\|\s*([\d,]+)\s*\|", line
        )
        if not m:
            continue
        rank = int(m.group(1))
        if rank > limit:
            continue
        # Strip the "County"/"Parish"/"Borough" suffix so this joins to the
        # corpus, which stores the bare name ("Los Angeles", not "Los Angeles County").
        name = re.sub(r"\s+(County|Parish|Borough|Census Area|Municipality|City and Borough)$",
                      "", m.group(2).strip())
        key = (name.lower(), m.group(3))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"rank": rank, "county": name, "state": m.group(3),
                     "population": int(m.group(4).replace(",", ""))})
    rows.sort(key=lambda r: r["rank"])
    return rows


def load_projects() -> tuple[Counter, Counter]:
    corpus = json.loads((ROOT / "data" / "national-commercial-projects.json").read_text())
    # Federal award records (sam_gov / usaspending) are statewide and carry no
    # county, so they can never match a county here anyway -- but skipping them
    # explicitly keeps this aligned with the permit_projects figure that
    # fast-merge-national-corpus.py now reports, rather than silently differing
    # from the headline by ~16,000 rows.
    federal_feeds = {"usaspending", "sam"}
    total: Counter = Counter()
    in_window: Counter = Counter()
    for p in corpus["projects"]:
        parts = (p.get("id") or "").split("-")
        if len(parts) > 1 and parts[1] in federal_feeds:
            continue
        c = (p.get("county") or "").strip().lower()
        s = (p.get("state") or "").strip().upper()
        if not c:
            continue
        total[(c, s)] += 1
        if str(p.get("opened_or_announced_date") or "") >= WINDOW_START:
            in_window[(c, s)] += 1
    return total, in_window


def load_documents() -> Counter:
    """Document counts per county. Returns empty on any failure -- the page is
    still useful without the depth column, and a missing DB should not block
    regenerating breadth numbers."""
    docs: Counter = Counter()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("  DATABASE_URL not set -- document counts will be 0", file=sys.stderr)
        return docs
    try:
        import psycopg2  # noqa: PLC0415

        conn = psycopg2.connect(url, connect_timeout=20)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.county, p.state, COUNT(*)
                  FROM project_document_files f
                  JOIN projects p ON p.project_sk = f.project_sk
                 WHERE p.county IS NOT NULL AND p.county <> ''
                 GROUP BY 1, 2
                """
            )
            for county, state, n in cur.fetchall():
                docs[(county.strip().lower(), (state or "").strip().upper())] = n
        conn.close()
    except Exception as e:  # noqa: BLE001
        print(f"  document counts unavailable ({type(e).__name__}) -- continuing", file=sys.stderr)
    return docs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--no-docs", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "data" / "top500-coverage.json"),
                    help="Output path. NOT a state file -- this writes a new "
                         "report, and must never point at data/states/*.json.")
    args = ap.parse_args(argv)

    ranking = load_ranking(args.limit)
    print(f"ranking rows: {len(ranking)}")
    total, in_window = load_projects()
    docs = Counter() if args.no_docs else load_documents()

    out = []
    for r in ranking:
        k = (r["county"].lower(), r["state"])
        proj = total.get(k, 0)
        win = in_window.get(k, 0)
        ndocs = docs.get(k, 0)
        # A county is only fully "covered" when it has BOTH in-window projects
        # and real documents -- metadata breadth alone is the axis Shovels.ai
        # already owns, so it is a partial win by design, not an oversight.
        if win == 0:
            status = "none"
        elif ndocs == 0:
            status = "projects-only"
        else:
            status = "covered"
        out.append({**r, "projects": proj, "projects_in_window": win,
                    "documents": ndocs, "status": status})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_start": WINDOW_START,
        "counties": out,
        "summary": {
            "total": len(out),
            "covered": sum(1 for r in out if r["status"] == "covered"),
            "projects_only": sum(1 for r in out if r["status"] == "projects-only"),
            "none": sum(1 for r in out if r["status"] == "none"),
            "total_projects_in_window": sum(r["projects_in_window"] for r in out),
            "total_documents": sum(r["documents"] for r in out),
        },
    }
    Path(args.out).write_text(json.dumps(payload, indent=2) + "\n")
    s = payload["summary"]
    print(f"\ntop {len(out)} counties:")
    print(f"  covered (projects + documents): {s['covered']}")
    print(f"  projects only (no documents)  : {s['projects_only']}")
    print(f"  no in-window projects         : {s['none']}")
    print(f"  in-window projects            : {s['total_projects_in_window']:,}")
    print(f"  documents                     : {s['total_documents']:,}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
