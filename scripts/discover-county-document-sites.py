#!/usr/bin/env python3
"""Find, for each priority county, a government site whose meeting/agenda pages
carry downloadable construction documents -- then prove it by downloading one.

WHY THIS EXISTS. crawl-municipal-events.py works, but only against a base URL
somebody supplied. Detroit was hand-fed. Scaling to 500 counties needs the base
URLs discovered and, more importantly, VERIFIED: the estimate that "top 100
cities cover 90%" silently assumes other jurisdictions look like Detroit, and
Detroit is a single 6-page sample. This script is what turns that assumption
into a measurement.

PRIORITISED BY OUR CORPUS, NOT BY POPULATION. docs/us_counties_by_population.md
is the authoritative Census ranking and is the right tie-breaker, but a county
where we hold 8,000 document-less projects is worth more than a larger one where
we hold 40. The ranking here is projects-we-hold first, population second.

A COUNTY IS ONLY 'VIABLE' IF A REAL PDF CAME BACK. Not if a URL resolved, not
if a page mentioned "agenda". Government hosts answer unknown paths with 200 and
their landing page, so viability requires: a sitemap or events index, a page
linking a .pdf, and that PDF downloading with a PDF magic number and differing
from the host's own soft-404 body. Anything less is recorded as a NEGATIVE
result with the reason, because a wrong "viable" costs a whole crawl run to
discover.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from specindex.db import connect  # noqa: E402

USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"
EVENT_HINT = re.compile(r"/events?/|/meetings?/|/agenda|/calendar|/board|/commission", re.I)


def get(url: str, timeout: float = 30.0) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, b"", ""
    except Exception:  # noqa: BLE001
        return 0, b"", ""


def priority_counties(limit: int) -> list[dict]:
    """Counties ranked by document-less projects we hold, population as tiebreak."""
    pop: dict[tuple[str, str], int] = {}
    doc = ROOT / "docs" / "us_counties_by_population.md"
    if doc.exists():
        for line in doc.read_text().splitlines():
            m = re.match(r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([A-Z]{2})\s*\|\s*([\d,]+)", line)
            if m:
                pop[(m.group(1).replace(" County", "").strip().lower(), m.group(2))] = int(
                    m.group(3).replace(",", "")
                )

    cur = connect().cursor()
    cur.execute(
        """
        SELECT p.county, p.state, count(*) AS n
        FROM projects p
        WHERE NOT EXISTS (SELECT 1 FROM project_document_files f
                          WHERE f.project_sk = p.project_sk)
          AND p.opened_or_announced_date >= '2025-01-01'
          AND p.county IS NOT NULL AND p.county <> '' AND p.state IS NOT NULL
        GROUP BY 1, 2
        ORDER BY n DESC
        """
    )
    out = []
    for county, state, n in cur.fetchall():
        key = (county.replace(" County", "").strip().lower(), state)
        out.append({"county": county, "state": state, "zero_doc_projects": n,
                    "population": pop.get(key, 0)})
    out.sort(key=lambda r: (-r["zero_doc_projects"], -r["population"]))
    return out[:limit]


def find_base_urls(client, types, model: str, county: str, state: str) -> list[str]:
    """Ask Google, through GCP, where this county publishes meeting documents."""
    prompt = (
        f"Search google for:\n"
        f"1. official government website for {county} County, {state} planning "
        f"commission or board of supervisors meeting agendas\n"
        f"2. the page where meeting agendas, staff reports and packets are posted\n\n"
        "Output ONLY the base site URLs (scheme + domain, no path), one per line, "
        "max 3, government domains only. No commentary."
    )
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )
    urls = []
    for m in re.finditer(r"https?://[a-zA-Z0-9.\-]+", resp.text or ""):
        root = m.group(0).rstrip("/")
        if root not in urls and not root.endswith(("google.com", "wikipedia.org")):
            urls.append(root)
    return urls[:3]


def probe(base: str, pause: float) -> dict:
    """Verify by download. Returns a result dict with an explicit reason on failure."""
    res = {"base": base, "viable": False, "reason": "", "sample_pdf": "", "event_urls": 0}

    st, body, _ = get(f"{base}/sitemap.xml")
    time.sleep(pause)
    candidates: list[str] = []
    if st == 200 and b"<loc>" in body:
        locs = re.findall(r"<loc>([^<]+)</loc>", body.decode("utf-8", "ignore"))
        subs = [x.split('"')[0] for x in locs if x.endswith(".xml")][:3]
        for s in subs:
            time.sleep(pause)
            s2, b2, _ = get(s)
            if s2 == 200:
                locs += re.findall(r"<loc>([^<]+)</loc>", b2.decode("utf-8", "ignore"))
        candidates = [u.split('"')[0] for u in locs if EVENT_HINT.search(u)]
        res["event_urls"] = len(candidates)
    if not candidates:
        res["reason"] = "no sitemap or no event/agenda URLs in it"
        return res

    # Soft-404 baseline: what this host serves for a path that cannot exist.
    _, base_body, _ = get(f"{base}/zzz-specindex-not-a-real-9174")
    time.sleep(pause)

    for page in candidates[:25]:
        time.sleep(pause)
        ps, pbody, _ = get(page)
        if ps != 200 or not pbody:
            continue
        for m in re.finditer(r'href="([^"]+\.pdf[^"]*)"', pbody.decode("utf-8", "ignore"), re.I):
            href = m.group(1)
            pdf = href if href.startswith("http") else urllib.parse.urljoin(base, href)
            time.sleep(pause)
            ds, dbody, _ = get(pdf)
            if ds == 200 and dbody[:5].startswith(b"%PDF") and dbody != base_body:
                res.update(viable=True, sample_pdf=pdf, reason="verified by download")
                return res
    res["reason"] = "event pages found but no downloadable PDF"
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--pause", type=float, default=1.2)
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--out", default="data/raw/county_document_sites.json",
                    help="NEVER point this at data/states/*.json")
    ap.add_argument("--sentinel", default=None)
    args = ap.parse_args()

    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    counties = priority_counties(args.limit)
    print(f"[scope] {len(counties)} counties, "
          f"{sum(c['zero_doc_projects'] for c in counties):,} zero-doc projects covered",
          flush=True)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(out_path.read_text()) if out_path.exists() else []
    done = {(r["county"], r["state"]) for r in results}

    viable = 0
    t0 = time.time()
    for i, c in enumerate(counties, 1):
        if (c["county"], c["state"]) in done:
            continue
        try:
            bases = find_base_urls(client, types, args.model, c["county"], c["state"])
        except Exception as e:  # noqa: BLE001
            print(f"  [search-error] {c['county']}, {c['state']}: {type(e).__name__}", flush=True)
            bases = []
        # Probe EVERY candidate, not just until the first one answers. Grounded
        # search is not deterministic: the pilot returned manhattanbp.nyc.gov for
        # New York County and marked it VIABLE by downloading a real PDF, then
        # the full run returned plain nyc.gov for the same county and marked it
        # not viable. Same county, opposite verdict, different day -- which makes
        # "0 viable" a statement about which URL the model happened to name, not
        # about the county. Trying all of them and keeping the best makes the
        # verdict depend on the jurisdiction instead of on the sampling.
        best = {"base": "", "viable": False, "reason": "no candidate site found",
                "sample_pdf": "", "event_urls": 0, "tried": []}
        for b in bases:
            r = probe(b, args.pause)
            best.setdefault("tried", []).append({"base": b, "reason": r["reason"]})
            if r["viable"]:
                r["tried"] = best["tried"]
                best = r
                break
            if r["event_urls"] > best["event_urls"]:
                tried = best["tried"]
                best = r
                best["tried"] = tried
        rec = {**c, **best}
        results.append(rec)
        if rec["viable"]:
            viable += 1
        print(f"  [{'VIABLE' if rec['viable'] else '  no  '}] {c['county']}, {c['state']} "
              f"({c['zero_doc_projects']:,} proj) {rec['base'] or '-'} :: {rec['reason']}",
              flush=True)

        if i % 5 == 0:
            out_path.write_text(json.dumps(results, indent=2))
            el = time.time() - t0
            rate = i / el if el else 0
            print(f"[{i}/{len(counties)}] viable={viable} "
                  f"{rate*60:.1f}/min ETA {(len(counties)-i)/rate/60 if rate else 0:.0f}m",
                  flush=True)

    out_path.write_text(json.dumps(results, indent=2))
    covered = sum(r["zero_doc_projects"] for r in results if r["viable"])
    print(f"\n[done] viable={viable}/{len(results)} counties, "
          f"covering {covered:,} zero-doc projects", flush=True)
    if args.sentinel:
        Path(args.sentinel).write_text(f"done viable={viable}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
