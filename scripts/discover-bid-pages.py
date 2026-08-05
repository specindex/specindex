#!/usr/bin/env python3
"""Find each agency's REAL bid/solicitation page, then test it for open addenda.

The first pass at these agencies returned SOFT-404 for 8 of 15 hosts -- the
host answers every path with 200 and its landing page, so the probe carried no
information either way. Those are NOT negatives; they are unusable verdicts,
and calling them "gated" would repeat the mistake that produced 17 fake EDMS
discoveries.

The fix is not a better guess at the URL. It is to stop guessing: crawl from
the agency's real homepage, follow links whose text says "bids",
"solicitations", "procurement", "doing business", and evaluate the pages that
actually exist. Every URL tested here was linked by the site itself.

Why it matters: after retuning SAM.gov from hot to warm (it RETAINS
attachments), there are currently NO hot sources registered. Local bid portals
are the only place where addenda genuinely vanish after award, so they are the
only thing that justifies daily cadence -- and the moat depends on finding
them.

Usage:
  python3 scripts/discover-bid-pages.py --out data/raw/bid_pages_discovered.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

BID_LINK_RE = re.compile(
    r"\bbid|solicitation|procure|purchasing|contract\s*opportunit|doing\s*business"
    r"|vendor|rfp\b|rfq\b|ifb\b|invitation\s*to\s*bid|current\s*opportunit", re.I)

ADDENDA_RE = re.compile(r"addend(um|a)|amendment\s*(no|#|\d)", re.I)
LOGIN_WALL_RE = re.compile(
    r"sign\s*in\s*to\s*(view|download|access)|must\s*(be\s*)?(sign|log)\s*(ed)?\s*in"
    r"|registration\s*(is\s*)?required|you\s*must\s*register|login\s*required", re.I)
SOLICITATION_RE = re.compile(
    r"solicitation|invitation\s*(for|to)\s*bid|request\s*for\s*proposal|\bIFB\b|\bRFP\b"
    r"|\bRFQ\b|bid\s*opportunit|open\s*bids|current\s*bids|bid\s*number", re.I)

AGENCIES = [
    ("Cook County OCPO",              "Cook", "IL", "https://www.cookcountyil.gov/"),
    ("Chicago Public Schools",        "Cook", "IL", "https://www.cps.edu/"),
    ("Harris County Purchasing",      "Harris", "TX", "https://purchasing.harriscountytx.gov/"),
    ("Houston ISD",                   "Harris", "TX", "https://www.houstonisd.org/"),
    ("San Diego Unified SD",          "San Diego", "CA", "https://www.sandiegounified.org/"),
    ("OC Public Works",               "Orange", "CA", "https://www.ocgov.com/"),
    ("NYC School Construction Auth",  "Kings", "NY", "https://www.nycsca.org/"),
    ("Riverside County Purchasing",   "Riverside", "CA", "https://www.rivco.org/"),
]


def render(url: str, timeout_ms: int = 55000):
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"))
            pg.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            pg.wait_for_timeout(4000)
            try:
                text = pg.inner_text("body")
            except Exception:  # noqa: BLE001
                text = ""
            links = []
            for a in pg.query_selector_all("a[href]"):
                try:
                    h = a.get_attribute("href") or ""
                    t = (a.inner_text() or "")[:90]
                    if h:
                        links.append((urllib.parse.urljoin(url, h), t))
                except Exception:  # noqa: BLE001
                    continue
            return pg.content(), text, links
        finally:
            b.close()


def evaluate(url: str):
    """Score a candidate bid page. Returns None if it could not be rendered."""
    try:
        html, text, links = render(url)
    except Exception as e:  # noqa: BLE001
        return {"url": url, "verdict": f"UNREACHABLE {type(e).__name__}"}
    linkblob = "\n".join(f"{u} :: {t}" for u, t in links)
    addenda_docs = [u for u, t in links
                    if ADDENDA_RE.search(f"{u} {t}") and re.search(r"\.(pdf|docx?|zip)", u, re.I)]
    login = bool(LOGIN_WALL_RE.search(text))
    solicitations = bool(SOLICITATION_RE.search(text))
    addenda = bool(ADDENDA_RE.search(text) or ADDENDA_RE.search(linkblob))
    if addenda_docs and not login:
        v = "OPEN-ADDENDA"
    elif addenda and not login and solicitations:
        v = "LIKELY-OPEN"
    elif login:
        v = "GATED"
    elif solicitations:
        v = "SOLICITATIONS-ONLY"
    else:
        v = "NO-SIGNAL"
    return {"url": url, "verdict": v, "login_wall": login, "solicitations": solicitations,
            "addenda_mentioned": addenda, "n_addenda_docs": len(addenda_docs),
            "addenda_docs": addenda_docs[:6], "chars": len(text)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-candidates", type=int, default=4)
    args = ap.parse_args()

    results = []
    for name, county, state, home in AGENCIES:
        print(f"\n=== {name} ({county} {state}) {home}", flush=True)
        try:
            _, _, links = render(home)
        except Exception as e:  # noqa: BLE001
            print(f"    homepage unreachable: {type(e).__name__}")
            results.append({"agency": name, "county": county, "state": state,
                            "home": home, "error": type(e).__name__})
            continue
        # Candidates are links the SITE published, never constructed.
        cands, seen = [], set()
        for u, t in links:
            if not BID_LINK_RE.search(f"{u} {t}"):
                continue
            cu = u.split("#")[0]
            if cu in seen:
                continue
            seen.add(cu)
            cands.append((cu, t.strip()))
        print(f"    {len(cands)} bid-ish links found on homepage")
        best = []
        for cu, t in cands[: args.max_candidates]:
            r = evaluate(cu)
            print(f"      {r.get('verdict','?'):<20} addenda_docs={r.get('n_addenda_docs',0)} "
                  f"{t[:34]!r} {cu[:66]}")
            best.append({**r, "link_text": t})
            time.sleep(1.0)
        results.append({"agency": name, "county": county, "state": state,
                        "home": home, "candidates": best})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "results": results}, indent=2))
    print("\n=== SUMMARY ===")
    hot = 0
    for r in results:
        best = max((c for c in r.get("candidates", []) if c.get("verdict")),
                   key=lambda c: {"OPEN-ADDENDA": 3, "LIKELY-OPEN": 2,
                                  "SOLICITATIONS-ONLY": 1}.get(c.get("verdict", ""), 0),
                   default=None)
        v = best.get("verdict") if best else "none"
        if v in ("OPEN-ADDENDA", "LIKELY-OPEN"):
            hot += 1
        print(f"  {v:<20} {r['agency']}")
    print(f"\nhot-worthy agencies: {hot} of {len(results)}  -> {args.out}")
    print("BID PAGE DISCOVERY COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
