#!/usr/bin/env python3
"""Find permit data sources for a county by SEARCHING REAL CATALOGS, not guessing.

Why this exists (2026-08-03): constructing candidate hostnames by pattern does
not work. Four EnerGov tenant hostnames built from the obvious template
(energov.cityftmyers.com, energov.marionfl.org, midlandtx-energovweb.tylerhost.net,
epzb.pbcgov.org) all DNS-failed; every one that was found came from following a
live redirect or a catalog entry instead. So this queries catalogs that actually
index the data:

  * **Socrata Discovery API** (api.us.socrata.com/api/catalog/v1) -- indexes
    every public Socrata dataset across all domains, searchable by text and
    filterable by jurisdiction.
  * **ArcGIS Online search** (www.arcgis.com/sharing/rest/search) -- indexes
    public hosted Feature Services, including the county-published permit
    layers that never appear in any open-data portal UI.
  * **CKAN** portals via package_search where a known portal exists.

Both are read-only public APIs and are queried concurrently across counties --
these are small independent requests, the regime where parallelism is a pure
win (unlike large file transfers, which saturate the uplink at ~3 streams).

This REPORTS candidates only. It writes no config and downloads nothing. Every
hit needs live verification -- a catalog entry proves a dataset is indexed, not
that it holds commercial permits in the pull window, and titles lie. A
well-evidenced negative is a valid result: record it in
data/jurisdiction_health_matrix.json rather than leaving a county unexplained.

Usage:
    python3 scripts/discover-county-sources.py --county "Alameda,CA" --county "Travis,TX"
    python3 scripts/discover-county-sources.py --from-gaps --top 100
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "SpecIndex-SourceDiscovery/1.0 (construction data research)"}

# Terms that suggest a dataset is actually building/commercial permits rather
# than the many other things a county publishes.
GOOD = re.compile(r"(building permit|construction permit|permit issued|issued permit|"
                  r"commercial permit|building inspection|certificate of occupancy|"
                  r"development application|site plan|plan review)", re.I)
# Datasets that match "permit" but are never construction.
BAD = re.compile(r"(parking|dog|animal|fishing|hunting|event permit|film|"
                 r"vendor|peddler|alcohol|liquor|tobacco|burn permit|"
                 r"special event|tree removal|garage sale)", re.I)


STATE_DOMAIN_HINTS = {
    "CA": ("ca.gov", "cagov", ".ca."), "TX": ("tx.gov", "texas", ".tx."),
    "NJ": ("nj.gov", ".nj.", "newjersey"), "NY": ("ny.gov", ".ny.", "newyork"),
    "FL": ("fl.gov", ".fl.", "florida"), "WA": ("wa.gov", ".wa."),
    "MA": ("ma.gov", ".ma.", "mass.gov"), "PA": ("pa.gov", ".pa."),
    "MD": ("md.gov", ".md."), "OH": ("oh.gov", ".oh.", "ohio"),
    "GA": ("ga.gov", ".ga.", "georgia"), "MI": ("mi.gov", ".mi."),
    "MO": ("mo.gov", ".mo."), "IL": ("il.gov", ".il.", "illinois"),
    "TN": ("tn.gov", ".tn."), "UT": ("utah", ".ut."), "HI": ("hawaii", ".hi."),
}


def _belongs_to(name: str, domain: str, county: str, state: str) -> bool:
    """Does this dataset plausibly belong to the target county/state?

    Socrata's catalog search matches on the generic words ("building permits")
    and ignores the place name entirely, so relevance has to be re-checked
    here. Deliberately permissive about HOW it matches (county name in the
    title, county name in the domain, or a state-specific domain hint) but
    strict that it must match SOMETHING -- a candidate that cannot be tied to
    the jurisdiction is worse than no candidate at all.
    """
    hay = f"{name} {domain}".lower()
    cty = county.lower()
    if cty in hay:
        return True
    # County names are often absent while the city is present; a state-scoped
    # domain is weak evidence but keeps genuinely-local city portals in play.
    return any(h in domain.lower() for h in STATE_DOMAIN_HINTS.get(state.upper(), ()))


def get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def search_socrata(county: str, state: str) -> list[dict]:
    """Socrata's cross-domain discovery catalog."""
    out = []
    for q in (f"{county} building permits", f"{county} county permits"):
        url = ("https://api.us.socrata.com/api/catalog/v1?"
               + urllib.parse.urlencode({"q": q, "limit": 25, "only": "dataset"}))
        try:
            data = get_json(url)
        except Exception:  # noqa: BLE001
            continue
        for r in data.get("results", []):
            res = r.get("resource", {})
            name = res.get("name") or ""
            if BAD.search(name) or not GOOD.search(name):
                continue
            dom = (r.get("metadata") or {}).get("domain") or ""
            # Socrata's text search is global and heavily fuzzy: querying
            # "San Mateo building permits" happily returns Calgary, Edmonton,
            # Chicago and Austin, because it matches on "building permits"
            # alone. Without this the script becomes a false-positive machine
            # that would have had someone wiring Calgary's feed as San Mateo.
            # Require the county (or its state) to actually appear in the
            # dataset name or the publishing domain.
            if not _belongs_to(name, dom, county, state):
                continue
            out.append({
                "kind": "socrata", "county": county, "state": state,
                "name": name[:80], "domain": dom, "id": res.get("id"),
                "url": f"https://{dom}/resource/{res.get('id')}.json",
                "rows": res.get("rows_size"),
            })
    # de-dup by dataset id
    seen, uniq = set(), []
    for o in out:
        if o["id"] not in seen:
            seen.add(o["id"])
            uniq.append(o)
    return uniq


def search_arcgis(county: str, state: str) -> list[dict]:
    """ArcGIS Online hosted Feature Services.

    Searching item titles finds county-published permit layers that are often
    invisible in any open-data portal UI -- this is the same class of source
    that a portal-first search misses entirely.
    """
    out = []
    q = f'({county} AND permits) AND (type:"Feature Service")'
    url = ("https://www.arcgis.com/sharing/rest/search?"
           + urllib.parse.urlencode({"q": q, "f": "json", "num": 30,
                                     "sortField": "numViews", "sortOrder": "desc"}))
    try:
        data = get_json(url)
    except Exception:  # noqa: BLE001
        return out
    for it in data.get("results", []):
        title = it.get("title") or ""
        if BAD.search(title) or not GOOD.search(title):
            continue
        # ArcGIS titles frequently carry NO jurisdiction ("Issued Building
        # Permits"), so a name test drops real county layers -- it discarded a
        # 198,610-row Alameda service. Flag instead of drop, and let the live
        # probe plus a human decide. Silently dropping a true source is a worse
        # failure here than reporting one that needs checking.
        matched = _belongs_to(title, (it.get("url") or "") + " " + (it.get("owner") or ""),
                              county, state)
        out.append({
            "kind": "arcgis", "county": county, "state": state,
            "name": title[:80], "owner": it.get("owner"),
            "url": it.get("url") or "",
            "id": it.get("id"),
            "jurisdiction_confirmed": matched,
        })
    return out


def probe_counts(cand: dict) -> dict:
    """Ask the live endpoint how many records it has since 2025-01-01.

    A catalog hit is only a lead; this is the cheapest possible evidence that
    the dataset is real, reachable and non-empty before anyone wires a config.
    """
    try:
        if cand["kind"] == "socrata" and cand.get("url"):
            u = cand["url"] + "?" + urllib.parse.urlencode({"$select": "count(1)"})
            d = get_json(u, timeout=25)
            if isinstance(d, list) and d:
                cand["live_total"] = int(next(iter(d[0].values())))
        elif cand["kind"] == "arcgis" and cand.get("url"):
            base = cand["url"].rstrip("/")
            u = f"{base}/0/query?" + urllib.parse.urlencode(
                {"where": "1=1", "returnCountOnly": "true", "f": "json"})
            d = get_json(u, timeout=25)
            if "count" in d:
                cand["live_total"] = int(d["count"])
    except Exception as e:  # noqa: BLE001
        cand["probe_error"] = f"{type(e).__name__}"
    return cand


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--county", action="append", default=[],
                    help='"County,ST" (repeatable).')
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--no-probe", action="store_true", help="Skip live count probes.")
    ap.add_argument("--json", help="Write candidates to this path.")
    args = ap.parse_args(argv)

    targets = []
    for c in args.county:
        cty, _, st = c.rpartition(",")
        targets.append((cty.strip(), st.strip().upper()))
    if not targets:
        ap.error("pass --county 'Name,ST'")

    print(f"Searching Socrata + ArcGIS Online for {len(targets)} counties "
          f"({args.workers} workers)\n", flush=True)

    cands: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {}
        for cty, st in targets:
            futs[pool.submit(search_socrata, cty, st)] = (cty, st, "socrata")
            futs[pool.submit(search_arcgis, cty, st)] = (cty, st, "arcgis")
        for f in as_completed(futs):
            try:
                cands.extend(f.result())
            except Exception:  # noqa: BLE001
                pass

    if not args.no_probe and cands:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            cands = [f.result() for f in as_completed([pool.submit(probe_counts, c) for c in cands])]

    by_county: dict[tuple[str, str], list[dict]] = {}
    for c in cands:
        by_county.setdefault((c["county"], c["state"]), []).append(c)

    for cty, st in targets:
        hits = sorted(by_county.get((cty, st), []),
                      key=lambda c: -(c.get("live_total") or 0))
        print(f"\n=== {cty}, {st} -- {len(hits)} candidate(s)")
        for h in hits[:6]:
            n = h.get("live_total")
            n_s = f"{n:,} rows" if isinstance(n, int) else (h.get("probe_error") or "unprobed")
            flag = "" if h.get("jurisdiction_confirmed", True) else "  (jurisdiction UNVERIFIED)"
            print(f"   [{h['kind']:<7}] {h['name'][:56]:<57} {n_s}{flag}")
            print(f"             {h['url'][:96]}")
        if not hits:
            print("   (no catalog match -- needs Gemini discovery / portal hunt)")

    found = sum(1 for k in by_county if by_county[k])
    print(f"\n{'='*72}")
    print(f"counties with at least one candidate: {found}/{len(targets)}")
    print("Every hit needs live verification before wiring: a catalog entry proves\n"
          "the dataset is indexed, not that it holds commercial permits in-window.")
    if args.json:
        Path(args.json).write_text(json.dumps(cands, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
