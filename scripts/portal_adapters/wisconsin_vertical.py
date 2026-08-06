"""Wisconsin DFD (Division of Facilities Development) -- WisBuild public bid archive.

Tier assessment 2026-08-06: the spreadsheet listed Wisconsin as T2 ("free account
or vendor registration believed necessary"). That is HALF right, and the half
matters:

  * CURRENT bids (May 2024 onward) are genuinely walled. doa.wi.gov/Pages/
    DoingBusiness/DFDProjects.aspx says every project's documents live in the
    "Trimble Unity Construct Bid Portal" and "All bidders must sign in ... using
    a Trimble ID". That is a real login wall; no account was created.
  * The PRIOR system, WisBuild, is still online and still serving its bid
    documents to anyone. No login, no cookie, no referer trick. That archive is
    what this adapter reads.

The path there is two hops the spreadsheet URL does not show:
  DFDProjects.aspx  ->  wisbuildnet .../public/bidlist_public_past.aspx
                    ->  .../public/bid_documents.aspx?projnum=<n>
                    ->  .../filedownload.aspx?path=bid_docs/...
The listing is ASP.NET WebForms and defaults to "the last 3 months", which for a
system retired in May 2024 renders an EMPTY table -- the exact shape that reads
as "portal is dead" if you stop at the first page. It is not dead; it needs a
date range posted back with the page's own hidden fields.

Proven end to end: project 23C2A (8th & 9th Floor Remodel, Administration
Building, Madison) -> 23C2A TOC.pdf, 803,417 bytes, carrying CSI section numbers
and DIVISION headings.
"""
from __future__ import annotations
import html as H
import re
import time
import urllib.error
import urllib.parse
import urllib.request

PORTAL = {
    "state": "Wisconsin",
    "type": "Vertical",
    "tier": 1,                     # for the WisBuild archive; current bids are T3
    "agency": "Department of Administration, Division of Facilities Development",
    "listing_url": "https://wisbuildnet.wisconsin.gov/public/bidlist_public_past.aspx",
    "landing_url": "https://doa.wi.gov/Pages/DoingBusiness/DFDProjects.aspx",
    "needs_browser": False,
    "needs_headers": False,
    "notes": "Current (post-2024-05) bids require a Trimble ID login. This adapter "
             "reads the still-public WisBuild archive only.",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

# How far back to sweep when discover() is called with no explicit range. WisBuild
# was retired in May 2024, so the useful window ends there.
DEFAULT_BEGIN = "1/1/2023"
DEFAULT_END = "5/14/2024"

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, data: bytes | None = None,
         timeout: float = 120) -> tuple[int, bytes, str]:
    h = {"User-Agent": UA,
         "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    if data is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        req = urllib.request.Request(url, headers=h, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, b"", url
    except Exception:  # noqa: BLE001
        return 0, b"", url


def _soft404(host_root: str) -> bytes:
    """What this host serves for a path that cannot exist. Government hosts answer
    200 with their landing page, so every fetch is compared against this."""
    if host_root not in _baseline:
        _, body, _ = _get(f"{host_root}/zzz-specindex-not-real-9174.pdf")
        _baseline[host_root] = body
    return _baseline[host_root]


def _hidden_fields(html: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', html, re.I):
        tag = m.group(0)
        n = re.search(r'name="([^"]+)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            out[n.group(1)] = H.unescape(v.group(1)) if v else ""
    return out


_SESSION = re.compile(r"/\(S\([a-z0-9]+\)\)")


def _encode(url: str) -> str:
    """WisBuild file URLs carry raw spaces and '+' inside the query. urllib will
    not send them as-is; quoting path and query separately turns a silent 0-byte
    failure into an 800KB PDF.

    Two traps this also disarms:
      * the URL is cookieless-ASP.NET and embeds a session segment `/(S(xxx))/`.
        That session dies within minutes, so a URL captured by discover() and
        fetched later 302s to an empty page. The server re-issues a session for
        the bare path, so the segment is stripped.
      * quoting must be idempotent -- encoding an already-encoded URL turns %20
        into %2520 and the file 404s. Unquote first.
    """
    sp = urllib.parse.urlsplit(url)
    path = _SESSION.sub("", urllib.parse.unquote(sp.path))
    query = urllib.parse.unquote(sp.query)
    return urllib.parse.urlunsplit((
        sp.scheme, sp.netloc, urllib.parse.quote(path),
        urllib.parse.quote(query, safe="=&+"), ""))


# WisBuild names every file by role. Only one of them is the project manual, and
# grabbing whichever appears first hands back a one-page bid tabulation -- the
# portal then looks like it holds no specifications at all.
#   <PROJ> TOC.pdf            <- project manual table of contents: CSI sections
#   <PROJ> A-1 Document.pdf   <- notice of advertisement, no CSI
#   <PROJ> BidTab.pdf         <- bid results
#   <PROJ> Award Results.pdf  <- award
_SPEC_FIRST = ("project manual", "specification", "spec", "toc",
               "table of contents", "mep-id", "mepid")
_NEVER = ("bidtab", "bid tab", "award")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    for kw in _NEVER:
        if kw in low:
            return 99
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _project_numbers(begin: str, end: str, limit: int) -> list[dict]:
    status, body, final = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    form = _hidden_fields(html)
    form.update({
        "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        "ctl00$ContentPlaceHolder1$TextBox1": begin,
        "ctl00$ContentPlaceHolder1$TextBox2": end,
        "ctl00$ContentPlaceHolder1$Button1": "Submit",
    })
    # `final` carries the cookieless session id -- posting to the bare URL 500s.
    status, body, final = _get(final, referer=final,
                               data=urllib.parse.urlencode(form).encode())
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    grid = body.decode("utf-8", "ignore")

    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
            r'href="[^"]*bid_documents\.aspx\?projnum=([^"&]+)"[^>]*>(.*?)</a>',
            grid, re.I | re.S):
        num = H.unescape(urllib.parse.unquote(m.group(1))).strip()
        title = re.sub(r"\s+", " ",
                       H.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
        if num in seen:
            continue
        seen.add(num)
        out.append({"project_name": title or num, "project_number": num})
        if len(out) >= limit:
            break
    return out


def discover(limit: int = 50, begin: str = DEFAULT_BEGIN,
             end: str = DEFAULT_END) -> list[dict]:
    """Two hops: post a date range to get project numbers, then read each
    project's document page. Does not download any PDF."""
    projects = _project_numbers(begin, end, limit)
    if not projects:
        return []

    out: list[dict] = []
    t0 = time.time()
    total = len(projects)
    for i, p in enumerate(projects, 1):
        page = ("https://wisbuildnet.wisconsin.gov/public/bid_documents.aspx"
                f"?projnum={urllib.parse.quote(p['project_number'])}")
        status, body, final = _get(page)
        time.sleep(PAUSE)
        if status != 200 or not body:
            continue
        html = body.decode("utf-8", "ignore")
        urls: list[str] = []
        for m in re.finditer(r'href="([^"]*filedownload\.aspx[^"]*)"', html, re.I):
            u = _encode(urllib.parse.urljoin(final, H.unescape(m.group(1))))
            if u not in urls:
                urls.append(u)
        if not urls:
            continue
        urls.sort(key=_rank)          # project manual first, bid tab last
        bid = re.search(r"Bid Date:\s*</[^>]+>\s*([0-9/]{8,10})", html) or \
            re.search(r"Bid Date:\s*([0-9/]{8,10})", html)
        out.append({
            "project_name": p["project_name"],
            "project_number": p["project_number"],
            "bid_date": bid.group(1) if bid else None,
            "doc_urls": urls,
        })
        if i % 5 == 0 or i == total:
            el = time.time() - t0
            rate = i / el * 60 if el else 0
            eta = (total - i) / (i / el) if el and i else 0
            print(f"[{i}/{total}] wisconsin discover {rate:.1f}/min ETA {eta:.0f}s",
                  flush=True)

    # Rule 5: assert the next step can see this step's output.
    if out and not any(e["doc_urls"] for e in out):
        print("wisconsin: discover() produced projects with no document URLs")
    return out


def fetch(url: str) -> bytes | None:
    """Content-checked. A status code never decides."""
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    status, body, _ = _get(_encode(url), referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body[:4] == b"%PDF" or len(body) < 2048:
        return None
    base = _soft404(root)
    if base and body == base:
        return None
    return body


if __name__ == "__main__":
    found = discover(limit=5)
    print(f"{len(found)} projects")
    for f in found:
        print(" ", f["project_number"], f["project_name"], len(f["doc_urls"]))
