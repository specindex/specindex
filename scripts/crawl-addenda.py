#!/usr/bin/env python3
"""Track C -- crawl state/local bid portals for ADDENDA and substitution rulings.

WHY THIS IS THE ONLY PATH TO THE MOAT. Tested 2026-08-05: 400 pages of federal
document text containing "reject" produced ZERO named substitution rulings.
Every hit was specification boilerplate --

    "CONSULTANT RESERVES THE RIGHT TO REJECT ANY SYSTEM WHICH, WHEN INSTALLED,
     DOES NOT PROVIDE CAPTURE AND CONTAINMENT..."

-- a reserved right, not a decision about a named manufacturer. SAM.gov
amendments carry basis-of-design and substitution PROCEDURES; they do not
carry rulings. Federal capture delivers the wedge, not the moat. Those are
different products.

Rulings live where the strategy doc said they live: addenda and pre-bid Q&A
logs on state and local bid portals. And unlike everything else in this
corpus, THEY ARE REMOVED AFTER AWARD -- so this is the only crawler where a
week of delay is a week of data permanently lost.

TARGETING, learned the hard way. An earlier probe of 15 top-10-county agencies
found 8 unusable (soft-404 hosts), 5 solicitations-only, and 2 likely-open.
The top-10 counties are as thin for addenda as they were for documents
generally. Mid-size owners -- school districts, university systems, transit
authorities -- are the realistic target, matching the pattern where mid-size
counties serve documents and the top-20 do not.

WHAT COUNTS AS A FIND. Not a page mentioning "addendum" -- government sites
say that everywhere. A find is a DOWNLOADABLE addendum file reachable without
login. Anything else is recorded as a lead with its gate described, because a
mapped-but-gated path is real intel (that is how Duval FL's document API got
documented) while an unmapped one is nothing.

Usage:
  python3 scripts/crawl-addenda.py --seeds data/seeds/addenda_portals.json --dry-run
  python3 scripts/crawl-addenda.py --seeds data/seeds/addenda_portals.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import storage  # noqa: E402

ADDENDA_FILE_RE = re.compile(
    r"(addend|amendment|q\s*&\s*a|question.*answer|substitution)", re.I)
DOC_EXT_RE = re.compile(r"\.(pdf|docx?|xlsx?)(\?|$)", re.I)
SOLICITATION_LINK_RE = re.compile(
    r"\bbid|solicitation|rfp\b|rfq\b|ifb\b|procure|purchasing|contract\s*opportunit"
    r"|doing\s*business|vendor", re.I)
LOGIN_WALL_RE = re.compile(
    r"sign\s*in\s*to\s*(view|download|access)|must\s*(be\s*)?(sign|log)\s*(ed)?\s*in"
    r"|registration\s*(is\s*)?required|you\s*must\s*register|login\s*required"
    r"|create\s*an?\s*account\s*to", re.I)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def render(url: str, timeout_ms: int = 55000):
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(user_agent=UA)
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
                    if h:
                        links.append((urllib.parse.urljoin(url, h),
                                      (a.inner_text() or "")[:120]))
                except Exception:  # noqa: BLE001
                    continue
            return text, links
        finally:
            b.close()


def baseline_len(url: str) -> int:
    """Government hosts answer unknown paths with 200 and their landing page.
    Without this every probe is a false positive -- 8 of 15 agencies in the
    earlier pass were exactly this."""
    p = urllib.parse.urlparse(url)
    try:
        t, _ = render(f"{p.scheme}://{p.netloc}/zzzz-nonexistent-specindex/", 40000)
        return len(t)
    except Exception:  # noqa: BLE001
        return 0


def crawl_agency(seed: dict, max_pages: int, delay: float) -> dict:
    name, url = seed["agency"], seed["url"]
    out = {**seed, "addenda_files": [], "leads": [], "pages_seen": 0,
           "gate": None, "verdict": "no-signal"}
    base = baseline_len(url)
    seen, queue = set(), [(url, 0)]
    found: list[dict] = []

    while queue and out["pages_seen"] < max_pages:
        u, depth = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        try:
            text, links = render(u)
        except Exception:  # noqa: BLE001 -- one dead page must not end the agency
            continue
        # Indistinguishable from the host's catch-all -> carries no information.
        if base and abs(len(text) - base) < 200:
            out["verdict"] = "soft-404 host (probe carries no information)"
            return out
        out["pages_seen"] += 1

        if LOGIN_WALL_RE.search(text):
            out["gate"] = "login required"

        for lu, lt in links:
            blob = f"{lu} {lt}"
            # A downloadable addendum file is the only real find.
            if DOC_EXT_RE.search(lu) and ADDENDA_FILE_RE.search(blob):
                found.append({"url": lu, "label": re.sub(r"\s+", " ", lt).strip()[:120]})
            elif depth < 2 and SOLICITATION_LINK_RE.search(blob) and "#" not in lu:
                queue.append((lu.split("#")[0], depth + 1))
        time.sleep(delay)

    # Dedupe by url; portals repeat the same addendum across listing pages.
    uniq, seenu = [], set()
    for f in found:
        if f["url"] not in seenu:
            seenu.add(f["url"])
            uniq.append(f)
    out["addenda_files"] = uniq[:200]
    if uniq and not out["gate"]:
        out["verdict"] = "OPEN-ADDENDA"
    elif uniq:
        out["verdict"] = "addenda listed, gated"
    elif out["gate"]:
        out["verdict"] = "gated"
    elif out["pages_seen"]:
        out["verdict"] = "no addenda found"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/raw/addenda_crawl.json"))
    ap.add_argument("--max-pages", type=int, default=25)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--dry-run", action="store_true", help="discover only, do not download")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    seeds = json.loads(args.seeds.read_text())
    if args.limit:
        seeds = seeds[: args.limit]
    results = []
    for i, s in enumerate(seeds, 1):
        print(f"[{i}/{len(seeds)}] {s['agency']} -- {s['url']}", flush=True)
        r = crawl_agency(s, args.max_pages, args.delay)
        print(f"    {r['verdict']}  addenda_files={len(r['addenda_files'])} "
              f"pages={r['pages_seen']} gate={r['gate']}", flush=True)
        for f in r["addenda_files"][:3]:
            print(f"       {f['label'][:60]!r}", flush=True)
        results.append(r)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "agencies": results}, indent=2))

    total = sum(len(r["addenda_files"]) for r in results)
    openn = sum(1 for r in results if r["verdict"] == "OPEN-ADDENDA")
    print(f"\n=== ADDENDA CRAWL ===")
    print(f"  agencies crawled     : {len(results)}")
    print(f"  OPEN-ADDENDA         : {openn}")
    print(f"  downloadable addenda : {total}")
    for r in results:
        print(f"    {r['verdict'][:38]:<40}{r['agency'][:34]}")
    print(f"  -> {args.out}")

    if args.dry_run or not total:
        print("\nDRY RUN or nothing to fetch -- no downloads")
        print("ADDENDA CRAWL COMPLETE")
        return 0

    # Capture. Content-type verified, never status -- a 200 HTML error page
    # must not land in the bucket as an addendum.
    import urllib.request  # noqa: PLC0415

    bucket = storage.bucket()
    up = 0
    for r in results:
        slug = re.sub(r"[^a-z0-9]+", "-", r["agency"].lower()).strip("-")[:50]
        for f in r["addenda_files"]:
            try:
                req = urllib.request.Request(f["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    body = resp.read()
                if not any(c in ct for c in ("pdf", "officedocument", "msword", "excel")):
                    continue
                if len(body) < 2048:
                    continue
                fn = urllib.parse.unquote(urllib.parse.urlparse(f["url"]).path.rsplit("/", 1)[-1])
                fn = re.sub(r"[^A-Za-z0-9._\- ]+", "_", fn)[:150] or "addendum.pdf"
                bucket.blob(f"addenda/{slug}/{fn}").upload_from_string(
                    body, content_type=ct.split(";")[0])
                up += 1
                print(f"  uploaded {fn[:60]}", flush=True)
            except Exception as e:  # noqa: BLE001
                continue
    print(f"\nuploaded {up} addenda to gs://specindex-ai-raw-documents/addenda/")
    print("ADDENDA CRAWL COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
