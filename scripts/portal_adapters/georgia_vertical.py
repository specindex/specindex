"""Georgia Procurement Registry (DOAS) -- state and local construction events.

The registry page ships no rows; the grid is a DataTables POST to /gpr/eventSearch
returning JSON. Two behaviours matter:

* `search[value]` is accepted and IGNORED -- recordsFiltered comes back equal to
  recordsTotal for any term. Server-side keyword filtering does not exist here,
  so the whole open set (527 events on 2026-08-06) is pulled once and filtered
  locally. Believing the search parameter would silently mean "all events" while
  looking like a targeted query.
* Attachment filenames on this portal almost never contain the word "spec".
  Of 28 vertical events sampled, zero had a file named *spec*; the CSI content
  was inside `BL095_26 Ad1 FS 27 and 28 07_20_26.pdf`, a 15,051,785-byte
  addendum for Gwinnett County Fire Stations 27 & 28 HVAC Replacement. Georgia
  bundles the project manual into the addendum or the ITB, so ranking on the
  word "spec" returns nothing and the portal looks empty.

Consequently the ranking here is negative: push the documents that are
provably NOT spec books (notices, advertisements, plan-holder lists, award
letters) to the back and try the rest.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, urllib.error

PORTAL = {
    "state": "Georgia",
    "type": "Vertical",
    "tier": 1,
    "agency": "Dept. of Administrative Services / GSFIC (Georgia Procurement Registry)",
    "listing_url": "https://ssl.doas.state.ga.us/gpr/",
    "search_api": "https://ssl.doas.state.ga.us/gpr/eventSearch",
    "detail_url": "https://ssl.doas.state.ga.us/gpr/eventDetails"
                  "?eSourceNumber={num}&sourceSystemType={sys}",
    "needs_browser": False,
    "needs_headers": False,
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0
HOST = "https://ssl.doas.state.ga.us"

_baseline: dict[str, bytes] = {}

# Building (vertical) work only -- the registry is dominated by GDOT paving,
# commodity buys and professional services.
_VERTICAL = re.compile(
    r"renovat|remodel|building|hvac|roof|chiller|boiler|restroom|gymnasium|"
    r"classroom|fire station|facility|addition|construction|replacement", re.I)
_NOT_VERTICAL = re.compile(
    r"paving|resurfac|sidewalk|speed table|bridge|water treatment|sewer|"
    r"runway|airfield|tote bag|liners|uniform|vehicle|mowing", re.I)

# Positive hints first, then the un-hinted middle, then the known-useless.
_SPEC_FIRST = ("specification", "project manual", "technical", "spec",
               "addendum", "amendment", "itb", "ifb", "bid")
_NEVER = ("notice", "advertisement", "advertise", "plan holder", "planholder",
          "award", "at a glance", "q_a", "q&a", "sign in", "tabulation")


def _get(url: str, referer: str | None = None, data: bytes | None = None,
         extra: dict | None = None, timeout: float = 240) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/pdf,application/json,text/html,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h, data=data),
                                    timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _soft404(host_root: str) -> bytes:
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/gpr/downloadAttachment?attachmentId=0"
                       "&sourceSystemType=gpr20", referer=PORTAL["listing_url"])
        _baseline[host_root] = body
    return _baseline[host_root]


def _rank(label: str) -> int:
    low = label.lower()
    if any(n in low for n in _NEVER):
        return 90
    for i, kw in enumerate(_SPEC_FIRST):
        if kw in low:
            return i
    return len(_SPEC_FIRST)


def _search_payload(length: int) -> bytes:
    cols = ["function", "function", "title", "agencyName",
            "function", "function", "function", "status"]
    p: list[tuple[str, str]] = [("draw", "1")]
    for i, d in enumerate(cols):
        p += [(f"columns[{i}][data]", d), (f"columns[{i}][name]", ""),
              (f"columns[{i}][searchable]", "true"),
              (f"columns[{i}][orderable]", "true"),
              (f"columns[{i}][search][value]", ""),
              (f"columns[{i}][search][regex]", "false")]
    p += [("order[0][column]", "5"), ("order[0][dir]", "asc"),
          ("start", "0"), ("length", str(length)),
          ("search[value]", ""), ("search[regex]", "false"),
          ("responseType", "ALL"), ("eventStatus", "OPEN"),
          ("eventIdTitle", ""), ("govType", "ALL"), ("govEntity", ""),
          ("catType", "ALL"), ("eventProcessType", "ALL"),
          ("dateRangeType", ""), ("rangeStartDate", ""), ("rangeEndDate", ""),
          ("isReset", "false"), ("persisted", ""), ("refreshSearchData", "false")]
    return urllib.parse.urlencode(p).encode()


def discover(limit: int = 50, scan: int = 40) -> list[dict]:
    st, body = _get(PORTAL["search_api"], referer=PORTAL["listing_url"],
                    data=_search_payload(600),
                    extra={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                           "X-Requested-With": "XMLHttpRequest"})
    time.sleep(PAUSE)
    if st != 200 or body.lstrip()[:1] != b"{":
        return []
    try:
        rows = json.loads(body).get("data", [])
    except Exception:  # noqa: BLE001
        return []

    cands = [r for r in rows
             if _VERTICAL.search(r.get("title") or "")
             and not _NOT_VERTICAL.search(r.get("title") or "")][:scan]

    out: list[dict] = []
    t0 = time.time()
    for i, r in enumerate(cands, 1):
        num = r.get("esourceNumber") or ""
        url = PORTAL["detail_url"].format(
            num=urllib.parse.quote(num), sys=r.get("eSourceId") or "gpr20")
        st, d = _get(url, referer=PORTAL["listing_url"])
        time.sleep(PAUSE)
        if st != 200 or not d:
            continue
        docs, seen = [], set()
        for m in re.finditer(
                r'href="([^"]*downloadAttachment\?attachmentId=\d+[^"]*)"[^>]*>(.*?)</a>',
                d.decode("utf-8", "ignore"), re.I | re.S):
            href = urllib.parse.urljoin(url, m.group(1).replace("&amp;", "&"))
            label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            if not label.lower().endswith(".pdf") or href in seen:
                continue
            seen.add(href)
            docs.append((_rank(label), href, label))
        if not docs:
            continue
        docs.sort()
        if docs[0][0] >= 90:      # nothing but notices -- not worth a download
            continue
        out.append({
            "project_name": r.get("title") or "",
            "project_number": num,
            "bid_date": r.get("closingDate"),
            "doc_urls": [x[1] for x in docs if x[0] < 90],
            "_best_rank": docs[0][0],
        })
        el = time.time() - t0
        print(f"[{i}/{len(cands)}] {len(out)} with docs  {i / el * 60:.0f}/min "
              f"ETA {(len(cands) - i) * el / i:.0f}s", file=sys.stderr)
        if len(out) >= limit * 2:
            break

    # Addenda and ITBs before un-hinted files; both before nothing.
    out.sort(key=lambda e: e["_best_rank"])
    return out[:limit]


def fetch(url: str) -> bytes | None:
    st, body = _get(url, referer=PORTAL["listing_url"])
    time.sleep(PAUSE)
    if st != 200 or not body[:5].startswith(b"%PDF") or len(body) < 2048:
        return None
    base = _soft404(HOST)
    if base and body == base:
        return None
    return body
