"""Florida MyFloridaMarketPlace -- Vendor Information Portal advertisements.

An Angular SPA over a Spring API. Everything here is content-negotiated, and
that is the whole trick:

    GET  /mfmp/bids/detail/attachment/download?attachmentId=N

returns the SPA's index.html -- 1,132 bytes, HTTP 200 -- when the request's
Accept header admits text/html, and the actual PDF when Accept is
`application/json`. The same URL, the same status code, two different resources.
Probing it with `Accept: */*` produced the shell and would have been recorded as
"attachment endpoint not found". 1,132 bytes is this host's soft-404 signature
and is baselined below.

The rest of the API:

    POST /mfmp/pub/search/bids        {"title": "...", "type": ["4","6"], ...}
    GET  /mfmp/pub/search/bids/detail?id=<advertisementId>   -> `docs` array

The search body must carry at least one non-empty criterion. An all-empty body
returns `[]` with HTTP 200 -- confirmed in a real browser, so it is the API's
behaviour and not a header problem -- which reads exactly like "Florida has no
open solicitations". Keyword terms are therefore issued explicitly.

Most Florida advertisements attach only an award notice or a bid tabulation.
The CSI-bearing files are the ones whose names say SPECS or Technical
Specifications, e.g. `BLACK CREEK_IFB_SPECS_06152022.pdf`.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Florida",
    "type": "Vertical",
    "tier": 1,
    "agency": "Dept. of Management Services -- MyFloridaMarketPlace (VIP)",
    "listing_url": "https://vendor.myfloridamarketplace.com/search/bids",
    "search_api": "https://vendor.myfloridamarketplace.com/mfmp/pub/search/bids",
    "detail_api": "https://vendor.myfloridamarketplace.com/mfmp/pub/search/bids/detail?id={id}",
    "download_api": "https://vendor.myfloridamarketplace.com/mfmp/bids/detail/"
                    "attachment/download?attachmentId={aid}",
    "needs_browser": False,
    "needs_headers": True,   # Accept: application/json decides PDF vs SPA shell
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
HOST = "https://vendor.myfloridamarketplace.com"

# Search terms -- the API will not return anything for an empty criteria set.
TERMS = ("construction", "renovation", "roof", "hvac", "building")
# 4 = Invitation to Bid, 6 = Request for Proposals.
AD_TYPES = ("4", "6")

_baseline: dict[str, bytes] = {}

_SPEC_FIRST = ("spec", "technical", "project manual", "part 2", "solicitation",
               "itb", "ifb", "addendum", "addenda")
_NEVER = ("bid tab", "tabulation", "award", "intent to", "short list",
          "withdrawal", "notice", "advertisement", "q&a", "question")


def _get(url: str, data: bytes | None = None, extra: dict | None = None,
         timeout: float = 240) -> tuple[int, bytes]:
    # Deliberately NOT text/html: this API serves the SPA shell to anything
    # that will accept HTML, including for valid document ids.
    h = {"User-Agent": UA, "Accept": "application/json",
         "Accept-Language": "en-US,en;q=0.9"}
    if extra:
        h.update(extra)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h, data=data),
                                    timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _soft404() -> bytes:
    if "shell" not in _baseline:
        _, body = _get(PORTAL["download_api"].format(aid=0))
        _baseline["shell"] = body
    return _baseline["shell"]


def _rank(name: str, desc: str) -> int:
    low = f"{name} {desc}".lower()
    if any(n in low for n in _NEVER):
        return 90
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _search(term: str, page: int = 1) -> list[dict]:
    body = {"pageSize": 25, "type": list(AD_TYPES), "status": [], "agency": [],
            "adNumber": "", "agencyAdvertisementNumber": "", "title": term,
            "publishedDate": "", "openDate": "", "endDate": "",
            "commodityCodes": [], "intendsToParticipate": "", "assignee": "",
            "page": page}
    st, b = _get(PORTAL["search_api"], data=json.dumps(body).encode(),
                 extra={"Content-Type": "application/json",
                        "Referer": PORTAL["listing_url"]})
    if st != 200 or b.lstrip()[:1] != b"[":
        return []
    try:
        return json.loads(b)
    except Exception:  # noqa: BLE001
        return []


def discover(limit: int = 50) -> list[dict]:
    ads: dict[int, dict] = {}
    for term in TERMS:
        for r in _search(term):
            if r.get("advertisementId") is not None:
                ads.setdefault(r["advertisementId"], r)
        time.sleep(PAUSE)
    if not ads:
        return []

    out: list[dict] = []
    rows = list(ads.values())
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        aid = r["advertisementId"]
        st, d = _get(PORTAL["detail_api"].format(id=aid),
                     extra={"Referer": PORTAL["listing_url"]})
        time.sleep(PAUSE)
        if st != 200 or d.lstrip()[:1] != b"{":
            continue
        try:
            docs_raw = json.loads(d).get("docs") or []
        except Exception:  # noqa: BLE001
            continue
        docs = []
        for a in docs_raw:
            fn = a.get("fileName") or ""
            if not fn.lower().endswith(".pdf") or a.get("attachmentId") is None:
                continue
            docs.append((_rank(fn, a.get("description") or ""),
                         PORTAL["download_api"].format(aid=a["attachmentId"])))
        docs = [x for x in docs if x[0] < 90]
        if not docs:
            continue
        docs.sort()
        out.append({
            "project_name": r.get("title") or "",
            "project_number": r.get("agencyAdNumber") or r.get("uniqueName"),
            "bid_date": (r.get("closeDate") or "")[:10] or None,
            "doc_urls": [x[1] for x in docs],
            "_best_rank": docs[0][0],
        })
        el = time.time() - t0
        print(f"[{i}/{len(rows)}] {len(out)} with docs  {i / el * 60:.0f}/min "
              f"ETA {(len(rows) - i) * el / i:.0f}s", file=sys.stderr)
        if sum(1 for e in out if e["_best_rank"] < 2) >= limit:
            break

    out.sort(key=lambda e: e["_best_rank"])
    return out[:limit]


def fetch(url: str) -> bytes | None:
    st, body = _get(url, extra={"Referer": PORTAL["listing_url"]})
    time.sleep(PAUSE)
    if st != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    if body == _soft404():
        return None
    return body
