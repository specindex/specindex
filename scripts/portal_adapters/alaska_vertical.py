"""Alaska Online Public Notices -- state facility ITB/RFP attachments.

Two levels: the notice list (Search.aspx) carries View.aspx?id=N detail pages,
and each detail page carries Attachment.aspx?id=N links whose anchor TEXT is the
original filename. That anchor text is the only place the document's role is
visible -- the URL itself is an opaque numeric id -- so ranking has to be done
on link text, not on the href.

Proven 2026-08-06: notice 224655 "Snowden Administration Building Facade"
carries snowden-facade-repair_100pct_arch_specs.pdf alongside an ITB, two
addenda, a bid schedule and drawings. Taking the first attachment returns
"00 3000 Bid Schedule.pdf" -- a bid form, no CSI body.

Note the list mixes construction with land leases, public meetings and grant
notices, so titles are pre-filtered before any detail page is fetched. Without
that filter eight of eight discovered notices are public hearings with no
attachments at all.
"""
from __future__ import annotations
import re, sys, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Alaska",
    "type": "Vertical",
    "tier": 1,
    "agency": "State of Alaska, Online Public Notices (DOA / agency facilities)",
    # Bare Search.aspx renders the search FORM and zero results -- discover()
    # returned nothing against it. Any `search=` value flips it to the result
    # list; the term itself is ignored server-side (identical output for
    # "construction" and "bid"), so this is just "the 100 most recent notices".
    "listing_url": "https://aws.state.ak.us/OnlinePublicNotices/Notices/Search.aspx?search=construction",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
HOST = "https://aws.state.ak.us"

_baseline: dict[str, bytes] = {}

# Notice titles worth spending a detail-page fetch on.
_WORTH = re.compile(
    r"\b(itb|ifb|invitation to bid|bid|construction|renovat|replace|repair|"
    r"upgrade|remodel|hvac|roof|building|facility|facilities|addition|"
    r"improvement)\b", re.I)
# ...but never these, which match the words above and carry nothing.
_SKIP = re.compile(r"\b(land lease|public meeting|public hearing|categorical "
                   r"exclusion|charitable sale|grant|workshop|regulation)\b", re.I)

# Attachment filename roles, most-spec-like first.
_SPEC_FIRST = ("spec", "project manual", "manual", "addendum", "addenda")


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
        _, body = _get(f"{host_root}/OnlinePublicNotices/Notices/Attachment.aspx?id=0")
        _baseline[host_root] = body
    return _baseline[host_root]


def _rank(label: str) -> int:
    low = label.lower()
    # A "bid schedule" is named 00 3000 and looks CSI-ish; it is a form.
    if "bid schedule" in low or "bid form" in low:
        return 90
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _anchors(html: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        out.append((urllib.parse.urljoin(base, m.group(1)), txt))
    return out


def discover(limit: int = 50, scan: int = 60) -> list[dict]:
    status, body = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")

    cands = []
    seen = set()
    for url, txt in _anchors(html, PORTAL["listing_url"]):
        if "View.aspx?id=" not in url or url in seen:
            continue
        title = urllib.parse.unquote(txt).replace("&nbsp;", " ").strip()
        if not _WORTH.search(title) or _SKIP.search(title):
            continue
        seen.add(url)
        cands.append((url, title[:120]))
    cands = cands[:scan]

    out: list[dict] = []
    t0 = time.time()
    for i, (url, title) in enumerate(cands, 1):
        st, b = _get(url, referer=PORTAL["listing_url"])
        time.sleep(PAUSE)
        if st != 200 or not b:
            continue
        docs = []
        for aurl, atxt in _anchors(b.decode("utf-8", "ignore"), url):
            if "Attachment.aspx?id=" in aurl and atxt.lower().endswith(".pdf"):
                docs.append((_rank(atxt), aurl, atxt))
        if not docs:
            continue
        docs.sort()
        num = re.search(r"\b([A-Z]{2,4}-?[A-Z]?-?\d{2}-?\d{3,5})\b", title)
        out.append({
            "project_name": title,
            "project_number": num.group(1) if num else None,
            "bid_date": None,
            "doc_urls": [d[1] for d in docs],
            "_best_rank": docs[0][0],
        })
        el = time.time() - t0
        print(f"[{i}/{len(cands)}] {len(out)} with docs  "
              f"{i / el * 60:.0f}/min ETA {(len(cands) - i) * el / i:.0f}s",
              file=sys.stderr)
        if sum(1 for e in out if e["_best_rank"] < len(_SPEC_FIRST)) >= limit:
            break

    # Notices that actually carry a spec-class file first.
    out.sort(key=lambda e: e["_best_rank"])
    return out[:limit]


def fetch(url: str) -> bytes | None:
    status, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    base = _soft404(HOST)
    if base and body == base:
        return None
    return body
