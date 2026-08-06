"""Caltrans Office of Engineering -- advertised highway contracts.

Classification (a-with-JSON): no login, no browser needed.

The human-facing listing at ppmoe.dot.ca.gov is a ServiceNow Service Portal
(Angular). A plain fetch of `all-adv-projects.php` returns 165 KB of template
markup and ZERO advertisement links -- the shape that makes a portal look dead.
Playwright rendered it and showed the real page is `/cc?id=cc_advertisement`,
which in turn fills itself from an ANONYMOUS JSON endpoint:

    /api/now/sp/page?id=cc_advertisement&timespan=all&portal_id=<portal>

so no browser is needed at run time -- we call the same endpoint the browser
calls.

Attachments are the trap. The obvious ServiceNow paths BOTH fail while looking
like a login wall:

    /sys_attachment.do?sys_id=...            -> 302 to idpcluster.ctpass.dot.ca.gov
    /api/now/attachment/<sys_id>/file        -> 401 "User is not authenticated"

Recording Caltrans as Tier-2/login-required on that evidence would have been
wrong. The portal's own widget template downloads through a scoped public
processor that needs no session at all:

    /api/x_cado2_contractor/public_attachment_downloader_api/<attachment_sys_id>

Verified 2026-08-06: contract 02-2K2304 special provisions, 468,806 bytes,
`%PDF-1.6`, 37 pages, anonymous.

CALIBRATION NOTE -- read before "fixing" this adapter.
Caltrans bid books are NOT CSI MasterFormat. They are written against the
Caltrans Standard Specifications, whose numbering is `7-1.02K(3)`, `12-4.02`,
`14-11.14` -- a different, older scheme. The content is genuine specification
text; it simply does not carry `23 05 00` / `PART 1 - GENERAL` / `DIVISION 23`.
check-portal-adapters.py will therefore report FAIL for CSI evidence on most
Caltrans contracts. That is a real property of the source, not a defect here,
and it must not be papered over by weakening the checker.
"""
from __future__ import annotations
import json, re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "California",
    "type": "DOT",
    "tier": 1,  # demoted from T2: no account is needed for any of it
    "agency": "Caltrans Division of Engineering Services, Office of Engineering",
    "listing_url": "https://ppmoe.dot.ca.gov/cc?id=cc_advertisement&timespan=all",
    "needs_browser": False,   # the JSON endpoint the browser calls is public
    "needs_headers": False,
}

_PORTAL_ID = "2086b814c3221200f3897bfaa2d3aea8"
_API = "https://ppmoe.dot.ca.gov/api/now/sp/page"
_DL = "https://ppmoe.dot.ca.gov/api/x_cado2_contractor/public_attachment_downloader_api/"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0


def _get(url: str, referer: str | None = None, timeout: float = 120) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/json,application/pdf,*/*"}
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


# tag order: the special provisions are the specification document. "plans" are
# drawings, "forms_for_bid" is a bid form with no technical content, and the
# information handout is geotech/asbestos reports.
_TAG_RANK = ("specs", "special", "sp", "addend", "ih")
# Never returned: "plans" (drawings, tens of MB) and "forms_for_bid" (a bid
# form). Both are definitionally not specification text, and leaving them in
# meant a single project's four attachments consumed every slot a consumer
# sampled -- so five other contracts were never looked at at all.
_TAG_DROP = ("plans", "forms")


def _rank_tag(tag: str, fname: str) -> int:
    low = f"{tag} {fname}".lower()
    for i, kw in enumerate(_TAG_RANK):
        if kw in low:
            return i
    return len(_TAG_RANK)


def _drop(tag: str, fname: str) -> bool:
    low = f"{tag} {fname}".lower()
    return any(k in low for k in _TAG_DROP)


def _ad_ids(limit: int) -> list[str]:
    url = f"{_API}?id=cc_advertisement&timespan=all&portal_id={_PORTAL_ID}"
    status, body = _get(url)
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    text = body.decode("utf-8", "ignore")
    seen: list[str] = []
    for m in re.finditer(r"\b(\d{2}-[0-9A-Z]{6})\b", text):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen[:limit]


def _attachments(ad_id: str) -> list[tuple[int, str, str]]:
    """[(rank, filename, download_url)] for one advertisement."""
    url = (f"{_API}?id=cc_advertisement_details&ad_id={urllib.parse.quote(ad_id)}"
           f"&focus=bidFiles&portal_id={_PORTAL_ID}")
    status, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    text = body.decode("utf-8", "ignore")
    out: list[tuple[int, str, str]] = []
    # Records look like:
    #   {"sys_id":"afa3...","display_field":{...,"value":"02-2K2304sp.pdf"},
    #    "tagString":"specs", ...}
    for m in re.finditer(
        r'\{"sys_id":"([0-9a-f]{32})","display_field":\{.*?"value":"([^"]+?\.(?:pdf|zip))"\}'
        r'.*?"tagString":"([^"]*)"', text, re.S):
        sys_id, fname, tag = m.group(1), m.group(2), m.group(3)
        if _drop(tag, fname):
            continue
        out.append((_rank_tag(tag, fname), fname, _DL + sys_id))
    out.sort(key=lambda t: t[0])
    return out


def discover(limit: int = 50) -> list[dict]:
    ids = _ad_ids(limit)
    total = len(ids)
    out: list[dict] = []
    t0 = time.time()
    for i, ad in enumerate(ids, 1):
        atts = _attachments(ad)
        if atts:
            out.append({
                "project_name": f"Caltrans contract {ad}",
                "project_number": ad,
                "bid_date": None,
                "doc_urls": [u for _, _, u in atts],
            })
        el = time.time() - t0
        rate = i / el * 60 if el else 0
        print(f"[{i}/{total}] {ad} {len(atts)} docs  {rate:.0f}/min "
              f"ETA {(total - i) / rate * 60 if rate else 0:.0f}s", flush=True)
    return out


def fetch(url: str) -> bytes | None:
    status, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return None
    return body


if __name__ == "__main__":  # rule 5: read back what was written
    found = discover(limit=3)
    print(f"discovered {len(found)} projects")
    for f in found:
        b = fetch(f["doc_urls"][0])
        print(f"  {f['project_number']}: {len(b) if b else 0} bytes from {f['doc_urls'][0]}")
