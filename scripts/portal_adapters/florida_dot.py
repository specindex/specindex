"""FDOT -- Florida DOT central office letting (Tier 1, DOT).

Documents ARE reachable, anonymously: the letting page carries 333 PDFs on
ftp.fdot.gov, and they are real. What they are NOT is specification books.
Every free FDOT letting document falls into one of four classes:

    T####BSN.pdf          Bid Solicitation Notice + approximate quantities (2-7 pp)
    T####Addendum###.pdf  addendum cover + plan-revision table (5-8 pp)
    T####-Bid-Tab.pdf     bid tabulation, post-award
    CO-MM-DD-YYBSN-n.pdf  letting-wide advertisement

The project Specifications Package and plan set are NOT published here. They are
ordered through the CPP Online Ordering System, fdotwp1.dot.state.fl.us, which
requires an account. This adapter therefore FAILS the checker, and that FAIL is
the correct answer for the free tier. See docs/adapter_findings_tier1_dot.md.

DELIBERATE RANKING CHOICE -- read before "fixing" this:
The CSI section-number regex FIRES on FDOT addenda, and it is a false positive
every time. T7599Addendum001.pdf matches on "447935-1-52-01 1 07/20/26" -- a
plan-revision row where a sheet number and a date sit side by side and extract as
"1 07 20". That file is 7 pages and contains no specification prose at all. The
checker was hardened on 2026-08-06 so a bare section-number match no longer
counts, which closes the hole; _rank() still puts the Bid Solicitation Notice --
the actual primary letting document -- first, so a future loosening of that rule
cannot turn this portal into a fake PASS.

Verified 2026-08-06 with the DOT-aware checker: six FDOT addenda scanned in FULL
(not just 25 pages) contain neither a numbered highway spec section nor any of
BASIS OF PAYMENT / METHOD OF MEASUREMENT / CONSTRUCTION REQUIREMENTS. The
absence is real, not a numbering-convention mismatch.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Florida",
    "type": "DOT",
    "tier": 1,
    "agency": "Florida Department of Transportation, Contracts Administration",
    "listing_url": "https://www.fdot.gov/contracts/lettings/letting-project-info.shtm",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, timeout: float = 300) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,text/html,*/*"}
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _soft404(host_root: str) -> bytes:
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/zzz-specindex-not-real-9174.pdf")
        _baseline[host_root] = body
    return _baseline[host_root]


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    if "bsn" in low:
        return 0          # bid solicitation notice: the primary letting document
    if "addendum" in low:
        return 1          # amends the (unpublished) spec package; see docstring
    if "bid-tab" in low or "bid%20tab" in low:
        return 3          # post-award, never specification content
    return 2


def discover(limit: int = 50) -> list[dict]:
    status, body = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    by_proposal: dict[str, dict] = {}
    for m in re.finditer(r'href="(https://ftp\.fdot\.gov/[^"]+\.pdf[^"]*)"', html, re.I):
        url = m.group(1)
        fname = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        prop = re.match(r"(T[0-9A-Z]{4})", fname)
        if not prop:
            continue   # letting-wide notices, fuel allocations, work-class breakouts
        key = prop.group(1)
        e = by_proposal.setdefault(key, {
            "project_name": key, "project_number": key,
            "bid_date": None, "doc_urls": [],
        })
        if url not in e["doc_urls"]:
            e["doc_urls"].append(url)
    out = []
    for e in by_proposal.values():
        e["doc_urls"].sort(key=_rank)
        out.append(e)
        if len(out) >= limit:
            break
    return out


def fetch(url: str) -> bytes | None:
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    status, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    base = _soft404(root)
    if base and body == base:
        return None
    return body


if __name__ == "__main__":
    found = discover(limit=6)
    print(f"discover() -> {len(found)} projects, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
    for f in found:
        print(" ", f["project_number"], len(f["doc_urls"]))
