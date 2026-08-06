"""VTrans -- Vermont Agency of Transportation construction bid opportunities.

Proven end to end 2026-08-06: contract C03284 (JAMAICA ER P23-1(216)) returned a
15,234,475-byte PROPOSAL whose first page reads "STANDARD SPECIFICATIONS FOR
CONSTRUCTION DATED 2024 SHALL APPLY TO THIS CONTRACT / SPECIAL PROVISIONS", and
the checker finds division headings in it. No login.

TRAP THIS ADAPTER WALKED INTO:
The spreadsheet URL (vtrans.vermont.gov/contract-admin/bids-requests) is a
landing page. Its Design-Bid-Build sub-page says in bold "DBB Plans must be
downloaded by logging in to the iCX Web System" -- which reads as a hard login
wall and would justify recording Vermont as Tier 3. It is not. Further down the
same page an <iframe> embeds

    https://vtrans.exevision.com/icxpublic/BidOpportunityContainer.aspx

which itself embeds BidOpportunities.aspx. That inner page serves the contract
PROPOSAL (the specification document) anonymously through DocumentHandler.ashx.
Only the *plan sheets* need the iCX login. Reading the sentence and stopping
would have lost a passing source.
"""
from __future__ import annotations
import html as _html
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Vermont",
    "type": "DOT",
    "tier": 1,
    "agency": "Vermont Agency of Transportation, Contract Administration",
    "listing_url": "https://vtrans.exevision.com/icxpublic/BidOpportunities.aspx",
    "landing_url": "https://vtrans.vermont.gov/contract-admin/bids-requests",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

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


# Each contract offers: the contract-name PDF (a one-page advertisement), the
# PROPOSAL (special provisions + standard specifications reference -- the spec
# document), and reference reports (geotech, record plans, TMP checklist).
# Only the PROPOSAL carries specification text; ranking by document order in the
# page would return the advertisement and the portal would look empty.
_SPEC_FIRST = ("proposal", "special provision", "specification", "addend")


def _rank(pair: tuple[str, str]) -> int:
    label = (pair[1] + " " + urllib.parse.unquote(pair[0])).lower()
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in label:
            return i
    return len(_SPEC_FIRST)


def discover(limit: int = 50) -> list[dict]:
    status, body = _get(PORTAL["listing_url"], referer=PORTAL["landing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    page = body.decode("utf-8", "ignore")

    # rows are keyed by a repeater index: rptContracts_btnContractName_<n>
    starts = [(int(m.group(1)), m.start())
              for m in re.finditer(r'rptContracts_btnContractName_(\d+)', page)]
    out: list[dict] = []
    for pos, (idx, start) in enumerate(starts):
        end = starts[pos + 1][1] if pos + 1 < len(starts) else len(page)
        seg = page[start:end]
        head = page[max(0, start - 400):start]
        num = None
        nums = re.findall(r'>\s*(C\d{4,6})\s*<', head)
        if nums:
            num = nums[-1]
        docs: list[tuple[str, str]] = []
        for m in re.finditer(r'href="(DocumentHandler\.ashx\?[^"]+)"[^>]*>(.*?)</a>', seg, re.I | re.S):
            href = _html.unescape(m.group(1))
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            url = urllib.parse.urljoin(PORTAL["listing_url"], href)
            if url not in [d[0] for d in docs]:
                docs.append((url, label))
        if not docs:
            continue
        name_m = re.search(r'>([^<]+)</a>', seg)
        docs.sort(key=_rank)
        out.append({
            "project_name": (name_m.group(1).strip() if name_m else num or f"contract-{idx}"),
            "project_number": num,
            "bid_date": None,
            "doc_urls": [d[0] for d in docs],
        })
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
        print(" ", f["project_number"], f["project_name"], len(f["doc_urls"]))
