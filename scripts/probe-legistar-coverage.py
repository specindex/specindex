#!/usr/bin/env python3
"""Measure how many priority jurisdictions expose a working Legistar API.

WHY. The Drupal-sitemap crawler found 1 viable county in 4, but that number was
partly an artefact of the probe: Cook County was recorded as "no candidate site
found" when cookcountyil.legistar.com plainly exists. The probe only understood
Drupal sitemaps, so it was structurally blind to Legistar -- the dominant US
municipal legislative platform -- and the 1-in-4 is therefore wrong in an
unknown direction.

Legistar is not a site to scrape. It is a REST API that returns meeting matters
and their attachment URLs directly:

    webapi.legistar.com/v1/detroit/matters                    -> 200, real matters
    webapi.legistar.com/v1/detroit/matters/3689/attachments   -> 200, PDF link

No sitemap parsing, no path repair, no per-city HTML. If the slugs resolve for a
decent share of priority counties, this beats the crawler outright.

THE SLUG IS THE WHOLE PROBLEM. `detroit` works; `chicago` and `cookcountyil`
return a config error and `nyc` returns 403. There is no published directory
mapping a jurisdiction to its Legistar client name, so this generates candidates
from the county and state and tests each. That guessing is exactly why this
script exists as a MEASUREMENT rather than as an assumption baked into a crawler.

A slug counts as working only if `/matters` returns HTTP 200 AND a non-empty
JSON array. A 500 with a LegistarConnectionString error is a wrong slug, not a
dead jurisdiction, and the two must not be conflated.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from specindex.db import connect  # noqa: E402

API = "https://webapi.legistar.com/v1"
UA = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"


def get(url: str, timeout: float = 20.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def slug_candidates(county: str, state: str, cities: list[str]) -> list[str]:
    """Plausible Legistar client names, most likely first.

    Real observed shapes: `detroit` (bare city), `cookcountyil` (county+state).
    Cities come from the corpus, so the biggest city in the county is tried --
    a county's construction documents usually sit with the city anyway.
    """
    base = re.sub(r"[^a-z]", "", county.lower().replace("county", ""))
    st = state.lower()
    out = [f"{base}county{st}", f"{base}{st}", base, f"{base}county"]
    for c in cities:
        cb = re.sub(r"[^a-z]", "", c.lower())
        if cb:
            out += [cb, f"{cb}{st}"]
    seen, uniq = set(), []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:8]


def test_slug(slug: str, pause: float) -> dict:
    st, body = get(f"{API}/{slug}/matters?$top=1")
    time.sleep(pause)
    if st != 200:
        return {"ok": False, "status": st}
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        return {"ok": False, "status": st}
    if not isinstance(data, list) or not data:
        return {"ok": False, "status": st}

    # Prove it actually yields a document, not just metadata.
    mid = data[0].get("MatterId")
    attach = 0
    link = ""
    if mid:
        ast_, abody = get(f"{API}/{slug}/matters/{mid}/attachments")
        time.sleep(pause)
        if ast_ == 200:
            try:
                arr = json.loads(abody)
                attach = len(arr)
                if arr:
                    link = arr[0].get("MatterAttachmentHyperlink", "") or ""
            except Exception:  # noqa: BLE001
                pass
    return {"ok": True, "status": 200, "attachments_on_first_matter": attach,
            "sample_link": link[:120]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--pause", type=float, default=0.4)
    ap.add_argument("--out", default="data/raw/legistar_coverage.json")
    args = ap.parse_args()

    cur = connect().cursor()
    cur.execute(
        """
        SELECT p.county, p.state, count(*) n,
               (array_agg(DISTINCT p.city) FILTER (WHERE p.city <> ''))[1:3]
        FROM projects p
        WHERE NOT EXISTS (SELECT 1 FROM project_document_files f
                          WHERE f.project_sk = p.project_sk)
          AND p.opened_or_announced_date >= '2025-01-01'
          AND p.county IS NOT NULL AND p.county <> '' AND p.state IS NOT NULL
        GROUP BY 1, 2 ORDER BY n DESC LIMIT %s
        """,
        (args.limit,),
    )
    rows = cur.fetchall()

    results, working = [], 0
    covered = 0
    for county, state, n, cities in rows:
        found = None
        for slug in slug_candidates(county, state, list(cities or [])):
            r = test_slug(slug, args.pause)
            if r["ok"]:
                found = {"slug": slug, **r}
                break
        rec = {"county": county, "state": state, "zero_doc_projects": n,
               "legistar": found}
        results.append(rec)
        if found:
            working += 1
            covered += n
            print(f"  [OK ] {county}, {state} ({n:,} proj) slug={found['slug']} "
                  f"attachments={found['attachments_on_first_matter']}", flush=True)
        else:
            print(f"  [ -- ] {county}, {state} ({n:,} proj) no working slug", flush=True)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    total = sum(r["zero_doc_projects"] for r in results)
    print(f"\n[done] {working}/{len(results)} jurisdictions on Legistar; "
          f"{covered:,} of {total:,} zero-doc projects ({covered/total*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
