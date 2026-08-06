"""MoDOT Bid Letting Plans Room -- highway letting documents.

Classification (a): fully open. The workbook called this Tier 2 ("free account
believed necessary") because the plans room offers Account/Create and
Account/ResetPwd links in its header. It does not gate the documents behind
them: every bid book, notice and addendum streams to an anonymous request.

Verified 2026-08-06, no login:
  ViewStream/22418?type=plan     -> 260821_A01_JNW0105_JNW0106_Bid_Book.pdf, 947,598 bytes
  ViewStream/6108?type=notice    -> 260821_Notice_To_Contractors.pdf, 152,958 bytes
  ViewStream/36882?type=addenda  -> 260821_Notice_To_Contractors_F01.pdf, 146,627 bytes
all %PDF-1.4 with Content-Disposition filenames.

Do NOT follow the plans room's bidx.com link. Bid Express is another agent's
source and is out of scope here.

CALIBRATION NOTE -- expected checker result is FAIL, and that is the finding.
MoDOT bid books are written against the Missouri Standard Specifications for
Highway Construction. The 260821-A01 bid book's own words: "See Secs 101-103 of
the Missouri Standard Specifications for Highway Construction" and "considered
irregular per section 102.8". There is no CSI MasterFormat numbering, no
DIVISION headings and no PART 1/2/3 skeleton anywhere in it, so
check-portal-adapters.py -- which requires CSI structure -- will reject it.
The portal is open and the content is real specification text in a different
numbering system. Do not weaken the checker to make this pass.
"""
from __future__ import annotations
import re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Missouri",
    "type": "DOT",
    "tier": 1,  # demoted from T2
    "agency": "Missouri Department of Transportation, Bid Letting Plans Room",
    "listing_url": "https://modotweb.modot.mo.gov/BidLettingPlansRoom/Letting",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
_BASE = "https://modotweb.modot.mo.gov"

# The bid book (type=plan) is the document with the job special provisions.
# Road/Bridge JSPs come next. general_info is the letting calendar -- pure
# noise; open_info is bid-opening logistics.
_TYPE_RANK = ("plan", "road_jsp", "bridge_jsp", "addenda", "notice",
              "x_section", "open_info", "general_info")


def _rank(url: str) -> int:
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("type", [""])[0]
    return _TYPE_RANK.index(q) if q in _TYPE_RANK else len(_TYPE_RANK)


def _get(url: str, referer: str | None = None, timeout: float = 180) -> tuple[int, bytes, str]:
    h = {"User-Agent": UA, "Accept": "text/html,application/pdf,*/*"}
    if referer:
        h["Referer"] = referer
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Disposition") or ""
    except urllib.error.HTTPError as e:
        return e.code, b"", ""
    except Exception:  # noqa: BLE001
        return 0, b"", ""


_ROW = re.compile(
    r'value="(?P<call>[A-Z]\d{2})"\s*/>.*?<span>(?P<desc>.*?)</span>(?P<links>.*?)(?=value="[A-Z]\d{2}"|\Z)',
    re.S)


def discover(limit: int = 50) -> list[dict]:
    status, body, _ = _get(PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")

    out: list[dict] = []
    for m in _ROW.finditer(html):
        call = m.group("call")
        desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group("desc"))).strip()
        urls = []
        for h in re.findall(r'href="(/BidLettingPlansRoom/Letting/ViewStream/\d+\?type=[a-z_]+)"',
                            m.group("links")):
            u = _BASE + h
            if u not in urls:
                urls.append(u)
        if not urls:
            continue
        urls.sort(key=_rank)
        job = re.search(r"Job\s+([A-Z0-9]+)", desc)
        out.append({
            "project_name": desc[:220] or f"MoDOT call {call}",
            "project_number": job.group(1) if job else call,
            "bid_date": None,
            "doc_urls": urls,
        })
        if len(out) >= limit:
            break
    print(f"discovered {len(out)} MoDOT letting calls", flush=True)
    return out


def fetch(url: str) -> bytes | None:
    status, body, cd = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if status != 200 or len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return None
    return body


if __name__ == "__main__":  # rule 5: read back what was written
    found = discover(limit=3)
    for f in found:
        b = fetch(f["doc_urls"][0])
        print(f"  {f['project_number']}: {len(b) if b else 0} bytes  {f['doc_urls'][0]}")
