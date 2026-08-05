#!/usr/bin/env python3
"""Verify which owner-side bid portals expose ADDENDA without registration.

WHY ADDENDA SPECIFICALLY. Addenda and pre-bid Q&A logs are where substitution
requests are ruled on, naming the approved and rejected manufacturers with
dates. They are the only public artifact showing competitive DISPLACEMENT,
nobody indexes them, and they come down after award -- so an archive cannot be
reconstructed by anyone who starts later. This is the one time-sensitive item
on the roadmap.

WHY THIS SCRIPT EXISTS AT ALL. Gemini was asked which top-10-county portals
serve addenda anonymously and produced a clean, confident table. In the SAME
answer about a different question it returned a soft-404 URL alongside a real
one, at equal confidence. So every claim here is re-derived from live evidence
and the model's verdict is recorded only as a hypothesis to be confirmed or
contradicted.

The permit-portal path is already a closed dead end for these counties: 14 of
the top 20 are metadata-only, no EDMS exists on any of them, and the proven
document tenants are saturated. Owner-side procurement is a DIFFERENT source
class and is where the moat actually lives.

WHAT COUNTS AS A REAL FINDING. Three things must all hold:
  1. the host answers a nonsense path differently than the real page (no soft-404)
  2. the page names a recognised procurement platform, or exposes solicitation
     links, WITHOUT a login wall
  3. the word "addend"/"amendment" appears in a document or link context

"Mentions the word addendum" alone is not evidence -- the incumbent-research
lesson: never accept a generic word as a product signature.

Usage:
  python3 scripts/verify-bid-portal-addenda.py --out data/raw/bid_portal_verdicts.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Recognised e-procurement platforms and the signature that identifies each.
# A platform match plus a differing baseline is what makes a hit believable.
PLATFORM_SIGNATURES = {
    "Bonfire":      r"bonfirehub|bonfire\s*portal|GoBonfire",
    "PlanetBids":   r"planetbids|pbsystem",
    "BidNet":       r"bidnetdirect|bidnet\s*direct",
    "Periscope":    r"periscopeholdings|bidsync",
    "Ionwave":      r"ionwave",
    "DemandStar":   r"demandstar",
    "OpenGov":      r"opengov\.com/procurement|procurement\.opengov",
    "Ivalua":       r"ivalua|buynet",
    "BidExpress":   r"bidexpress",
    "CivcastUSA":   r"civcast",
    "Vendor Registry": r"vendorregistry",
    "eMMA/Maryland": r"emma\.maryland",
    "Custom/Unknown": r"$^",
}

LOGIN_WALL_RE = re.compile(
    r"sign\s*in\s*to\s*(view|download|access)|must\s*(be\s*)?(sign|log)\s*(ed)?\s*in"
    r"|registration\s*(is\s*)?required|you\s*must\s*register|login\s*required", re.I)

ADDENDA_RE = re.compile(r"addend(um|a)|amendment\s*(no|#|\d)", re.I)

SOLICITATION_RE = re.compile(
    r"solicitation|invitation\s*(for|to)\s*bid|request\s*for\s*proposal|\bIFB\b|\bRFP\b"
    r"|\bRFQ\b|bid\s*opportunit|open\s*bids|current\s*bids", re.I)


def render(url: str, timeout_ms: int = 60000) -> tuple[str, str, list[str]]:
    """Returns (html, visible_text, doc_links). Playwright, because most of
    these portals are SPA shells that curl cannot see through."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"))
            pg.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            pg.wait_for_timeout(5000)
            html = pg.content()
            try:
                text = pg.inner_text("body")
            except Exception:  # noqa: BLE001
                text = ""
            links = []
            for a in pg.query_selector_all("a[href]"):
                try:
                    links.append(f"{a.get_attribute('href')} :: {(a.inner_text() or '')[:80]}")
                except Exception:  # noqa: BLE001
                    continue
            return html, text, links
        finally:
            b.close()


def assess(entry: dict) -> dict:
    url = entry["url"]
    out = dict(entry)
    # BASELINE FIRST. A government host that answers every path with 200 and
    # its landing page will otherwise turn every probe into a false positive.
    base_url = re.sub(r"(https?://[^/]+).*", r"\1", url) + "/zzzz-nonexistent-specindex/"
    try:
        _, base_text, _ = render(base_url, timeout_ms=45000)
    except Exception:  # noqa: BLE001
        base_text = ""
    try:
        html, text, links = render(url)
    except Exception as e:  # noqa: BLE001
        out.update(verdict="UNREACHABLE", detail=f"{type(e).__name__}: {str(e)[:100]}")
        return out

    linkblob = "\n".join(links)
    soft404 = bool(base_text) and abs(len(base_text) - len(text)) < 200

    platforms = [n for n, sig in PLATFORM_SIGNATURES.items()
                 if n != "Custom/Unknown" and re.search(sig, html, re.I)]
    login_wall = bool(LOGIN_WALL_RE.search(text))
    addenda = bool(ADDENDA_RE.search(text) or ADDENDA_RE.search(linkblob))
    addenda_docs = [l for l in links
                    if ADDENDA_RE.search(l) and re.search(r"\.(pdf|docx?|zip)", l, re.I)]
    solicitations = bool(SOLICITATION_RE.search(text))

    if soft404:
        verdict = "SOFT-404 (host answers everything; probe worthless)"
    elif addenda_docs and not login_wall:
        verdict = "OPEN-ADDENDA"          # the outcome that matters
    elif addenda and not login_wall and solicitations:
        verdict = "LIKELY-OPEN (addenda named, no wall, not yet downloaded)"
    elif login_wall:
        verdict = "GATED"
    elif solicitations:
        verdict = "SOLICITATIONS-ONLY (no addenda seen)"
    else:
        verdict = "NO-SIGNAL"

    out.update(
        verdict=verdict,
        platforms=platforms or ["unrecognised"],
        login_wall=login_wall,
        addenda_mentioned=addenda,
        addenda_doc_links=addenda_docs[:8],
        n_addenda_docs=len(addenda_docs),
        solicitations=solicitations,
        soft404=soft404,
        page_chars=len(text),
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()

    if "data/states/" in str(args.out):
        print("REFUSING: --out must not target data/states/", file=sys.stderr)
        return 2

    # Top-10 counties by population. Agency URLs only; the model's claim is
    # carried as a hypothesis field so the live verdict can contradict it.
    targets = [
        dict(county="Los Angeles", state="CA", rank=1, agency="LA County Public Works",
             url="https://pw.lacounty.gov/brcd/servicecontracts", gemini_said="OPEN"),
        dict(county="Los Angeles", state="CA", rank=1, agency="LAUSD Procurement",
             url="https://achieve.lausd.net/procurement", gemini_said=None),
        dict(county="Los Angeles", state="CA", rank=1, agency="LA Metro Vendor Portal",
             url="https://business.metro.net/", gemini_said=None),
        dict(county="Cook", state="IL", rank=2, agency="Cook County OCPO",
             url="https://www.cookcountyil.gov/service/current-contracting-opportunities",
             gemini_said="GATED"),
        dict(county="Cook", state="IL", rank=2, agency="Chicago Public Schools",
             url="https://www.cps.edu/about/procurement/", gemini_said=None),
        dict(county="Harris", state="TX", rank=3, agency="Harris County Purchasing",
             url="https://purchasing.harriscountytx.gov/Pages/BidSolicitations.aspx",
             gemini_said="GATED"),
        dict(county="Harris", state="TX", rank=3, agency="Houston ISD Procurement",
             url="https://www.houstonisd.org/procurement", gemini_said=None),
        dict(county="Maricopa", state="AZ", rank=4, agency="Maricopa County Procurement",
             url="https://www.maricopa.gov/2190/Solicitations", gemini_said="GATED"),
        dict(county="San Diego", state="CA", rank=5, agency="San Diego County P&C",
             url="https://www.sandiegocounty.gov/content/sdc/purchasing.html",
             gemini_said="GATED"),
        dict(county="San Diego", state="CA", rank=5, agency="San Diego Unified School District",
             url="https://www.sandiegounified.org/departments/contract_services", gemini_said=None),
        dict(county="Orange", state="CA", rank=6, agency="OC Public Works",
             url="https://ocgov.com/contracts-purchasing", gemini_said=None),
        dict(county="Miami-Dade", state="FL", rank=7, agency="Miami-Dade Procurement",
             url="https://www.miamidade.gov/global/business/procurement/home.page",
             gemini_said=None),
        dict(county="Dallas", state="TX", rank=8, agency="Dallas County Purchasing",
             url="https://www.dallascounty.org/departments/purchasing/", gemini_said=None),
        dict(county="Kings", state="NY", rank=9, agency="NYC School Construction Authority",
             url="https://www.nycsca.org/Business/Opportunities", gemini_said=None),
        dict(county="Riverside", state="CA", rank=10, agency="Riverside County Purchasing",
             url="https://rivcocob.org/clerk-of-the-board/bids", gemini_said=None),
    ]

    results = []
    for i, t in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {t['county']} {t['state']} -- {t['agency']}", flush=True)
        r = assess(t)
        print(f"    {r['verdict']}  platforms={r.get('platforms')} "
              f"addenda_docs={r.get('n_addenda_docs', 0)} wall={r.get('login_wall')}", flush=True)
        if t.get("gemini_said"):
            agreed = ((t["gemini_said"] == "OPEN" and "OPEN" in r["verdict"])
                      or (t["gemini_said"] == "GATED" and r["verdict"] == "GATED"))
            print(f"    gemini said {t['gemini_said']} -> {'CONFIRMED' if agreed else 'NOT CONFIRMED'}",
                  flush=True)
            r["gemini_confirmed"] = agreed
        results.append(r)
        time.sleep(args.delay)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "results": results}, indent=2))
    print("\n=== VERDICTS ===")
    for r in results:
        print(f"  {r['verdict']:52s} {r['county']:12s} {r['agency']}")
    open_n = sum(1 for r in results if "OPEN" in r["verdict"])
    print(f"\nopen/likely-open: {open_n} of {len(results)}   -> {args.out}")
    print("BID PORTAL VERIFICATION COMPLETE")  # sentinel
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
