"""Iowa DAS Bidding Opportunities.

The listing is a DataTables grid; the served HTML contains no rows. Its source
is GET /Home/DT_HostedBidsSearch (plain JSON, no auth), and each bid's
attachments live on /Home/BidInfo?bidId=<guid> as
/Home/GetBidOpportunityDocument/<guid> links.

Two things this portal punishes:

* Most rows are commodity buys -- bakery products, athletic wear, snow blowers.
  Of 45 open bids only a handful are vertical construction, and 20 of them have
  no attachment at all because the plans are held by a private plan room
  ("available at Beeline and Blue, Des Moines"). That is a genuine limit of the
  source, not a bug: the metadata is public, some documents are not.
* Among the bids that DO attach documents, the spec book is one file among ten.
  RFB952500-01 (IPBS HVAC Motivair Units Replacement) carries an Addendum, a Bid
  Form, a Notice to Bidders, Drawings and "RFB952500-01 - Project Manual".
  Only the last is CSI-structured.

Labels, not URLs, carry the role here -- the href is an opaque GUID.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Iowa",
    "type": "Vertical",
    "tier": 1,
    "agency": "Department of Administrative Services",
    "listing_url": "https://bidopportunities.iowa.gov/",
    "bids_api": "https://bidopportunities.iowa.gov/Home/DT_HostedBidsSearch"
                "?agencyId=&enteredSearchText=",
    "detail_url": "https://bidopportunities.iowa.gov/Home/BidInfo?bidId={id}",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
HOST = "https://bidopportunities.iowa.gov"

_baseline: dict[str, bytes] = {}

_SPEC_FIRST = ("project manual", "specification", "specs", "spec ", "addendum",
               "bid package", "appendix")
_NEVER = ("bid form", "bid worksheet", "notice to bidders", "schedule of prices",
          "questions", "registration", "invitation", "bid tab", "award")


def _get(url: str, referer: str | None = None, extra: dict | None = None,
         timeout: float = 180) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,application/json,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _soft404(host_root: str) -> bytes:
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/Home/GetBidOpportunityDocument/"
                       "00000000-0000-0000-0000-000000000000")
        _baseline[host_root] = body
    return _baseline[host_root]


def _rank(label: str) -> int:
    low = label.lower()
    if any(n in low for n in _NEVER):
        return 90
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    st, body = _get(PORTAL["bids_api"], referer=PORTAL["listing_url"],
                    extra={"X-Requested-With": "XMLHttpRequest"})
    time.sleep(PAUSE)
    if st != 200 or not body.lstrip()[:1] == b"{":
        return []
    try:
        rows = json.loads(body).get("aaData", [])
    except Exception:  # noqa: BLE001
        return []

    out: list[dict] = []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        bid_id = r.get("ID")
        if not bid_id:
            continue
        url = PORTAL["detail_url"].format(id=bid_id)
        st, d = _get(url, referer=PORTAL["listing_url"])
        time.sleep(PAUSE)
        if st != 200 or not d:
            continue
        docs, seen = [], set()
        for m in re.finditer(
                r'href="(/Home/GetBidOpportunityDocument/[^"]+)"[^>]*>(.*?)</a>',
                d.decode("utf-8", "ignore"), re.I | re.S):
            u = urllib.parse.urljoin(HOST, m.group(1))
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            if not label or u in seen:
                continue
            seen.add(u)
            docs.append((_rank(label), u, label))
        if not docs:
            continue
        docs.sort()
        out.append({
            "project_name": r.get("Solicitation") or "",
            "project_number": r.get("BidNumber"),
            "bid_date": r.get("ExpirationDate"),
            "doc_urls": [d_[1] for d_ in docs],
            "_best_rank": docs[0][0],
        })
        el = time.time() - t0
        print(f"[{i}/{len(rows)}] {len(out)} with docs  {i / el * 60:.0f}/min "
              f"ETA {(len(rows) - i) * el / i:.0f}s", file=sys.stderr)
        if sum(1 for e in out if e["_best_rank"] < 3) >= limit:
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
