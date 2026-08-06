"""HDOT -- Hawaii DOT "Current Bid Openings" (Tier 1 claim NOT confirmed).

THE SPREADSHEET ROW IS MISLABELLED. hidot.hawaii.gov/administration/con/
current-bid-openings/ is a bid RESULTS page, not a solicitation page. Its own
parent page, /administration/con/, titles the link "Current Bid Results" and
lists the siblings as "Prior Bid Results - FY2022 / FY2021 / FY2020". The 16
PDFs it serves are bid tabulations: RH1016-22.pdf is 12,635 bytes and reads
"PROJECT NO.: RH1016-22 / BID OPENING: 2:00 P.M., JULY 21, 2022 / BIDDER BID
AMOUNT". No plans, no proposals, no specifications. The adapter therefore FAILS
the checker, correctly.

WHERE THE REAL DOCUMENTS ARE, AND WHY THIS ADAPTER DOES NOT POINT AT THEM:
Hawaii DOT solicitations are issued through HIePRO, the state eProcurement
system. Individual HIePRO resources ARE anonymously downloadable and are genuine
Hawaii DOT specification books, verified 2026-08-06:

    https://hiepro.ehawaii.gov/resources/173899/
        Specifications-FINAL SPECIFICATIONS w NTB HWY C 32 25.pdf
        8,837,082 bytes -- "STATE OF HAWAII DEPARTMENT OF TRANSPORTATION
        HIGHWAYS ... SPECIAL PROVISIONS, SPECIFICATIONS, PROPOSAL AND CONTRACT"

But there is no anonymous LISTING to discover them from. hiepro.ehawaii.gov's
public pages expose only a vendor search; the aggregator hands.ehawaii.gov is an
Angular SPA whose opportunities API lives in a lazy-loaded chunk and whose
obvious REST paths (/hands/api/opportunities, /hands/rest/opportunities) return
the SPA shell at HTTP 200 -- soft 404s, not data. Discovery needs either that
chunk reverse-engineered or a browser session. Recorded as an open lead rather
than guessed at.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Hawaii",
    "type": "DOT",
    "tier": 1,
    "agency": "Hawaii Department of Transportation, Contracts Office",
    "listing_url": "https://hidot.hawaii.gov/administration/con/current-bid-openings/",
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


# If HDOT ever posts a specification alongside the tabulation, take it first.
_SPEC_FIRST = ("specification", "special provision", "proposal", "addend")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
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
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
            r'href="(https://hidot\.hawaii\.gov/administration/files/[^"]+\.pdf)"[^>]*>(.*?)</a>',
            html, re.I | re.S):
        url = m.group(1)
        if url in seen:
            continue
        seen.add(url)
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        out.append({
            "project_name": label or urllib.parse.unquote(url.rsplit("/", 1)[-1])[:-4],
            "project_number": label or None,
            "bid_date": None,
            "doc_urls": sorted([url], key=_rank),
        })
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
        print(" ", f["project_name"])
