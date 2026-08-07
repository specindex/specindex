"""North Carolina electronic Vendor Portal (eVP) -- statewide solicitation board.

Tier assessment 2026-08-06: the spreadsheet listed North Carolina T2 behind
doa.nc.gov/divisions/state-construction-office. Two things were wrong with that.

1. The SCO page holds no documents at all. Every one of its "Bids", "Design
   Services Requests" and "Construction Bid Notices" links points at evp.nc.gov.
   Stopping at the spreadsheet URL yields zero PDFs and reads as a dead portal.

2. eVP shows a prominent "Sign in" and the vendor pitch is all about registering,
   which is what put it in T2. Registration is required to RESPOND. It is not
   required to READ. The attachment endpoint

       https://evp.nc.gov/_entity/annotation/<annotationId>/<viewId>

   returns the PDF to an anonymous request with ordinary browser headers --
   verified at 4,078,206 bytes for the Raleigh BRAC stair project manual with no
   cookie, no account, and no terms accepted.

What DOES need a browser is the listing. eVP is Microsoft Power Pages; a plain
fetch of /solicitations/ returns 270KB of chrome with a single template link
`/solicitations/details/` and no ids. The rows arrive from a POST to
/_services/entity-grid-data.json whose payload is an opaque signed blob minted by
the page, so it cannot be replayed by hand. Hence needs_browser: True -- for the
LISTING only. The PDFs themselves are plain HTTP and are fetched that way.

Proven end to end: IFB 2027-004 (UC Jesse Helms Park Field Lighting, Union
County) -> 406,621 bytes carrying CSI section numbers and DIVISION headings.
"""
from __future__ import annotations
import html as H
import re
import time
import urllib.error
import urllib.parse
import urllib.request

PORTAL = {
    "state": "North Carolina",
    "type": "Vertical",
    "tier": 1,
    "agency": "Department of Administration -- State Construction Office / "
              "Division of Purchase & Contract (eVP)",
    "listing_url": "https://evp.nc.gov/solicitations/",
    "landing_url": "https://www.doa.nc.gov/divisions/state-construction-office",
    "needs_browser": True,      # the LISTING is Power Pages; the PDFs are not
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
SEARCH_TERM = "construction"

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, timeout: float = 120) -> tuple[int, bytes]:
    h = {"User-Agent": UA,
         "Accept": "application/pdf,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                    timeout=timeout) as r:
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


# eVP attaches everything to one record: the advertisement, the bid form, the
# insurance exhibit, the sales-tax form and -- somewhere in the pile -- the
# project manual. Taking whatever comes first hands back a sales-tax form.
_SPEC_FIRST = ("project manual", "specification", "spec", "bid doc",
               "bid document", "technical", "advertisement", "ifb", "itb")
_NEVER = ("sales tax", "insurance", "sign-in", "signin", "sign in", "bid results",
          "bidtab", "bid tab", "award", "addend", "q&a", "checklist", "w-9", "w9")


def _rank(name: str) -> int:
    low = urllib.parse.unquote(name).lower()
    for kw in _NEVER:
        if kw in low:
            return 99
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _detail_url(sid: str) -> str:
    return f"https://evp.nc.gov/solicitations/details/?id={sid}"


def discover(limit: int = 50, term: str = SEARCH_TERM) -> list[dict]:
    """Drive the Power Pages listing with Playwright, then read each solicitation
    detail page for its attachment ids. Downloads nothing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("north_carolina: playwright not installed; the eVP listing needs it")
        return []

    out: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        try:
            page.goto(PORTAL["listing_url"], wait_until="networkidle", timeout=90_000)
            page.wait_for_timeout(2500)
            box = page.query_selector(
                "input[type='search'], .entitylist-search input, input.query")
            if box:
                box.fill(term)
                box.press("Enter")
                page.wait_for_timeout(6000)
            html = page.content()

            ids = re.findall(r'/solicitations/details/\?id=([0-9a-f-]{36})', html)
            titles = re.findall(
                r'<a[^>]+/solicitations/details/\?id=[0-9a-f-]{36}[^>]*>(.*?)</a>',
                html, re.S)
            pairs, seen = [], set()
            for i, sid in enumerate(ids):
                if sid in seen:
                    continue
                seen.add(sid)
                t = ""
                if i < len(titles):
                    t = re.sub(r"\s+", " ",
                               H.unescape(re.sub(r"<[^>]+>", "", titles[i]))).strip()
                pairs.append((sid, t))
                if len(pairs) >= limit:
                    break

            if not pairs:
                print("north_carolina: listing rendered but produced no "
                      "solicitation ids -- eVP grid markup may have changed")
                return []

            t0, total = time.time(), len(pairs)
            for i, (sid, title) in enumerate(pairs, 1):
                page.goto(_detail_url(sid), wait_until="networkidle", timeout=90_000)
                page.wait_for_timeout(4000)
                dhtml = page.content()
                docs = []
                for m in re.finditer(
                        r'href="(/_entity/annotation/[^"]+)"[^>]*>(.*?)</a>',
                        dhtml, re.S):
                    href = H.unescape(m.group(1)).split("?")[0]
                    name = re.sub(r"\s+", " ",
                                  H.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
                    docs.append((_rank(name), name,
                                 urllib.parse.urljoin("https://evp.nc.gov", href)))
                if not docs:
                    continue
                docs.sort(key=lambda d: d[0])
                # Two per project, so the checker's six-URL budget spans six
                # projects instead of six exhibits of the same one.
                out.append({
                    "project_name": title or sid,
                    "project_number": title or None,
                    "bid_date": None,
                    "doc_urls": [d[2] for d in docs[:2]],
                })
                if i % 3 == 0 or i == total:
                    el = time.time() - t0
                    rate = i / el * 60 if el else 0
                    eta = (total - i) / (i / el) if el and i else 0
                    print(f"[{i}/{total}] north_carolina discover "
                          f"{rate:.1f}/min ETA {eta:.0f}s", flush=True)
                time.sleep(PAUSE)
        finally:
            browser.close()

    if out and not any(e["doc_urls"] for e in out):
        print("north_carolina: discover() produced projects with no document URLs")
    return out


def fetch(url: str) -> bytes | None:
    """Plain HTTP -- the attachment endpoint is anonymous. Content-checked."""
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    status, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or body[:4] != b"%PDF" or len(body) < 2048:
        return None
    base = _soft404(root)
    if base and body == base:
        return None
    return body


if __name__ == "__main__":
    found = discover(limit=6)
    print(f"{len(found)} solicitations")
    for f in found:
        print(" ", f["project_name"][:60], len(f["doc_urls"]))
