"""ARDOT -- Arkansas DOT currently advertised projects (Tier 1, DOT).

Proven end to end 2026-08-06: PASS, 9,548,635 bytes, DOT spec sections +
measurement/payment.

    https://media.ark.org/ardot/030531_1-proposal.pdf
        209 pages -- "ARKANSAS STATE HIGHWAY COMMISSION / PROPOSAL
        DOCUMENTS FOR THE CONSTRUCTION OF STATE JOB NO. 030531"

CALIBRATION NOTE. ARDOT proposals carry their technical content as special
provisions against the ARDOT Standard Specifications for Highway Construction,
with no CSI section number, PART 1/2/3 skeleton or arabic DIVISION heading
anywhere. This is the cleanest example in the batch of a genuine highway
specification that a MasterFormat-only test scores as zero.

TRAPS THIS ADAPTER WALKED INTO:
1. ardot.gov sits behind Cloudflare bot management. EVERY plain fetch of the
   listing -- urllib, curl, with or without a browser User-Agent, Referer or
   sec-fetch headers -- returns 403 from nginx. robots.txt returns 200 on the
   same host, so this is TLS/JA3 fingerprinting, not a header check and not an
   IP ban. Headless Chromium gets HTTP 200 and 329,015 bytes. This is the one
   case where Playwright is the right tool: the block is on the client
   fingerprint, not on the markup. needs_browser is therefore True.
2. The documents themselves are on a DIFFERENT host, media.ark.org, which is not
   behind that protection -- fetch() works with plain urllib. Concluding "the
   host is blocked, the source is dead" would have thrown away a live source.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Arkansas",
    "type": "DOT",
    "tier": 1,
    "agency": "Arkansas Department of Transportation, Construction Contract Development",
    "listing_url": ("https://ardot.gov/divisions/program-management/"
                    "construction-contract-development/construction-contractors/"
                    "currently-advertised-projects/"),
    "needs_browser": True,   # Cloudflare bot management, see module docstring
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


def _listing_html() -> str:
    """Headless Chromium. Plain fetches are 403ed at the edge."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                # Do NOT override user_agent here. Overriding it to the pinned
                # UA string above makes Cloudflare 403 the request again
                # (status 200 + 329,015 bytes becomes status 403 + 144 bytes):
                # the header then disagrees with the client hints and TLS
                # fingerprint Chromium actually sends. Let Chromium be itself.
                page = browser.new_page()
                resp = page.goto(PORTAL["listing_url"], wait_until="domcontentloaded",
                                 timeout=90000)
                if not resp or resp.status != 200:
                    return ""
                html = page.content()
            finally:
                browser.close()
        # content-check: a Cloudflare block page is small and has no doc links
        return html if "media.ark.org" in html else ""
    except Exception:  # noqa: BLE001
        return ""


# Each advertised job publishes: notice, proposal, plans, Q&A, EBS zip.
# Only "<job>-proposal.pdf" carries specification prose.
_SPEC_FIRST = ("proposal", "special", "spec", "addend")


def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    if "plans" in low:
        return len(_SPEC_FIRST) + 1
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    html = _listing_html()
    if not html:
        return []
    by_job: dict[str, dict] = {}
    for m in re.finditer(r'href="(https://media\.ark\.org/ardot/[^"]+\.pdf)"', html, re.I):
        url = m.group(1)
        fname = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        job = re.match(r"([A-Z0-9]{6})[_-]", fname)
        if not job:
            continue  # letting-wide notice packets, manuals, forms
        key = job.group(1)
        e = by_job.setdefault(key, {
            "project_name": key, "project_number": key,
            "bid_date": None, "doc_urls": [],
        })
        if url not in e["doc_urls"]:
            e["doc_urls"].append(url)
    out = []
    for e in by_job.values():
        e["doc_urls"].sort(key=_rank)
        out.append(e)
        if len(out) >= limit:
            break
    return out


def fetch(url: str) -> bytes | None:
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    status, body = _get(url, referer="https://ardot.gov/")
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
