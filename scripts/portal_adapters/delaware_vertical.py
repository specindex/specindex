"""Delaware MyMarketPlace Bids -- OMB/DFM public works solicitations.

Three findings, each of which independently produced a false "dead source":

1. bids.delaware.gov 302s to mmp.delaware.gov/Bids/, whose bid table is drawn
   by jqGrid from a JSON endpoint. Parsing the served HTML yields zero rows.
   The endpoint is POST /Bids/GetBids?status=Open with jqGrid paging params.

2. The document list is a SECOND ajax call, GET /Bids/GetBidDocumentList?id=N,
   returning an HTML fragment. It is not present in the detail response and not
   reachable by guessing (/BidDocs, /GetBidDocuments and /GetDocs all return the
   SPA shell at HTTP 200 -- textbook soft-404).

3. The PDFs live on bidcondocs.delaware.gov, which WAF-rejects requests without
   a browser User-Agent: 245 bytes of "Request Rejected" at HTTP 200. With a
   real UA and a Referer the same URL returns the full document -- 10,527,410
   bytes for OMB-MC3804000169-specs.pdf, verified 2026-08-06.

Delaware names files by role in the URL, and only "-specs" is the spec book;
"-rfp" is the public-works RFP boilerplate and "-wages" is a prevailing-wage
table that contains no CSI content at all.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Delaware",
    "type": "Vertical",
    "tier": 1,
    "agency": "Office of Management & Budget, Division of Facilities Management",
    "listing_url": "https://mmp.delaware.gov/Bids/",
    "landing_url": "https://bids.delaware.gov/",
    "bids_api": "https://mmp.delaware.gov/Bids/GetBids?status=Open",
    "docs_api": "https://mmp.delaware.gov/Bids/GetBidDocumentList?id={id}&currentCount=0",
    "needs_browser": False,   # the JSON endpoints are reachable without JS
    "needs_headers": True,    # bidcondocs.delaware.gov WAF-blocks bare fetches
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
DOC_REFERER = "https://bids.delaware.gov/"

_baseline: dict[str, bytes] = {}

_SPEC_FIRST = ("-specs", "specification", "project manual", "technical spec",
               "-addendum", "addendum", "-rfp", "-itb")
_NEVER = ("wages", "exemption", "prevailing", "bid tab", "award")


def _get(url: str, referer: str | None = None, data: bytes | None = None,
         extra: dict | None = None, timeout: float = 180) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,application/json,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    try:
        req = urllib.request.Request(url, headers=h, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _soft404(host_root: str) -> bytes:
    """These hosts answer unknown paths with 200 + a page, so baseline them."""
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/zzz-specindex-not-real-9174.pdf",
                       referer=DOC_REFERER)
        _baseline[host_root] = body
    return _baseline[host_root]


def _rank(url: str, label: str) -> int:
    low = (urllib.parse.unquote(url) + " " + label).lower()
    if any(n in low for n in _NEVER):
        return 90
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50, rows: int = 60) -> list[dict]:
    payload = json.dumps({"_search": False, "nd": int(time.time() * 1000),
                          "rows": rows, "page": 1,
                          "sidx": "OpenDate", "sord": "desc"}).encode()
    st, body = _get(PORTAL["bids_api"], referer=PORTAL["listing_url"], data=payload,
                    extra={"Content-Type": "application/json",
                           "X-Requested-With": "XMLHttpRequest"})
    time.sleep(PAUSE)
    if st != 200 or not body.lstrip()[:1] == b"{":
        return []
    try:
        bids = json.loads(body).get("rows", [])
    except Exception:  # noqa: BLE001
        return []

    out: list[dict] = []
    t0 = time.time()
    for i, b in enumerate(bids, 1):
        bid_id = b.get("Id")
        if bid_id is None:
            continue
        st, frag = _get(PORTAL["docs_api"].format(id=bid_id),
                        referer=PORTAL["listing_url"],
                        extra={"X-Requested-With": "XMLHttpRequest"})
        time.sleep(PAUSE)
        if st != 200 or not frag:
            continue
        docs = []
        for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>',
                             frag.decode("utf-8", "ignore"), re.I | re.S):
            u = m.group(1)
            if not u.lower().endswith(".pdf"):
                continue
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            docs.append((_rank(u, label), u, label))
        if not docs:
            continue
        docs.sort()
        out.append({
            "project_name": b.get("Title") or "",
            "project_number": b.get("ContractNumber"),
            "bid_date": b.get("DeadlineDate") or b.get("OpenDate"),
            "doc_urls": [d[1] for d in docs],
            "_best_rank": docs[0][0],
        })
        el = time.time() - t0
        print(f"[{i}/{len(bids)}] {len(out)} with docs  {i / el * 60:.0f}/min "
              f"ETA {(len(bids) - i) * el / i:.0f}s", file=sys.stderr)
        if sum(1 for e in out if e["_best_rank"] < 3) >= limit:
            break

    out.sort(key=lambda e: e["_best_rank"])
    return out[:limit]


def fetch(url: str) -> bytes | None:
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    st, body = _get(url, referer=DOC_REFERER)
    time.sleep(PAUSE)
    # The WAF rejection is HTTP 200 with a short HTML body -- status is useless
    # here, only the magic number and the length decide.
    if st != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    base = _soft404(root)
    if base and body == base:
        return None
    return body
