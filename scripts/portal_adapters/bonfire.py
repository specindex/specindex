"""Bonfire (Euna Solutions) -- PLATFORM adapter, not a state adapter.

One adapter, every Bonfire tenant. Two are wired here because the source
workbook listed them as separate Tier-2 states:

  utah.bonfirehub.com   Utah DFCM (via https://dfcm.utah.gov/construction-management/)
  deswa.bonfirehub.com  Washington State DES (via https://des.wa.gov/do-business-state/public-works-bidding)

Adding a third agency is one line in TENANTS -- that is the whole leverage
argument for going per-platform. Both state pages were classified Tier-2
("free account believed necessary"); neither is. No account, no credentials,
no terms accepted.

HOW IT WORKS, AND THE TWO TRAPS

1. The opportunity LIST is a public JSON endpoint, no Cloudflare, no session:
       /PublicPortal/getOpenPublicOpportunitiesSectionData
   -> payload.projects, keyed by ProjectID. Utah returned 187 open
   opportunities, Washington DES 12, on 2026-08-06.

2. The opportunity DETAIL page (/opportunities/<id>) sits behind a Cloudflare
   Turnstile managed challenge. Plain urllib gets HTTP 403 + "Just a moment...",
   and so does HEADLESS Chromium -- both chromium and channel=chrome headless
   stay stuck on the interstitial. A HEADED Chrome passes it. That is why
   needs_browser is True and why the browser is launched headless=False: this
   is an edge challenge, and the usual "Playwright fixes JS listings" reflex
   does not apply to the headless case.

3. The DOCUMENTS themselves are NOT protected at all. The links are literally
   named `downloadDocumentUnauthenticated`, and plain urllib with a browser UA
   plus a Referer returns the bytes. So exactly one step needs the browser:
   enumerating document ids. Downloads never do.

Verified 2026-08-06, no login: Utah project 244107 (DFCM Ogden Regional Center
Sewer Ejection Pump Replacement, #27079310) document 10541650
"3-CS27002-27079310-Approved Specs.pdf", 2,071,123 bytes, %PDF-1.5, containing
"DIVISION 22 - PLUMBING / 221329 SEWAGE PUMPS / DIVISION 26 - ELECTRICAL".
"""
from __future__ import annotations
import json, re, time, urllib.error, urllib.parse, urllib.request

TENANTS = [
    ("utah", "Utah Division of Facilities Construction & Management"),
    ("deswa", "Washington State Department of Enterprise Services"),
    # PennBid: Euna hosts it for ~1,900 Pennsylvania public agencies, so this
    # single line reaches boroughs, townships and authorities that have no
    # portal of their own -- the leverage argument for a platform adapter,
    # at its largest so far. Verified live 2026-08-08 with no account:
    # getOpenPublicOpportunitiesSectionData returned 205 open opportunities
    # (Carnegie Borough sewer rehabilitation, Marysville Lions Club park
    # improvements, Pennsburg liquid fuels road program, Mount Joy Township).
    #
    # Worth recording because it was nearly missed: probing the PORTAL page
    # first suggests this tenant is unusable -- /opportunities/<id> serves a
    # Cloudflare "Performing security verification" interstitial. That is the
    # detail page only, exactly as documented above; the JSON list endpoint
    # has no challenge and the documents are downloadUnauthenticated. Judging
    # the tenant by the detail page alone would have discarded 205 live
    # solicitations in the one state whose portals are otherwise fragmented.
    ("pennbid", "PennBid (Pennsylvania public agencies, ~1,900 via Euna)"),
]

PORTAL = {
    "state": "Utah, Washington, Pennsylvania",  # platform adapter: many states
    "type": "Vertical",
    "tier": 1,                            # demoted from T2: no account needed
    "agency": "Bonfire (Euna Solutions) hosted procurement portals",
    "platform": "bonfire",
    "tenants": [t for t, _ in TENANTS],
    "listing_url": "https://utah.bonfirehub.com/portal/?tab=openOpportunities",
    "needs_browser": True,   # ONLY to clear Cloudflare on the detail page
    "needs_headers": True,   # browser UA + Referer on every download
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

# Bonfire agencies attach a whole packet: general conditions, bid forms,
# subcontractor lists, wage decisions -- and one project manual. Grabbing the
# first attachment returns "A-DFCM General Conditions" and the portal looks
# like it holds no specifications.
_SPEC_FIRST = ("approved specs", "project manual", "specification", "specs",
               "technical", "addendum", "plans", "drawings")


def _rank(fname: str) -> int:
    low = fname.lower()
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _get(url: str, referer: str | None = None, timeout: float = 180,
         accept: str = "application/json,application/pdf,*/*") -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": accept,
         "Accept-Language": "en-US,en;q=0.9",
         "X-Requested-With": "XMLHttpRequest"}
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _open_projects(tenant: str) -> list[dict]:
    """Public JSON list. No Cloudflare on this path."""
    url = (f"https://{tenant}.bonfirehub.com/PublicPortal/"
           f"getOpenPublicOpportunitiesSectionData")
    status, body = _get(url, referer=f"https://{tenant}.bonfirehub.com/portal/?tab=openOpportunities")
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    try:
        payload = json.loads(body)["payload"]
    except Exception:  # noqa: BLE001
        return []
    projects = payload.get("projects") or {}
    if isinstance(projects, dict):
        projects = list(projects.values())
    # Public opportunities only. Private ones (ProjectVisibilityID 2) are the
    # ones a login would gate; we do not touch them.
    return [p for p in projects if str(p.get("ProjectVisibilityID")) == "1"]


_DOC_ROW = re.compile(
    r'<td id="document-(\d+)"[^>]*>\s*<strong>(.*?)</strong>', re.S)


def _documents(pages, tenant: str, project_id: str) -> list[tuple[int, str, str]]:
    """(rank, filename, download_url). Needs the headed browser for Cloudflare."""
    url = f"https://{tenant}.bonfirehub.com/opportunities/{project_id}"
    pg = pages
    pg.goto(url, wait_until="domcontentloaded", timeout=90000)
    # Poll for the document table rather than sleeping a flat 15s -- after the
    # first page the clearance cookie is set and it renders in about a second.
    html = ""
    for _ in range(30):
        html = pg.content()
        if "downloadDocumentUnauthenticated" in html:
            break
        if "Just a moment" not in html and "document-" in html:
            break
        pg.wait_for_timeout(1000)
    out: list[tuple[int, str, str]] = []
    for doc_id, fname in _DOC_ROW.findall(html):
        fname = re.sub(r"<[^>]+>", "", fname).strip()
        if not fname.lower().endswith(".pdf"):
            continue  # .docx bid forms are not specification content
        dl = (f"https://{tenant}.bonfirehub.com/opportunitiessingle/"
              f"{project_id}/downloadDocumentUnauthenticated/{doc_id}")
        out.append((_rank(fname), fname, dl))
    out.sort(key=lambda t: t[0])
    return out


def discover(limit: int = 50) -> list[dict]:
    from playwright.sync_api import sync_playwright

    targets: list[tuple[str, str, dict]] = []
    for tenant, agency in TENANTS:
        for p in _open_projects(tenant):
            targets.append((tenant, agency, p))
    # Construction packets first: a bid for office chairs has no project manual.
    _CONSTRUCTION = re.compile(
        r"construct|renovat|replace|remodel|hvac|roof|mechanical|electrical|"
        r"plumb|building|facilit|bldg|boiler|chiller|paving|bridge", re.I)
    targets.sort(key=lambda t: 0 if _CONSTRUCTION.search(t[2].get("ProjectName", "")) else 1)
    targets = targets[:limit]
    total = len(targets)
    if not total:
        return []

    out: list[dict] = []
    t0 = time.time()
    with sync_playwright() as pw:
        # headless=False on purpose: the Cloudflare managed challenge is never
        # solved by headless Chromium or headless channel=chrome. Verified.
        browser = pw.chromium.launch(
            headless=False, channel="chrome",
            args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        try:
            for i, (tenant, agency, p) in enumerate(targets, 1):
                pid = str(p.get("ProjectID"))
                try:
                    docs = _documents(page, tenant, pid)
                except Exception:  # noqa: BLE001
                    docs = []
                if docs:
                    out.append({
                        "project_name": p.get("ProjectName"),
                        "project_number": p.get("ReferenceID") or pid,
                        "bid_date": (p.get("DateClose") or "")[:10] or None,
                        "agency": agency,
                        "tenant": tenant,
                        "doc_urls": [u for _, _, u in docs],
                    })
                el = time.time() - t0
                rate = i / el * 60 if el else 0
                print(f"[{i}/{total}] {tenant}/{pid} {len(docs)} pdf(s)  "
                      f"{rate:.0f}/min ETA {((total - i) / rate * 60) if rate else 0:.0f}s",
                      flush=True)
                time.sleep(PAUSE)
        finally:
            browser.close()
    return out


def fetch(url: str) -> bytes | None:
    """Downloads are NOT Cloudflare-protected -- plain urllib is enough."""
    m = re.match(r"https://([a-z0-9\-]+)\.bonfirehub\.com/opportunitiessingle/(\d+)/", url)
    referer = (f"https://{m.group(1)}.bonfirehub.com/opportunities/{m.group(2)}"
               if m else PORTAL["listing_url"])
    status, body = _get(url, referer=referer, accept="application/pdf,*/*")
    time.sleep(PAUSE)
    if status != 200 or len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return None
    return body


if __name__ == "__main__":  # rule 5: read back what was written
    found = discover(limit=6)
    print(f"discovered {len(found)} projects with documents")
    for f in found[:3]:
        b = fetch(f["doc_urls"][0])
        print(f"  {f['tenant']} {f['project_number']}: {len(b) if b else 0} bytes")
