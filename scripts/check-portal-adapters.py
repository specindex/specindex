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

REQUIRED = ("PORTAL", "discover", "fetch")


def pdf_text(body: bytes, pages: int = 25) -> str:
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
    ev = []
    if CSI_SECTION.search(text):
        ev.append("section numbers")
    if CSI_PARTS.search(text):
        ev.append("PART 1/2/3")
    if CSI_DIVISION.search(text):
        ev.append("division headings")
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
        res["reason"] = f"downloaded {res['docs']} PDF(s) but none showed CSI structure (bid forms/notices only?)"
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
