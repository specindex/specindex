"""NCDOT -- North Carolina DOT Connect letting (Tier 1, DOT).

Proven end to end 2026-08-06: PASS, 9,737,343 bytes, DOT spec sections +
measurement/payment. Documents are reachable anonymously:

    https://connect.ncdot.gov/letting/Central Letting/09-16-2025 Central Letting/
        GUILFORD_U-4758_C204971.pdf      24,304,375 bytes, 402 pages

Each is the bid proposal, contract and contract bonds with the project special
provisions.

CALIBRATION NOTE. NCDOT proposals open with the contract cover, the bond forms
and the itemised bid schedule; the first arabic DIVISION heading in the Guilford
document above does not appear until page 56, and the checker reads 25. Five
NCDOT proposals sampled showed no MasterFormat evidence in their first 25 pages.
What they do carry early is NCDOT's own section numbering with the
measurement/payment skeleton, which is what this adapter now passes on.

TRAPS THIS ADAPTER WALKED INTO:
1. The spreadsheet URL (connect.ncdot.gov/letting/Pages/default.aspx) is a
   landing page. Its Division letting page renders its table in JavaScript, so
   a plain fetch sees 82,354 bytes and zero document links -- a silent zero.
2. connect.ncdot.gov is SharePoint, and its anonymous REST endpoint DOES answer:
       /letting/_api/web/GetFolderByServerRelativeUrl('<path>')/Files
   That is how this adapter enumerates a letting folder. Requires
   Accept: application/json;odata=nometadata -- with the default Accept the
   same URL returns XML that a naive JSON parse treats as "no documents".
"""
from __future__ import annotations
import json, re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "North Carolina",
    "type": "DOT",
    "tier": 1,
    "agency": "North Carolina Department of Transportation, Contract Standards & Development",
    "listing_url": "https://connect.ncdot.gov/letting/Pages/default.aspx",
    "library_root": "/letting/Central Letting",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
_API = "https://connect.ncdot.gov/letting/_api/web/GetFolderByServerRelativeUrl('%s')/%s"

_baseline: dict[str, bytes] = {}


def _get(url: str, referer: str | None = None, accept: str = "application/pdf,text/html,*/*",
         timeout: float = 300) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": accept}
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


def _sp(path: str, what: str) -> list[dict]:
    url = urllib.parse.quote(_API % (path, what), safe=":/?=&()'")
    status, body = _get(url, accept="application/json;odata=nometadata")
    time.sleep(PAUSE)
    if status != 200 or not body.lstrip()[:1] == b"{":
        return []
    try:
        return json.loads(body).get("value", [])
    except Exception:  # noqa: BLE001
        return []


_DATE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})")

# A letting folder mixes the per-project proposals with letting-wide artefacts.
# "Invite", "Bid Tabs" and "Item C" carry no specification text; addenda amend
# the proposal and are worth keeping but must not outrank it.
_SKIP = ("invite", "bid tab", "item c", "planholder", "understanding digital")


def _rank(name: str) -> int:
    low = name.lower()
    if "addendum" in low:
        return 1
    if any(s in low for s in _SKIP):
        return 3
    return 0


def discover(limit: int = 50) -> list[dict]:
    folders = _sp(PORTAL["library_root"], "Folders")
    dated = []
    for f in folders:
        m = _DATE.match(f.get("Name", ""))
        if m:
            dated.append(((int(m.group(3)), int(m.group(1)), int(m.group(2))), f["Name"]))
    dated.sort(reverse=True)

    out: list[dict] = []
    for _, folder in dated:
        if len(out) >= limit:
            break
        files = _sp(f"{PORTAL['library_root']}/{folder}", "Files")
        for f in files:
            name = f.get("Name", "")
            if not name.lower().endswith(".pdf") or _rank(name) >= 3:
                continue
            url = ("https://connect.ncdot.gov" +
                   urllib.parse.quote(f"{PORTAL['library_root']}/{folder}/{name}", safe=":/"))
            num = re.search(r"\b(C\d{6})\b", name)
            out.append({
                "project_name": name[:-4],
                "project_number": num.group(1) if num else None,
                "bid_date": folder.split(" ")[0],
                "doc_urls": [url],
            })
            if len(out) >= limit:
                break
    # proposals before addenda across the whole result
    out.sort(key=lambda e: _rank(e["project_name"]))
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
        print(" ", f["bid_date"], f["project_number"], f["project_name"][:50])
