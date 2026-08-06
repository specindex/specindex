#!/usr/bin/env python3
"""Independently verify portal adapters. THIS is the definition of done.

An adapter is done when this script says PASS -- never when an agent reports it
done. On 2026-08-06 three separate tasks returned a confident zero rather than an
error, and every one would have passed a self-report:

  * a stale-year filter silently discarded a 1,610-page state spec book
  * an address backfill matched nothing because it used the wrong NYC dataset
  * a portal probe recorded Delaware as dead while the host WAF-blocked plain
    fetches -- 245 bytes of "Request Rejected" at HTTP 200

So this checker does not read reports. It imports each adapter, runs discovery,
downloads a document, and requires CSI MasterFormat structure in the bytes that
come back. Anything less is a FAIL with a reason.
"""
from __future__ import annotations
import argparse, importlib.util, io, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "scripts" / "portal_adapters"

# CSI MasterFormat structure: a numbered section like "23 05 00", a division
# heading, or the PART 1/2/3 skeleton every spec section uses. Requiring this --
# rather than "is a PDF" -- is what separates a spec book from a bid form.
CSI_SECTION = re.compile(r"\b(0[0-9]|1[0-4]|2[0-8]|3[0-5])\s\d{2}\s\d{2}\b")
CSI_PARTS = re.compile(r"PART\s+[123]\s*[-–—]?\s*(GENERAL|PRODUCTS|EXECUTION)", re.I)
CSI_DIVISION = re.compile(r"\bDIVISION\s+\d{1,2}\b", re.I)

# STATE DOT SPECIFICATIONS ARE NOT MASTERFORMAT. MasterFormat is a VERTICAL
# building convention; highway agencies number their own way -- ADOT "Section
# 601", WSDOT "Divisions 1-9", Iowa "Divisions 11-42". Judging a DOT adapter by
# CSI structure fails every one of them however good the document is, which
# would have been read as "DOT portals hold no specifications".
#
# So DOT adapters are judged on THEIR convention: a numbered spec section plus
# the materials/measurement/payment skeleton every highway spec uses.
# `\d{5}` covers MasterFormat 1995, which Utah still uses and writes UNSPACED
# ("SECTION 00221", "SECTION 01355"). The modern spaced form ("23 05 00") is
# matched by CSI_SECTION; without the 1995 arm a genuine CSI project manual
# reads as having no section numbers at all.
DOT_SECTION = re.compile(r"\bSECTION\s+\d{3,5}\b", re.I)
# CALTRANS IS A THIRD CONVENTION. California numbers "1-1.06", "2-1.23",
# "7-1.02K(3)" -- neither MasterFormat nor the 3-4 digit DOT section form. Its
# own arm, deliberately, rather than loosening the others: a bare
# `\d+-\d+\.\d+` matches version strings, dates and clause references in any
# document, so it is required to CO-OCCUR with special-provision language.
CALTRANS_SECTION = re.compile(r"\b\d{1,2}-\d{1,2}\.\d{2}[A-Z]?(\(\d+\))?\b")
CALTRANS_CONTEXT = re.compile(
    r"\b(SPECIAL\s+PROVISIONS?|STANDARD\s+SPECIFICATIONS?|"
    r"REPLACE\s+SECTION|ADD\s+TO\s+SECTION|DELETE\s+SECTION)\b", re.I)

DOT_SKELETON = re.compile(
    r"\b(BASIS\s+OF\s+PAYMENT|METHOD\s+OF\s+MEASUREMENT|CONSTRUCTION\s+REQUIREMENTS"
    r"|MATERIALS\s+REQUIREMENTS|DESCRIPTION\s+AND\s+SCOPE)\b", re.I)

REQUIRED = ("PORTAL", "discover", "fetch")


def pdf_text(body: bytes, pages: int = 90) -> str:
    """Read enough pages to reach the specification.

    25 was too few and produced FALSE NEGATIVES on real spec books. A UDOT
    advertisement set carries drawings, bid schedule and boilerplate up front --
    its first measurement/payment heading is on PAGE 55. The document was
    correct, the adapter was correct, and the checker said no.

    90 is a deliberate trade: it costs a little more extraction time per
    candidate, and it is still bounded so a 2,000-page book cannot stall a run.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    try:
        r = PdfReader(io.BytesIO(body))
        return "\n".join((p.extract_text() or "") for p in r.pages[:pages])
    except Exception:  # noqa: BLE001
        return ""


def csi_evidence(text: str) -> list[str]:
    """Structural evidence only. A bare section-number match is NOT enough.

    HARDENED 2026-08-06 after the checker passed two documents that contain no
    specification at all:

      * a 37MB ADOT drawing set, whose "CSI section number" was `20 25 30`
        lifted out of a culvert FILL HEIGHT RANGE TABLE
      * an ADOT bid book, whose only match was the upside-down engineer's seal --
        the date 2026-07-20 extracting as `07 20 26`

    Both satisfy `\b(0[0-9]|...)\s\d{2}\s\d{2}\b`, because that pattern
    matches ANY three space-separated number groups. Over a numeric table it
    fires constantly. A real spec section number never appears alone: it sits
    under a DIVISION heading or above the PART 1/2/3 skeleton.

    So section numbers are now corroborating evidence, never sufficient on their
    own. The load-bearing signals are PART 1/2/3 and DIVISION headings, which do
    not occur by accident in a schedule or a seal.
    """
    parts = bool(CSI_PARTS.search(text))
    division = bool(CSI_DIVISION.search(text))
    section = bool(CSI_SECTION.search(text))
    # DOT convention: a numbered section AND the measurement/payment skeleton.
    # Both required -- "SECTION 601" alone appears in bid schedules too.
    if DOT_SECTION.search(text) and DOT_SKELETON.search(text):
        return ["DOT spec sections + measurement/payment"]
    if CALTRANS_SECTION.search(text) and CALTRANS_CONTEXT.search(text):
        return ["Caltrans section numbering + special provisions"]
    if not (parts or division):
        return []                      # section numbers alone prove nothing
    ev = []
    if parts:
        ev.append("PART 1/2/3")
    if division:
        ev.append("division headings")
    if section:
        ev.append("section numbers")
    return ev


def check(path: Path, timeout_discover: int = 180) -> dict:
    name = path.stem
    res = {"adapter": name, "pass": False, "reason": "", "docs": 0, "csi": []}
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        res["reason"] = f"import failed: {type(e).__name__}: {e}"
        return res

    missing = [a for a in REQUIRED if not hasattr(mod, a)]
    if missing:
        res["reason"] = f"missing required attribute(s): {missing}"
        return res
    for k in ("state", "type", "tier", "listing_url"):
        if k not in mod.PORTAL:
            res["reason"] = f"PORTAL missing key: {k}"
            return res

    try:
        found = mod.discover(limit=8)
    except Exception as e:  # noqa: BLE001
        res["reason"] = f"discover() raised {type(e).__name__}: {e}"
        return res
    if not found:
        res["reason"] = "discover() returned nothing -- portal may need a login, or the listing changed"
        return res

    urls = [u for f in found for u in (f.get("doc_urls") or [])]
    if not urls:
        res["reason"] = f"discover() found {len(found)} projects but no document URLs"
        return res

    for u in urls[:6]:
        try:
            body = mod.fetch(u)
        except Exception as e:  # noqa: BLE001
            res["reason"] = f"fetch() raised {type(e).__name__}"
            continue
        if not body or not body[:5].startswith(b"%PDF"):
            continue
        res["docs"] += 1
        ev = csi_evidence(pdf_text(body))
        if ev:
            res["pass"] = True
            res["csi"] = ev
            res["reason"] = f"verified: {len(body):,} bytes, CSI evidence {ev}"
            return res
        time.sleep(1.0)

    if res["docs"]:
        res["reason"] = (f"downloaded {res['docs']} PDF(s), none with PART 1/2/3 or DIVISION "
                         f"headings (bid forms/notices/drawings only?)")
    else:
        res["reason"] = "no URL returned a real PDF (WAF block? try browser headers + Referer)"
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    files = sorted(p for p in ADAPTERS.glob("*.py") if p.name != "__init__.py")
    if args.only:
        files = [p for p in files if p.stem in args.only]
    if not files:
        print("no adapters found in scripts/portal_adapters/")
        return 1
    rows = [check(p) for p in files]
    ok = sum(1 for r in rows if r["pass"])
    print(f"{'ADAPTER':<28}{'RESULT':<8}DETAIL")
    for r in sorted(rows, key=lambda x: (not x["pass"], x["adapter"])):
        print(f"  {r['adapter']:<26}{'PASS' if r['pass'] else 'FAIL':<8}{r['reason'][:88]}")
    print(f"\n{ok}/{len(rows)} adapters verified against live portals")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
