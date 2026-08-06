"""TxDOT -- Texas DOT Plans Online (Tier 1, DOT).

Proven end to end 2026-08-06: PASS, 4,746,855 bytes, division headings. Every
state-let construction letting publishes a full Proposal PDF anonymously, e.g.

    ftp.txdot.gov/plans/State-Let-Construction/2026/08 August/08 Proposals/
        Bexar 0025-02-234 Proposal.pdf     (8,138,105 bytes, 271 pages)

Note that TxDOT proposals carry their technical requirements as "SPECIAL
PROVISION TO ITEM <nnn>" against the TxDOT Standard Specifications item
numbering (Item 421 Hydraulic Cement Concrete, Item 360 Concrete Pavement) and
incorporate the Standard Specifications by reference -- so the measurement /
payment prose is thinner here than in, say, an ARDOT proposal. Evidence varies
document to document; the checker samples six.

TRAP THIS ADAPTER WALKED INTO:
The spreadsheet URL (txdot.gov/business/plans-online-bid-lettings.html) is a
landing page with zero PDFs. It links to a licence-agreement page whose "I
Agree" button is a plain JavaScript redirect to /business/plansonline/ftpinfo.htm,
which in turn holds an onClick with the FTP root. That root is served
anonymously over HTTPS -- the credentials embedded in one of the page's onClick
handlers are not required and are not used here.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Texas",
    "type": "DOT",
    "tier": 1,
    "agency": "Texas Department of Transportation, Construction Division",
    "listing_url": "https://ftp.txdot.gov/plans/",
    "landing_url": "https://www.txdot.gov/business/plans-online-bid-lettings.html",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

# Categories worth walking, most specification-bearing first. "Proposals" holds
# the bid proposal with the special provisions; "Proposal Addenda" amends it.
_CATEGORIES = ("State-Let-Construction", "State-Let-Maintenance",
               "Local-Let-Maintenance", "Facilities", "Airport")
_DOC_SUBDIRS = ("Proposals", "Proposal Addenda")

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


def _apache_entries(url: str) -> list[str]:
    """Apache autoindex listing -> absolute child URLs (sort links skipped)."""
    status, body = _get(url)
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<a href="([^"?][^"]*)"', html, re.I):
        href = m.group(1)
        if href.startswith("/") or href.startswith(".."):
            continue
        out.append(urllib.parse.urljoin(url, href))
    return out


def _subdir_rank(url: str) -> int:
    """Index into _DOC_SUBDIRS; len(_DOC_SUBDIRS) means 'not a document folder'.

    Longest key first so "Proposal Addenda" cannot be swallowed by "Proposal".
    """
    tail = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1]).lower()
    for i, key in enumerate(_DOC_SUBDIRS):
        if key.lower() in tail:
            return i
    return len(_DOC_SUBDIRS)


_SPEC_FIRST = ("proposal", "special provision", "spec", "addend")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    if re.search(r"/\d\d plans/|plans?\.pdf$", low):
        return len(_SPEC_FIRST) + 1
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    out: list[dict] = []
    for cat in _CATEGORIES:
        if len(out) >= limit:
            break
        years = [u for u in _apache_entries(PORTAL["listing_url"] + cat + "/")
                 if re.search(r"/\d{4}/$", u)]
        for year in sorted(years, reverse=True)[:2]:
            if len(out) >= limit:
                break
            months = sorted(_apache_entries(year), reverse=True)
            for month in months:
                if len(out) >= limit:
                    break
                # ORDER MATTERS. The month folder lists its subdirectories
                # alphabetically, which puts "08 Proposal Addenda" AHEAD of
                # "08 Proposals". Walking them in listing order fills the first
                # six document slots with 2-to-14-page addendum cover letters
                # and the portal reports "no specification structure" while the
                # 83-to-271-page proposals sit one folder later, untouched.
                subs = sorted(
                    (s for s in _apache_entries(month)
                     if _subdir_rank(s) < len(_DOC_SUBDIRS)),
                    key=_subdir_rank)
                for sub in subs:
                    pdfs = [u for u in _apache_entries(sub) if u.lower().endswith(".pdf")]
                    for pdf in pdfs:
                        name = urllib.parse.unquote(pdf.rsplit("/", 1)[-1])[:-4]
                        num = re.search(r"\b(\d{4}-\d{2}-\d{3})\b", name)
                        out.append({
                            "project_name": name,
                            "project_number": num.group(1) if num else None,
                            "bid_date": None,
                            "doc_urls": sorted([pdf], key=_rank),
                        })
                        if len(out) >= limit:
                            break
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
    found = discover(limit=5)
    print(f"discover() -> {len(found)} projects, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
    for f in found:
        print(" ", f["project_name"])
