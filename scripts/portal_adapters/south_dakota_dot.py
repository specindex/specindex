"""SDDOT -- South Dakota DOT bid letting (Tier 1, DOT).

Proven end to end 2026-08-06: PASS, 17,621,612 bytes, DOT spec sections +
measurement/payment. Documents are reachable anonymously and without a login:

    https://apps.sd.gov/HC65C2C/EBS/lettings/specprov/09ML_SpecProv.pdf
        12,764,699 bytes, 100 pages -- "NOTICE TO CONTRACTORS, PROPOSAL,
        SPECIAL PROVISIONS, CONTRACT AND CONTRACT BOND" for PCN 09ML

CALIBRATION NOTE. Not one of these documents contains a CSI MasterFormat section
number, a PART 1/2/3 skeleton or an arabic DIVISION heading -- not in the first
25 pages, not in all 100. SDDOT writes against its own Standard Specifications
for Roads and Bridges "Section 100/200/..." numbering. Under the MasterFormat-
only test this portal read as specification-free; it is not.

TRAP THIS ADAPTER WALKED INTO:
The spreadsheet URL (dot.sd.gov/doing-business/contractors/bid-letting-information)
is a landing page carrying zero PDFs and 284 navigation links. The letting
application is a separate host reached by one link reading "Bid Letting ->":
apps.sd.gov/HC65BidLetting/. From there ebslettings1.aspx lists the advertised
letting dates and ebslettingsdetail1.aspx?args=... lists each project's
Special Provisions and electronic plans.
"""
from __future__ import annotations
import html as _html
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "South Dakota",
    "type": "DOT",
    "tier": 1,
    "agency": "South Dakota Department of Transportation, Office of Bid Letting",
    "listing_url": "https://apps.sd.gov/HC65BidLetting/ebslettings1.aspx",
    "landing_url": "https://dot.sd.gov/doing-business/contractors/bid-letting-information/",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, timeout: float = 300) -> tuple[int, bytes]:
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


# Per project SDDOT publishes:
#   specprov/<PCN>_SpecProv.pdf        <- notice, proposal, SPECIAL PROVISIONS
#   electronicplans/<PCN>_*.pdf        <- drawing sheets, no prose
# Taking whichever appears first returns the plan set for many projects.
_SPEC_FIRST = ("specprov", "special", "spec")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    if "electronicplans" in low:
        return len(_SPEC_FIRST) + 1
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _letting_urls() -> list[str]:
    status, body = _get(PORTAL["listing_url"], referer=PORTAL["landing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    page = body.decode("utf-8", "ignore")
    seen, out = set(), []
    for m in re.finditer(r'href="(ebslettingsdetail1\.aspx\?args=[^"]+)"', page, re.I):
        u = urllib.parse.urljoin(PORTAL["listing_url"], _html.unescape(m.group(1)))
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def discover(limit: int = 50) -> list[dict]:
    out: list[dict] = []
    for letting in _letting_urls():
        if len(out) >= limit:
            break
        status, body = _get(letting, referer=PORTAL["listing_url"])
        time.sleep(PAUSE)
        if status != 200 or not body:
            continue
        page = body.decode("utf-8", "ignore")
        by_pcn: dict[str, dict] = {}
        for m in re.finditer(
                r'href="(https?://apps\.sd\.gov/HC65C2C/EBS/lettings/[^"]+\.pdf)"', page, re.I):
            url = _html.unescape(m.group(1))
            fname = urllib.parse.unquote(url.rsplit("/", 1)[-1])
            pcn = re.match(r"([0-9A-Z]{4})_", fname)
            key = pcn.group(1) if pcn else fname
            e = by_pcn.setdefault(key, {
                "project_name": key, "project_number": pcn.group(1) if pcn else None,
                "bid_date": None, "doc_urls": [],
            })
            if url not in e["doc_urls"]:
                e["doc_urls"].append(url)
        for e in by_pcn.values():
            # skip letting-wide notices (no PCN prefix)
            if e["project_number"] is None:
                continue
            e["doc_urls"].sort(key=_rank)
            out.append(e)
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
    found = discover(limit=6)
    print(f"discover() -> {len(found)} projects, "
          f"{sum(len(f['doc_urls']) for f in found)} document URLs")
    for f in found:
        print(" ", f["project_number"], f["doc_urls"][0].rsplit("/", 1)[-1])
