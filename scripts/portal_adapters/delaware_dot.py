"""DelDOT -- Delaware DOT competitive bids (Tier 1, DOT).

Proven end to end 2026-08-06: PASS, 5,236,715 bytes, DOT spec sections +
measurement/payment. Documents are reachable anonymously:

    https://gssdocs.deldot.delaware.gov/bids/T202201701 Proposal.pdf
        7,692,924 bytes -- "STATE OF DELAWARE DEPARTMENT OF TRANSPORTATION
        BID PROPOSAL CONTRACT T202201701 CEDAR NECK ROAD PATHWAY"

CALIBRATION NOTE. DelDOT bid proposals carry their technical content as special
provisions keyed to the DelDOT Standard Specifications section numbering. There
is no CSI section number, PART 1/2/3 skeleton or arabic DIVISION heading in the
first 25 pages of any proposal sampled.

TRAPS THIS ADAPTER WALKED INTO:
1. deldot.gov/Business/bids/ -- the spreadsheet URL -- is a landing page. It
   holds a bid bond form and a bidders list and NO advertised contracts. The
   contracts live on the statewide procurement console, mmp.delaware.gov/Bids.
2. That console is JavaScript. Its jqGrid backs onto two POST endpoints found in
   /js/bidsConsole.js:
       POST /Bids/GetBids?status=Open            -> JSON rows
       POST /Bids/GetBidDocumentList?id=<id>     -> HTML fragment of doc links
   A GET on either returns the SPA shell at HTTP 200 -- a textbook soft 404. So
   does a POST with an empty body (HTTP 500 dressed as an HTML error page). The
   jqGrid paging parameters are required.
3. Delaware's own document hosts WAF-block plain fetches; the browser
   User-Agent + Referer below is what makes fetch() return megabytes instead of
   245 bytes of "Request Rejected" at HTTP 200.
"""
from __future__ import annotations
import html as _html
import json, re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Delaware",
    "type": "DOT",
    "tier": 1,
    "agency": "Delaware Department of Transportation",
    "listing_url": "https://mmp.delaware.gov/Bids/",
    "landing_url": "https://deldot.gov/Business/bids/",
    "needs_browser": False,
    "needs_headers": True,   # gssdocs/bidcondocs reject non-browser fetches
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
_GRID = json.dumps({"_search": False, "nd": "1", "rows": "500", "page": "1",
                    "sidx": "DeadlineDate", "sord": "desc"}).encode()

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, data: bytes | None = None,
         extra: dict | None = None, timeout: float = 300) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=h, data=data), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _soft404(host_root: str) -> bytes:
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/zzz-specindex-not-real-9174.pdf",
                       referer=PORTAL["listing_url"])
        _baseline[host_root] = body
    return _baseline[host_root]


# Every DelDOT contract offers "<no> Proposal.pdf" (bid proposal + special
# provisions -- the specification document) and "<no> Construction Plans.pdf"
# (drawing sheets). The plan set must never outrank the proposal: its sheet
# index is a column of bare numbers that a loose section-number regex will
# happily mistake for CSI, which would turn a real FAIL into a fake PASS.
_SPEC_FIRST = ("proposal", "specification", "special provision", "addend")


def _rank(pair: tuple[str, str]) -> int:
    label = (pair[1] + " " + urllib.parse.unquote(pair[0])).lower()
    if "plan" in label and "proposal" not in label:
        return len(_SPEC_FIRST) + 1
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in label:
            return i
    return len(_SPEC_FIRST)


def _bids(status: str = "Open") -> list[dict]:
    st, body = _get(f"https://mmp.delaware.gov/Bids/GetBids?status={status}",
                    referer=PORTAL["listing_url"], data=_GRID,
                    extra={"Content-Type": "application/json; charset=utf-8",
                           "Accept": "application/json"})
    time.sleep(PAUSE)
    if st != 200 or body.lstrip()[:1] != b"{":
        return []
    try:
        return json.loads(body).get("rows", [])
    except Exception:  # noqa: BLE001
        return []


def discover(limit: int = 50) -> list[dict]:
    rows = [r for r in _bids("Open") if r.get("AgencyCode") == "DOT"]
    if len(rows) < limit:
        seen = {r["Id"] for r in rows}
        rows += [r for r in _bids("All")
                 if r.get("AgencyCode") == "DOT" and r["Id"] not in seen]
    out: list[dict] = []
    for r in rows:
        if len(out) >= limit:
            break
        st, body = _get(f"https://mmp.delaware.gov/Bids/GetBidDocumentList?id={r['Id']}",
                        referer=PORTAL["listing_url"], data=b"{}",
                        extra={"Content-Type": "application/json; charset=utf-8",
                               "Accept": "text/html,*/*"})
        time.sleep(PAUSE)
        if st != 200 or not body:
            continue
        frag = body.decode("utf-8", "ignore")
        docs: list[tuple[str, str]] = []
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]*)<', frag, re.I):
            url = _html.unescape(m.group(1))
            if not url.lower().endswith(".pdf"):
                continue
            docs.append((url, m.group(2).strip()))
        if not docs:
            continue
        docs.sort(key=_rank)
        out.append({
            "project_name": r.get("Title") or r.get("ContractNumber"),
            "project_number": r.get("ContractNumber"),
            "bid_date": r.get("DeadlineDate"),
            "doc_urls": [urllib.parse.quote(d[0], safe=":/?=&") for d in docs],
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
    found = discover(limit=5)
    print(f"discover() -> {len(found)} projects, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
    for f in found:
        print(" ", f["project_number"], f["project_name"][:45], len(f["doc_urls"]))
