"""IDOT Web Contractor Transportation Bulletin (WCTB) -- letting documents.

Classification (a): no login anywhere in the chain. The workbook already had
Illinois at Tier 1 and that is correct.

The chain is three hops and the middle one is the non-obvious part:

  /WCTB/LBHome                        -> "Notice of Letting" link (a GUID)
  /WCTB/LbLettingDetail/Index/<guid>  -> carries an eplan base URL for the
                                         letting, e.g. apps.dot.illinois.gov/
                                         eplan/desenv/073126/
  that eplan path                     -> a PLAIN IIS DIRECTORY LISTING, one
                                         folder per contract, each holding
                                         <contract>.pdf ("Notice to Bidders,
                                         Specifications and Proposal") plus
                                         PLANS/ and ADDITIONAL INFORMATION/.

Walking the directory listing instead of the per-contract WCTB pages turns 82
contracts into 83 requests instead of 165, and the listing is the same data.

Verified 2026-08-06, no login: 073126 letting, contract 62T84 (Cook County,
Section FAU 2843 22 CR), 62T84-002.pdf, 15,285,308 bytes, %PDF-1.7, first page
reads "Notice to Bidders, Specifications and Proposal".

CALIBRATION NOTE: IDOT proposals are written against the Illinois Standard
Specifications for Road and Bridge Construction (Article 1020.05 style), not
CSI MasterFormat. Where check-portal-adapters.py reports "section numbers" for
an IDOT proposal, confirm the match by eye before trusting it -- highway
documents are full of numeric tables that can satisfy the `\\d\\d \\d\\d \\d\\d`
pattern incidentally.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Illinois",
    "type": "DOT",
    "tier": 1,
    "agency": "Illinois Department of Transportation, Bureau of Design & Environment",
    "listing_url": "https://webapps1.dot.illinois.gov/WCTB/LBHome",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
_EPLAN = "http://apps.dot.illinois.gov"


def _get(url: str, referer: str | None = None, timeout: float = 240) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "text/html,application/pdf,*/*"}
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _letting_eplan_bases(limit_lettings: int = 2) -> list[str]:
    status, body = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    guids = []
    for m in re.finditer(r'href="(/WCTB/LbLettingDetail/Index/[0-9a-f\-]{36})"', html):
        if m.group(1) not in guids:
            guids.append(m.group(1))
    bases: list[str] = []
    for g in guids[:limit_lettings]:
        st, b = _get("https://webapps1.dot.illinois.gov" + g, PORTAL["listing_url"])
        time.sleep(PAUSE)
        if st != 200 or not b:
            continue
        for m in re.finditer(r'(https?://apps\.dot\.illinois\.gov/eplan/[^"\s]*?/)/?["\s]',
                             b.decode("utf-8", "ignore")):
            base = m.group(1).replace("//eplan", "/eplan")
            if base not in bases:
                bases.append(base)
    return bases


# One PDF per contract folder is the proposal/specifications book; PLANS/ holds
# the drawings. Take the top-level PDF first -- it is the one with the
# specification text.
def _rank(url: str) -> int:
    low = urllib.parse.unquote(url).lower()
    if "/plans/" in low:
        return 2
    if "/additional information/" in low:
        return 3
    return 0


def discover(limit: int = 50) -> list[dict]:
    bases = _letting_eplan_bases()
    if not bases:
        return []
    out: list[dict] = []
    t0 = time.time()
    for base in bases:
        st, b = _get(base, PORTAL["listing_url"])
        time.sleep(PAUSE)
        if st != 200 or not b:
            continue
        html = b.decode("utf-8", "ignore")
        dirs = [d for d in re.findall(r'HREF="(/eplan/[^"]+/)"', html, re.I)
                if d.rstrip("/").count("/") > base.count("/") - 3]
        dirs = [d for d in dirs if not d.rstrip("/").endswith(base.rstrip("/").rsplit("/", 1)[-1])]
        total = min(len(dirs), limit)
        for i, d in enumerate(dirs[:limit], 1):
            st2, b2 = _get(_EPLAN + d, base)
            time.sleep(PAUSE)
            if st2 != 200 or not b2:
                continue
            pdfs = re.findall(r'HREF="([^"]+\.pdf)"', b2.decode("utf-8", "ignore"), re.I)
            if not pdfs:
                continue
            urls = sorted((_EPLAN + p for p in pdfs), key=_rank)
            name = urllib.parse.unquote(d.rstrip("/").rsplit("/", 1)[-1])
            out.append({
                "project_name": f"IDOT letting contract {name}",
                "project_number": name.split("-")[-1],
                "bid_date": None,
                "doc_urls": urls,
            })
            el = time.time() - t0
            rate = i / el * 60 if el else 0
            print(f"[{i}/{total}] {name} {len(urls)} pdf(s)  {rate:.0f}/min "
                  f"ETA {((total - i) / rate * 60) if rate else 0:.0f}s", flush=True)
            if len(out) >= limit:
                return out
    return out


def fetch(url: str) -> bytes | None:
    status, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return None
    return body


if __name__ == "__main__":  # rule 5: read back what was written
    found = discover(limit=3)
    print(f"discovered {len(found)} contracts")
    for f in found:
        b = fetch(f["doc_urls"][0])
        print(f"  {f['project_number']}: {len(b) if b else 0} bytes")
