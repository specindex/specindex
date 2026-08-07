"""Missouri FMDC Bid Opportunities -- reference adapter.

Proven end to end 2026-08-06: R2511-01 (Replace HVAC & Boilers, Troop B HQ,
Macon) returned a 227-page project manual containing Division 23 Mechanical and
Division 26 Electrical, with no login. This file is the pattern other adapters
follow; see docs/PORTAL_ADAPTER_CONTRACT.md.
"""
from __future__ import annotations
import re, time, urllib.parse, urllib.request

PORTAL = {
    "state": "Missouri",
    "type": "Vertical",
    "tier": 1,
    "agency": "Office of Administration, Facilities Management Design & Construction",
    # The landing page carries ONE unrelated PDF; the bid documents live one
    # level down. The source workbook said "2 clicks from portal to spec PDF"
    # and the first version of this adapter collapsed that to one -- discover()
    # returned a single "OA Periodic Rule Review" and the checker failed it.
    # That failure is the contract working: a plausible-looking adapter that
    # scrapes the wrong page is exactly what a self-report would have hidden.
    "listing_url": "https://oa.mo.gov/facilities/bid-opportunities/bid-listing-electronic-plans",
    "landing_url": "https://oa.mo.gov/facilities/bid-opportunities",
    "needs_browser": False,
    "needs_headers": False,
}

# A real browser UA by default. Costs nothing when unnecessary and is the
# difference between 245 bytes and 9MB on WAF-protected hosts (see Delaware).
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0  # a ban is permanent loss of the source

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, timeout: float = 90) -> tuple[int, bytes]:
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
    """What this host serves for a path that cannot exist."""
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/zzz-specindex-not-real-9174.pdf")
        _baseline[host_root] = body
    return _baseline[host_root]


# Missouri names its files by role, and only one of the four is the spec book:
#   _<PROJ> Final Bid Specs.pdf      <- the project manual, CSI divisions
#   _<PROJ> Final Bid Plans.pdf      <- drawings
#   _<PROJ> Final Bid Documents.pdf  <- combined package
#   <PROJ> IFB.pdf                   <- invitation for bid, no CSI content
# Ranking matters: grabbing whatever PDF appears first returns a bid form and
# the portal looks like it holds no specifications.
_SPEC_FIRST = ("final bid specs", "project manual", "specification",
               "final bid documents")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    """Sub-page carries ~1,200 direct PDF links, no JS. Grouped by project
    number so each entry offers its spec book first."""
    status, body = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    by_project: dict[str, dict] = {}
    for m in re.finditer(r'href="([^"]+\.pdf[^"]*)"', html, re.I):
        href = m.group(1)
        url = href if href.startswith("http") else urllib.parse.urljoin(PORTAL["listing_url"], href)
        fname = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        # NO \b BEFORE THE LETTER. Missouri prefixes its spec files with an
        # underscore ("_O2512-01 - Final Specs.pdf"), and `_` is a word
        # character, so `\b[A-Z]` never matches there. Every underscored file
        # -- which is to say every spec book -- landed under project_id
        # "unknown" in GCS. Same failure the shared classifier documents for
        # `\bamd\b` against "Amd_1.pdf".
        num = re.search(r"([A-Z]\d{4}-\d{2})", fname)
        key = num.group(1) if num else fname
        e = by_project.setdefault(key, {
            "project_name": key, "project_number": num.group(1) if num else None,
            "bid_date": None, "doc_urls": [],
        })
        if url not in e["doc_urls"]:
            e["doc_urls"].append(url)

    out = []
    for e in by_project.values():
        e["doc_urls"].sort(key=_rank)   # spec book first
        out.append(e)
        if len(out) >= limit:
            break
    return out


def fetch(url: str) -> bytes | None:
    """Content-checked. Status alone never decides."""
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
