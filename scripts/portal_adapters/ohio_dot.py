"""ODOT -- Ohio DOT bidding documents, DigitalPaper XE (Tier 1, DOT).

Proven end to end 2026-08-06: PASS, 2,117,347 bytes, DOT spec sections +
measurement/payment. Documents are reachable anonymously, with no cart or
purchase:

    POST /document/documentSearch.do  (cabinetId=1003 Proposals)
    GET  /document/downloadDocument.do?documentId=1088002&cabinetId=1003
        2,117,347 bytes -- "January 15, 2026 / Project Number: 260001 /
        PID #: 114536 / BRIDGE REPLACEMENT (1 BRIDGE) / CUY-IR 71-10.07 /
        PROPOSAL / STATE OF OHIO DEPARTMENT OF TRANSPORTATION"

CALIBRATION NOTE. ODOT proposals are written against the ODOT Construction &
Material Specifications "Item 6nn" numbering. No proposal sampled carried a CSI
section number, a PART 1/2/3 skeleton or an arabic DIVISION heading in its first
25 pages.

TRAPS THIS ADAPTER WALKED INTO:
1. The spreadsheet URL is a SharePoint page holding exactly one PDF (the prebid
   questions log) and a "Sign In" link. Read alone it looks gated. The bidding
   documents are on a separate ePlus DigitalPaper host reached by one link:
   http://contracts.dot.state.oh.us/home.do
2. The search form's submit handler calls submitAction(this.form) with no action
   argument, so the form's own POST target is NOT the search endpoint. Posting
   to documentSearchCriteria.do returns the criteria page again at HTTP 200 --
   a silent zero that looks like "no results". The real endpoint is
   /document/documentSearch.do, and the session cookie from the criteria page
   must be carried across (a cookie jar, not just the jsessionid path segment).
"""
from __future__ import annotations
import http.cookiejar
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Ohio",
    "type": "DOT",
    "tier": 1,
    "agency": "Ohio Department of Transportation, Office of Contract Sales",
    "listing_url": "https://contracts.dot.state.oh.us/document/documentSearchCriteria.do?from=topNav",
    "landing_url": ("https://www.dot.state.oh.us/Divisions/ContractAdmin/Contracts/"
                    "Pages/Bidding-Documents.aspx"),
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
_HOST = "https://contracts.dot.state.oh.us"
_SEARCH = _HOST + "/document/documentSearch.do"
_DOWNLOAD = _HOST + "/document/downloadDocument.do?documentId=%s&cabinetId=%s"

# DigitalPaper cabinets. Proposals first: Plans are drawing sheets and Addenda
# only amend. Ranking by whatever the search returns first buys a bid tab.
_CABINETS = (("1003", "Proposals"), ("1000", "Addenda"))

# Ohio project numbers are YYnnnn. Wildcard by the two most recent years so the
# result set is current work rather than the 2002 lettings the unfiltered search
# returns first.
_YEAR_PREFIXES = ("26", "25")

_opener: urllib.request.OpenerDirector | None = None
_baseline: dict[str, bytes] = {}


def _session() -> urllib.request.OpenerDirector:
    """A fresh cookie jar seeded by loading the criteria page."""
    global _opener
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA), ("Accept", "text/html,application/pdf,*/*")]
    try:
        op.open(PORTAL["listing_url"], timeout=120).read()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(PAUSE)
    _opener = op
    return op


def _post(url: str, fields: dict, referer: str) -> tuple[int, bytes]:
    op = _opener or _session()
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": referer})
    try:
        r = op.open(req, timeout=180)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _fetch_raw(url: str) -> tuple[int, bytes]:
    op = _opener or _session()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": _SEARCH})
    try:
        r = op.open(req, timeout=600)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _attr(seg: str, name: str) -> str | None:
    m = re.search(name + r':\s*</span>.*?thumb-attribute-value">([^<]*)', seg, re.S)
    return m.group(1).strip() if m else None


def discover(limit: int = 50) -> list[dict]:
    _session()
    out: list[dict] = []
    for cab_id, cab_name in _CABINETS:
        for prefix in _YEAR_PREFIXES:
            if len(out) >= limit:
                break
            status, body = _post(_SEARCH, {
                "from": "topNav", "actionMode": "submit", "newSearch": "true",
                "resortedSearch": "false", "fromHomePage": "false", "addTo": "",
                "displayModeSorted": "", "clientWidth": "1200", "tabId": "",
                "fetchCurrent": "false", "cabinetId": cab_id,
                "DP.PROJECT_NUM.TEXT": prefix + "*", "DP.DOCUMENT_TYPE.TEXT": "",
                "crossDocPakSearch": "false", "orFlag": "false",
                "displayMode": "condensed", "hitsPerPage": str(max(limit, 20)),
            }, referer=PORTAL["listing_url"])
            time.sleep(PAUSE)
            if status != 200 or b"Document Search Results" not in body:
                continue   # content-check: the criteria page also answers 200
            page = body.decode("utf-8", "ignore")
            rows = [(m.group(1), m.start()) for m in
                    re.finditer(r'name="documentId" value="(\d+)"', page)]
            for pos, (doc_id, start) in enumerate(rows):
                end = rows[pos + 1][1] if pos + 1 < len(rows) else len(page)
                seg = page[start:end]
                num = _attr(seg, "PROJECT_NUM") or doc_id
                out.append({
                    "project_name": f"{num} {(_attr(seg, 'RT_SECTION') or '').strip()}".strip(),
                    "project_number": num,
                    "bid_date": _attr(seg, "LET_DATE"),
                    "doc_urls": [_DOWNLOAD % (doc_id, cab_id)],
                })
                if len(out) >= limit:
                    break
    return out


def fetch(url: str) -> bytes | None:
    status, body = _fetch_raw(url)
    time.sleep(PAUSE)
    if status != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    return body


if __name__ == "__main__":
    found = discover(limit=6)
    print(f"discover() -> {len(found)} projects, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
    for f in found:
        print(" ", f["bid_date"], f["project_number"], f["project_name"][:50])
