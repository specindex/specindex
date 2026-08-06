"""ODOT (Oklahoma) -- contracts and proposals (Tier 1 claim NOT confirmed).

NO DOCUMENTS ARE PUBLISHED ON THIS PORTAL. Verified 2026-08-06 across the whole
bid-opening tree, not just the landing page:

    contracts-and-proposals.html                    281 links,  0 PDFs
    future-bid-openings/oct-15-2026.html                        0 PDFs
    past-bid-openings/2026/jun-18-2026.html                     0 PDFs
    past-bid-openings/2025/oct-16-2025.html                     0 PDFs
    past-bid-openings/2023/jun-15-2023.html                     0 PDFs

Those per-letting pages contain no document links at all -- not hidden behind
JavaScript, simply absent; the only external links on a letting page are two
Vimeo showcases. The one page that still describes the document set,
previous-bid-openings.html, names "Advertised Plans", "Sample Proposals",
"Pre-Bid Letters" and "Addenda" as plain text and links out to
https://www.bidx.com/ for "Apparent Bids".

Oklahoma DOT letting documents are distributed through Bid Express (bidx.com),
which is out of scope for this adapter set by instruction. discover() therefore
returns the letting pages it can genuinely see, with no document URLs, and the
checker fails it with "found N projects but no document URLs" -- which is the
accurate description of this portal.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Oklahoma",
    "type": "DOT",
    "tier": 1,
    "agency": "Oklahoma Department of Transportation, Office Engineer",
    "listing_url": "https://oklahoma.gov/odot/business-center/contracts-and-proposals.html",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, timeout: float = 180) -> tuple[int, bytes]:
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


_SPEC_FIRST = ("proposal", "specification", "special provision", "plan")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _letting_pages() -> list[str]:
    status, body = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    seen, out = set(), []
    for m in re.finditer(
            r'href="(/odot/business-center/contracts-and-proposals/'
            r'(?:past|future)-bid-openings/[^"]+\.html)"', html, re.I):
        u = urllib.parse.urljoin("https://oklahoma.gov", m.group(1))
        if u not in seen:
            seen.add(u)
            out.append(u)
    return sorted(out, reverse=True)


def discover(limit: int = 50) -> list[dict]:
    out: list[dict] = []
    for page in _letting_pages():
        if len(out) >= limit:
            break
        status, body = _get(page, referer=PORTAL["listing_url"])
        time.sleep(PAUSE)
        if status != 200 or not body:
            continue
        html = body.decode("utf-8", "ignore")
        docs = sorted({m.group(1) for m in re.finditer(
            r'href="([^"]+\.(?:pdf|zip))"', html, re.I)
            if "bidx.com" not in m.group(1)}, key=_rank)
        out.append({
            "project_name": urllib.parse.unquote(page.rsplit("/", 1)[-1])[:-5],
            "project_number": None,
            "bid_date": None,
            "doc_urls": [urllib.parse.urljoin(page, d) for d in docs],
        })
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
    print(f"discover() -> {len(found)} letting pages, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
