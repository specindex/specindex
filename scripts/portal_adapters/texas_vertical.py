"""Texas ESBD (Electronic State Business Daily) on txsmartbuy.gov.

The ESBD is a NetSuite SuiteCommerce storefront, so nothing is in the served
HTML. Two undocumented services carry everything:

    POST /app/extensions/CPA/CPAMain/1.0.0/services/ESBD.Service.ss
         body {"lines":[],"page":N,"urlRoot":"esbd"}   -> 24 rows/page
    GET  .../ESBD.Details.Service.ss?identification=<solicitationId>
         -> the same row plus an `attachments` array

Traps this portal sets:

* The list service takes no keyword or category filter. The search box on the
  page issues the SAME payload -- verified by capturing the XHR while typing
  "construction" -- so any adapter that appears to search is really pulling
  pages blind. 58,801 records exist; vertical work is found by paging and
  filtering titles locally.
* Attachment fileURLs are NetSuite media links (`/core/media/media.nl?id=...`)
  whose `_xt` extension, not the fileName, tells you the real type: a file
  named `.docx` is served with `_xt=.doc`.
* Every Texas solicitation ships the same four boilerplate PDFs -- direct
  deposit authorization, Texas Identification Number application, standard terms
  and conditions, subcontracting plan. All four are large, real PDFs with zero
  CSI content. Taking the biggest or the first attachment gets a tax form.
  The project manual is the file whose description says "Solicitation".
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Texas",
    "type": "Vertical",
    "tier": 1,
    "agency": "Comptroller of Public Accounts / Texas Facilities Commission (ESBD)",
    "listing_url": "https://www.txsmartbuy.gov/esbd",
    "list_api": "https://www.txsmartbuy.gov/app/extensions/CPA/CPAMain/1.0.0/"
                "services/ESBD.Service.ss?c=852252&n=2",
    "detail_api": "https://www.txsmartbuy.gov/app/extensions/CPA/CPAMain/1.0.0/"
                  "services/ESBD.Details.Service.ss?c=852252&email="
                  "&identification={sid}&n=2&optOutKey=&urlRoot=esbd",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
HOST = "https://www.txsmartbuy.gov"

_baseline: dict[str, bytes] = {}

_VERTICAL = re.compile(
    r"renovat|remodel|building|hvac|roof|chiller|boiler|restroom|facility|"
    r"construction|replacement project|mechanical|electrical|plumbing|"
    r"fire alarm|elevator|painting", re.I)
_NOT_VERTICAL = re.compile(
    r"blanket purchase|o\.e\.m\.|conference|catering|uniform|food|vehicle|"
    r"software|staffing|consulting|network|hardware", re.I)

_SPEC_FIRST = ("solicitation", "specification", "project manual", "technical",
               "addendum", "amendment", "ifb", "rfp", "itb")
# Boilerplate every Texas posting carries; none of it is CSI.
_NEVER = ("direct deposit", "identification number", "ap-152", "74-176",
          "terms and conditions", "subcontracting plan", "hsp", "vethub",
          "notification", "sample contract", "instructions")


def _get(url: str, referer: str | None = None, data: bytes | None = None,
         extra: dict | None = None, timeout: float = 240) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,application/json,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
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


def _soft404(host_root: str) -> bytes:
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/core/media/media.nl?id=0&c=852252&_xt=.pdf",
                       referer=PORTAL["listing_url"])
        _baseline[host_root] = body
    return _baseline[host_root]


def _rank(name: str, desc: str) -> int:
    low = f"{name} {desc}".lower()
    if any(n in low for n in _NEVER):
        return 90
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _page(n: int) -> list[dict]:
    st, b = _get(PORTAL["list_api"], referer=PORTAL["listing_url"],
                 data=json.dumps({"lines": [], "page": n, "urlRoot": "esbd"}).encode(),
                 extra={"Content-Type": "application/json"})
    if st != 200 or b.lstrip()[:1] != b"{":
        return []
    try:
        return json.loads(b).get("lines", []) or []
    except Exception:  # noqa: BLE001
        return []


def discover(limit: int = 50, pages: int = 10) -> list[dict]:
    cands: list[dict] = []
    for n in range(1, pages + 1):
        rows = _page(n)
        time.sleep(PAUSE)
        if not rows:
            break
        for r in rows:
            t = r.get("title") or ""
            if _VERTICAL.search(t) and not _NOT_VERTICAL.search(t):
                cands.append(r)
    if not cands:
        return []

    out: list[dict] = []
    t0 = time.time()
    for i, r in enumerate(cands, 1):
        sid = r.get("solicitationId") or ""
        st, b = _get(PORTAL["detail_api"].format(sid=urllib.parse.quote(sid)),
                     referer=PORTAL["listing_url"])
        time.sleep(PAUSE)
        if st != 200 or b.lstrip()[:1] != b"{":
            continue
        try:
            atts = json.loads(b).get("attachments") or []
        except Exception:  # noqa: BLE001
            continue
        docs = []
        for a in atts:
            fu = a.get("fileURL") or ""
            # `_xt` is authoritative; fileName lies about .docx/.doc.
            if "_xt=.pdf" not in fu and not fu.lower().endswith(".pdf"):
                continue
            docs.append((_rank(a.get("fileName") or "", a.get("fileDescription") or ""),
                         urllib.parse.urljoin(HOST, fu)))
        docs = [d for d in docs if d[0] < 90]
        if not docs:
            continue
        docs.sort()
        out.append({
            "project_name": r.get("title") or "",
            "project_number": sid,
            "bid_date": r.get("responseDue"),
            "doc_urls": [d[1] for d in docs],
            "_best_rank": docs[0][0],
        })
        el = time.time() - t0
        print(f"[{i}/{len(cands)}] {len(out)} with docs  {i / el * 60:.0f}/min "
              f"ETA {(len(cands) - i) * el / i:.0f}s", file=sys.stderr)
        if len(out) >= limit * 2:
            break

    out.sort(key=lambda e: e["_best_rank"])
    return out[:limit]


def fetch(url: str) -> bytes | None:
    st, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if st != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    base = _soft404(HOST)
    if base and body == base:
        return None
    return body
