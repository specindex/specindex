"""WSDOT -- Washington State DOT public works contracts (Tier 1, DOT).

Proven end to end 2026-08-06: contract XE3757 (Tumwater RHQ Building Demolition)
returned a 29,681,240-byte project manual whose page 1 is
``00 01 00 TABLE OF CONTENTS`` followed by ``DIVISION 00 BIDDING AND CONTRACT
REQUIREMENTS`` -- CSI section numbers and division headings, no login.

TRAP THIS ADAPTER WALKED INTO:
The spreadsheet URL (search-contracting-opportunities) is a Drupal *landing*
page. Its per-contract detail pages carry only a bid tabulation PDF and a link
reading "order plans and specifications", which reads as a paywall. The actual
documents are one host away, in an anonymous IIS directory listing linked from
the contract-documents-archive page as "Active Contracts Directory":

    https://ftp.wsdot.wa.gov/contracts/<CONTRACT>/Plans&Specifications/

392 contract folders, no authentication. A discover() written against the
landing page returns zero documents and the portal looks dead.

Second trap: that IIS listing emits ``<A HREF=...>`` in UPPERCASE. A
case-sensitive href regex returns 0 links against a 60,091-byte body -- a
silent zero, not an error.
"""
from __future__ import annotations
import re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime

PORTAL = {
    "state": "Washington",
    "type": "DOT",
    "tier": 1,
    "agency": "Washington State Department of Transportation, Contract Ad & Award",
    "listing_url": "https://ftp.wsdot.wa.gov/contracts/",
    "landing_url": "https://wsdot.wa.gov/business-wsdot/contracts/search-contracting-opportunities",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

_baseline: dict[str, bytes] = {}
# The subfolder that holds bid documents. Addenda/Q&A/PlanHolders do not.
_DOC_FOLDER = "Plans&Specifications"


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


def _iis_entries(url: str) -> list[tuple[datetime | None, str]]:
    """Parse an IIS directory listing. NOTE the re.I -- hrefs are uppercase."""
    status, body = _get(url)
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    out: list[tuple[datetime | None, str]] = []
    for m in re.finditer(
        r'(?:(\d{1,2}/\d{1,2}/\d{4})\s+\d{1,2}:\d{2}\s+[AP]M)?[^<]*<a\s+href="([^"]+)"',
        html, re.I,
    ):
        stamp, href = m.group(1), m.group(2)
        if href.rstrip("/").endswith("/contracts") or href == "/":
            continue
        when = None
        if stamp:
            try:
                when = datetime.strptime(stamp, "%m/%d/%Y")
            except ValueError:
                when = None
        out.append((when, urllib.parse.urljoin(url, href)))
    return out


# WSDOT names the project manual "<something>Specs.pdf"; the drawing volumes are
# "...Plans Volume 1.pdf". Grabbing the first PDF returns a drawing set, which
# carries no CSI text and makes the contract look specification-free.
_SPEC_FIRST = ("specs", "specification", "provisions", "proposal")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    if "plan" in low and "spec" not in low:
        return len(_SPEC_FIRST) + 1
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    contracts = _iis_entries(PORTAL["listing_url"])
    # newest first; undated entries last
    contracts.sort(key=lambda t: t[0] or datetime(1970, 1, 1), reverse=True)
    out: list[dict] = []
    attempts = 0
    budget = max(limit * 4, 20)
    t0 = time.time()
    for _, cdir in contracts:
        if len(out) >= limit or attempts >= budget:
            break
        attempts += 1
        name = urllib.parse.unquote(cdir.rstrip("/").rsplit("/", 1)[-1])
        docs = [u for _, u in _iis_entries(cdir + urllib.parse.quote(_DOC_FOLDER) + "/")
                if u.lower().endswith(".pdf")]
        if not docs:
            continue
        docs.sort(key=_rank)
        num = name.split("-", 1)[0]
        out.append({
            "project_name": name,
            "project_number": num or None,
            "bid_date": None,
            "doc_urls": docs,
        })
        if attempts % 5 == 0:
            el = time.time() - t0
            rate = attempts / el * 60 if el else 0
            print(f"  [wsdot {len(out)}/{limit}] {attempts} dirs probed, "
                  f"{rate:.0f}/min, ETA {(limit - len(out)) * (el / max(len(out), 1)):.0f}s",
                  file=sys.stderr)
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


if __name__ == "__main__":  # assert the next step can see the output
    found = discover(limit=3)
    print(f"discover() -> {len(found)} projects, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
    for f in found:
        print(" ", f["project_name"], f["doc_urls"][0].rsplit("/", 1)[-1])
