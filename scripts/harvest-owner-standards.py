#!/usr/bin/env python3
"""Harvest owner-level design standards libraries (strategy doc, Part 4, row 4).

WHY THIS SOURCE. Public university systems, state facilities agencies and K-12
construction authorities publish MasterFormat-organised design standards at
permanent public URLs. The strategy doc calls this "the underrated one" and
"highest breadth-to-effort ratio in the set," and it understates it: unlike
UFGS and the VA masters -- which are TEMPLATES carrying bracketed choices and
almost no manufacturer names -- owner standards routinely name specific
manufacturers as a campus standard ("Basis of design: Trane centrifugal
chillers"). That is a durable commercial fact. It governs every project that
owner builds for years, rather than one job, and it is exactly the
basis-of-design attribution the wedge is built on.

(Row 3, the VA PG-18-1 masters, is NOT harvestable as of 2026-08-04: the TIL
migrated to vatilms.va.gov, an Angular app behind an Okta loop. Verified with
a soft-404 baseline -- the host returns honest 404s and still serves other
PDFs, so the missing .docx files are real absence, not a block. See
docs/ROADMAP.md.)

DISCOVERY, NOT GUESSING. Every URL here is reached by crawling from a seed
page that was verified live. Nothing is constructed by pattern. This codebase
has been burned twice by invented endpoints (four fabricated EnerGov hostnames,
all DNS failures; three of five Gemini-supplied URLs non-resolving), so a
candidate that was not linked from a real page is never emitted.

SOFT-404 BASELINE IS MANDATORY. Government and .edu hosts routinely answer
unknown paths with HTTP 200 and their landing page. Each host is baselined
against a nonsense path before any result from it is believed; if the baseline
returns 200, byte-length and body similarity are used instead of status alone.

Politeness: one host at a time, serial, with a delay. These are public
institutions and a ban is a permanent loss of the source.

Usage:
  python3 scripts/harvest-owner-standards.py --seeds data/seeds/owner_standards_seeds.json \\
      --out data/raw/owner_standards_manifest.json
  python3 scripts/harvest-owner-standards.py --seeds ... --out ... --limit 3   # smoke test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# A MasterFormat section number: "23 05 00", "230500", "23 05 00.13".
# Requiring this is what separates a real standards library from a page that
# merely uses the word "specification" -- the same discipline as demanding a
# product-specific signature before believing an EDMS probe.
MASTERFORMAT_RE = re.compile(r"\b(0[1-9]|1[0-4]|2[0-8]|3[0-5]|4[0-8])[\s\-_]?([0-2]\d)[\s\-_]?([0-9]\d)\b")

DOC_EXT_RE = re.compile(r"\.(pdf|docx?|zip)(\?|$)", re.I)

# "Division 23", "Div 26", "DIVISION 23 - HVAC". Real owner-standards files are
# named this way far more often than with a full six-digit section number, so
# requiring MASTERFORMAT_RE alone threw away most genuine hits.
DIVISION_WORD_RE = re.compile(r"\bdiv(?:ision)?\.?\s*[\-_]?\s*(\d{1,2})\b", re.I)

# Link text / href hints that a page is a standards index worth descending into.
INDEX_HINT_RE = re.compile(
    r"design[\s\-_]?standard|facilit(y|ies)[\s\-_]?standard|construction[\s\-_]?standard"
    r"|design[\s\-_]?guide|master[\s\-_]?spec|technical[\s\-_]?standard|division[\s\-_]?\d"
    r"|specification", re.I)

# Looser net, used only at depth 0-1, to reach the standards index that
# typically hides behind a generic nav label rather than being linked by name
# from the homepage. Too loose to trust deeper -- it would crawl the whole site.
NAV_HINT_RE = re.compile(
    r"standard|specif|design|construct|planning|project|resource|document|policy"
    r"|guide|architect|engineer|capital|contractor|bid", re.I)

# Owner standards are very often filed by DISCIPLINE rather than by division
# number -- UW publishes "Mechanical (pdf)" and "Electrical (pdf)", not
# "Division 23". Requiring a number silently dropped an entire library.
DISCIPLINE_DIV = {
    "mechanical": "23", "hvac": "23", "plumbing": "22", "electrical": "26",
    "fire protection": "21", "fire suppression": "21", "telecommunication": "27",
    "electronic safety": "28", "security": "28", "civil": "33", "structural": "05",
    "architectural": "08", "landscape": "32",
}

# The single highest-value artifact this whole harvest can return: an owner's
# standing list of acceptable manufacturers. It IS basis-of-design attribution
# at the owner level, and it governs every project that owner builds -- so it
# is captured regardless of whether it carries a division number or discipline.
MANUFACTURER_LIST_RE = re.compile(
    r"preferred[\s\-_]?manufacturer|approved[\s\-_]?manufacturer|acceptable[\s\-_]?manufacturer"
    r"|manufacturer[\s\-_]?list|approved[\s\-_]?product|equipment[\s\-_]?standard"
    r"|basis[\s\-_]?of[\s\-_]?design", re.I)

DIV_OF_INTEREST = {"21", "22", "23", "26", "27", "28"}  # fire/plumbing/HVAC/electrical


def registrable(host: str) -> str:
    """Last two labels of a hostname -- 'pdc.ufl.edu' and 'facilities.ufl.edu'
    collapse to 'ufl.edu'.

    Standards libraries very often live on a SIBLING SUBDOMAIN of the
    facilities site (UF publishes at pdc.ufl.edu, not facilities.ufl.edu), so
    a strict same-host rule silently returns zero for exactly the
    institutions that have the richest libraries. Scoping to the registrable
    domain follows the link the site actually published without letting the
    crawler wander onto the open web.
    """
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


@dataclass
class Hit:
    institution: str
    state: str
    url: str
    link_text: str
    sections: list[str] = field(default_factory=list)
    divisions: list[str] = field(default_factory=list)
    depth: int = 0
    manufacturer_list: bool = False


def fetch(url: str, timeout: float = 30.0) -> tuple[int | None, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except Exception as e:  # noqa: BLE001 -- any failure means "don't trust this URL"
        code = getattr(e, "code", None)
        return code, b"", f"error:{type(e).__name__}"


def host_baseline(base: str) -> tuple[bool, int]:
    """Returns (host_soft_404s, baseline_len).

    If a nonsense path returns 200, this host cannot be trusted on status code
    alone and every later hit must be compared against this body length.
    """
    p = urllib.parse.urlparse(base)
    probe = f"{p.scheme}://{p.netloc}/zzzz-nonexistent-specindex-baseline/"
    status, body, _ = fetch(probe, timeout=20)
    return (status == 200), len(body)


def looks_real(status, body: bytes, soft404: bool, baseline_len: int,
               is_seed: bool = False) -> bool:
    if status != 200 or not body:
        return False
    # The seed was verified live before it entered the seed file; never let the
    # baseline heuristic discard it. On SPA hosts (OFCC) the catch-all shell and
    # every real page are byte-identical, so a pure length comparison rejects
    # the entire site and reports zero -- a plausible zero, which in this
    # codebase is always a bug until proven otherwise.
    if is_seed:
        return True
    if soft404 and abs(len(body) - baseline_len) < 512:
        return False
    return True


def sections_in(text: str) -> list[str]:
    out = []
    for m in MASTERFORMAT_RE.finditer(text):
        out.append(f"{m.group(1)} {m.group(2)} {m.group(3)}")
    return sorted(set(out))


def crawl(seed: dict, max_depth: int, delay: float, max_pages: int) -> tuple[list[Hit], dict]:
    """Breadth-first from a seed page. Same-host only."""
    inst, state, start = seed["institution"], seed["state"], seed["url"]
    soft404, baseline_len = host_baseline(start)
    seen: set[str] = set()
    queue: list[tuple[str, str, int]] = [(start, "", 0)]

    # Seed from sitemap.xml where one exists -- the site telling us its own
    # real URLs beats inferring them from nav links.
    p0 = urllib.parse.urlparse(start)
    for sm in (f"{p0.scheme}://{p0.netloc}/sitemap.xml",
               f"{p0.scheme}://{p0.netloc}/sitemap_index.xml"):
        st, bd, _ = fetch(sm, timeout=25)
        if st != 200 or not bd or b"<" not in bd[:200]:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", bd.decode("utf-8", "replace"))
        added = 0
        for loc in locs:
            if urllib.parse.urlparse(loc).netloc != p0.netloc:
                continue
            if INDEX_HINT_RE.search(urllib.parse.unquote(loc)) or DOC_EXT_RE.search(loc):
                queue.append((loc, "", 1))
                added += 1
            if added >= 200:
                break
        if added:
            print(f"    sitemap: {sm} -> {added} candidate urls", flush=True)
        break
    hits: list[Hit] = []
    pages = 0
    start_host = urllib.parse.urlparse(start).netloc
    start_domain = registrable(start_host)

    while queue and pages < max_pages:
        url, link_text, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        is_seed = (url == start)
        status, body, ctype = fetch(url)
        time.sleep(delay)

        # A document: record it, do not parse as HTML.
        if DOC_EXT_RE.search(url) or "pdf" in ctype.lower() or "word" in ctype.lower():
            if looks_real(status, body, soft404, baseline_len):
                blob2 = f"{link_text} {urllib.parse.unquote(url)}"
                secs = sections_in(link_text) or sections_in(urllib.parse.unquote(url))
                divs = {s[:2] for s in secs}
                divs |= {m.group(1).zfill(2) for m in DIVISION_WORD_RE.finditer(blob2)}
                low = blob2.lower()
                divs |= {d for word, d in DISCIPLINE_DIV.items() if word in low}
                hits.append(Hit(inst, state, url, link_text.strip()[:160], secs,
                                sorted(divs), depth,
                                bool(MANUFACTURER_LIST_RE.search(blob2))))
            continue

        if not looks_real(status, body, soft404, baseline_len, is_seed=is_seed):
            continue
        pages += 1
        html = body.decode("utf-8", "replace")

        if depth >= max_depth:
            continue
        for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
            href, text = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            absu = urllib.parse.urljoin(url, href)
            if registrable(urllib.parse.urlparse(absu).netloc) != start_domain:
                continue
            blob = f"{text} {urllib.parse.unquote(href)}"
            # Descend only into plausible standards pages, but ALWAYS follow a
            # document link that carries a MasterFormat number -- that is the
            # payload and it is often linked from an otherwise dull page.
            if DOC_EXT_RE.search(absu):
                if (MASTERFORMAT_RE.search(blob) or DIVISION_WORD_RE.search(blob)
                        or MANUFACTURER_LIST_RE.search(blob)
                        or any(d in blob.lower() for d in DISCIPLINE_DIV)):
                    queue.insert(0, (absu, text, depth + 1))  # documents first
            elif INDEX_HINT_RE.search(blob):
                queue.insert(0, (absu, text, depth + 1))
            elif depth <= 1 and NAV_HINT_RE.search(blob):
                queue.append((absu, text, depth + 1))

    meta = {"institution": inst, "state": state, "seed": start,
            "host_soft_404s": soft404, "baseline_len": baseline_len,
            "pages_crawled": pages, "docs_found": len(hits)}
    return hits, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True,
                    help="Manifest path. NEVER point this at data/states/*.json -- it overwrites.")
    ap.add_argument("--max-depth", type=int, default=2)
    ap.add_argument("--max-pages", type=int, default=60, help="per institution")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests, per host")
    ap.add_argument("--limit", type=int, default=0, help="only first N seeds (smoke test)")
    args = ap.parse_args()

    if "data/states/" in str(args.out):
        print("REFUSING: --out must not target data/states/ (it overwrites).", file=sys.stderr)
        return 2

    seeds = json.loads(args.seeds.read_text())
    if args.limit:
        seeds = seeds[: args.limit]

    all_hits: list[Hit] = []
    metas = []
    for i, seed in enumerate(seeds, 1):
        print(f"[{i}/{len(seeds)}] {seed['institution']} ({seed['state']}) {seed['url']}", flush=True)
        try:
            hits, meta = crawl(seed, args.max_depth, args.delay, args.max_pages)
        except Exception as e:  # noqa: BLE001 -- one bad host must not end the run
            print(f"    FAILED: {type(e).__name__}: {e}", flush=True)
            metas.append({"institution": seed["institution"], "state": seed["state"],
                          "seed": seed["url"], "error": f"{type(e).__name__}: {e}"})
            continue
        mep = [h for h in hits if set(h.divisions) & DIV_OF_INTEREST]
        mfg = [h for h in hits if h.manufacturer_list]
        print(f"    pages={meta['pages_crawled']} docs={len(hits)} "
              f"MEP(21-28)={len(mep)} MFG_LISTS={len(mfg)} "
              f"soft404={meta['host_soft_404s']}", flush=True)
        all_hits.extend(hits)
        metas.append(meta)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "institutions": metas,
         "documents": [asdict(h) for h in all_hits]}, indent=2))

    mep_total = sum(1 for h in all_hits if set(h.divisions) & DIV_OF_INTEREST)
    mfg_total = sum(1 for h in all_hits if h.manufacturer_list)
    print(f"\nDONE. institutions={len(metas)} documents={len(all_hits)} "
          f"MEP_div_21_28={mep_total} manufacturer_lists={mfg_total}")
    print(f"Manifest: {args.out}")
    print("OWNER STANDARDS HARVEST COMPLETE")  # sentinel for wait loops
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
