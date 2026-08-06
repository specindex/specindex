"""Maine BGS (Bureau of General Services) -- Business Opportunities.

The listing page is plain server-rendered Drupal and carries ~400 direct PDF
links across all open and recently-closed projects. Files are named by role and
grouped by a 4-digit BGS project number:

    3843_Legal_Ad_DAFS.pdf              <- newspaper ad, no CSI
    3843_Notice_to_Contractors_DAFS.pdf <- notice, no CSI
    3843_Project_Manual_DAFS.pdf        <- THE SPEC BOOK
    3843_Drawings_DAFS.pdf              <- drawings
    3843_Addendum_1_DAFS.pdf            <- addenda

Same trap as Missouri: the legal ad sorts first alphabetically and by document
order, so an unranked adapter downloads a one-page newspaper notice and the
portal looks like it holds no specifications.
"""
from __future__ import annotations
import re, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Maine",
    "type": "Vertical",
    "tier": 1,
    "agency": "Dept. of Administrative & Financial Services, Bureau of General Services",
    "listing_url": "https://www.maine.gov/dafs/bgs/business-opportunities",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, timeout: float = 120) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
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


# Ranked most-spec-like first. "project manual" and "specifications" are the
# CSI-structured documents; ads, notices and bid tabs never are.
_SPEC_FIRST = ("project_manual", "project manual", "specification",
               "_manual", "addendum", "drawings")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower().replace("%20", " ")
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    status, body = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    by_project: dict[str, dict] = {}
    for m in re.finditer(r'href="([^"]+\.pdf[^"]*)"', html, re.I):
        url = urllib.parse.urljoin(PORTAL["listing_url"], m.group(1))
        fname = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        num = re.match(r"(\d{4})[_ ]", fname)
        key = num.group(1) if num else re.split(r"[_ ]", fname)[0]
        e = by_project.setdefault(key, {
            "project_name": key,
            "project_number": num.group(1) if num else None,
            "bid_date": None, "doc_urls": [],
        })
        if url not in e["doc_urls"]:
            e["doc_urls"].append(url)

    # Projects that actually offer a spec-class document come first, so the
    # checker's 6-URL budget is not spent on ad-only entries.
    entries = list(by_project.values())
    for e in entries:
        e["doc_urls"].sort(key=_rank)
    entries.sort(key=lambda e: _rank(e["doc_urls"][0]) if e["doc_urls"] else 99)
    return entries[:limit]


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
