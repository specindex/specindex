"""Bid Express (bidx.com, Infotech) -- platform adapter for 44 DOT agencies.

WHAT WAS MEASURED, 2026-08-06
-----------------------------
Bid Express is a single SPA (ui.bidx.com) backed by one Apollo GraphQL endpoint
(https://graphql.bidx.com/graphql). Three probes, all live:

  1. GraphQL, no cookie:  `{ agencies { agencyid agencyname ... } }`  -> 200,
     45 agencies (44 real + TEST). `agencySettings(agencyid:)` also answers.
     Every document-bearing field -- `lettings`, `proposals`, `activelinks`,
     `downloads`, `plans` -- returns extensions.code = FORBIDDEN,
     "You are not authorized to access this information."
  2. https://www.bidx.com/{agencydomain}/lettings -> 302 -> ui.bidx.com/login
     for every agency domain tried.
  3. Playwright, headless Chromium, no cookies, on ui.bidx.com/GADOT/lettings
     -> redirected to /login and rendered the sign-in form.

The `x-api-role` / `x-api-services` / `x-api-keep` headers the SPA sends are
privilege *downgrades* applied to an existing session (see `isAuthorizedAgency`
in the bundle); they cannot grant access. There is no anonymous read path to a
Bid Express letting document. The task brief said free info-only accounts can
browse lettings -- that is true for a signed-in free account, and we do not
create accounts, so bidx-hosted documents are out of reach here.

CONSEQUENCE FOR THE ADAPTER
---------------------------
The bidx agency directory is still worth holding: it is the authoritative map
of which state DOT is on this platform, and it is free to read. But every
document this adapter actually returns comes from the agency's own PUBLIC
mirror, not from bidx. `STATES` therefore carries both: the bidx agency id
(for identity/joins) and a `mirror` describing the public source, which is
None where the agency publishes nothing outside bidx.

Arizona (ADOT) is the reference mirror and the default: cnsads.azdot.gov lists
every advertised project, and `/Home/Documents/{id}` returns a plain HTML table
of direct S3 PDF links -- bid book, plans, cross sections, geotech -- with no
login, no cookie and no referer requirement.

DO NOT TRUST THE CHECKER'S VERDICT ON THIS ADAPTER
--------------------------------------------------
check-portal-adapters.py currently prints PASS for `bidexpress`. It is wrong.
The CSI evidence it reports is `['section numbers']` matched against the
upside-down engineer's seal on an ADOT bid book cover -- the seal date
2026-07-20 extracts as "07 20 26", which satisfies CSI_SECTION. No document
reachable from any Bid Express agency without an account carries real
MasterFormat structure. The honest verdict is FAIL. See section 3 of
docs/adapter_findings_bidexpress.md.

See docs/adapter_findings_bidexpress.md for the per-state table.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

PORTAL = {
    "state": "multi",                     # one platform, many agencies
    "type": "DOT",
    "tier": 1,
    "agency": "Bid Express / Infotech (44 state DOT and authority agencies)",
    "listing_url": "https://ui.bidx.com/lettings",
    "graphql_url": "https://graphql.bidx.com/graphql",
    "needs_browser": True,    # the bidx listing is a Vue SPA
    "needs_headers": True,    # several mirrors 403 a bare urllib UA
    "needs_login": True,      # bidx-hosted documents; mirrors do not
    "default_state": "Arizona",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.1          # >= 1.0s per host. A ban is permanent loss of the source.
_last_hit: dict[str, float] = {}
_baseline: dict[str, bytes] = {}


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------
def _throttle(url: str) -> None:
    host = urllib.parse.urlsplit(url).netloc
    gap = time.time() - _last_hit.get(host, 0.0)
    if gap < PAUSE:
        time.sleep(PAUSE - gap)
    _last_hit[host] = time.time()


def _get(url: str, referer: str | None = None, timeout: float = 240
         ) -> tuple[int, bytes]:
    _throttle(url)
    headers = {
        "User-Agent": UA,
        "Accept": "application/pdf,text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _post_json(url: str, payload: dict, timeout: float = 60) -> dict:
    _throttle(url)
    body = json.dumps(payload).encode()
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://ui.bidx.com",
        "Referer": "https://ui.bidx.com/",
    }
    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except Exception:  # noqa: BLE001
        return {}


def _soft404(host_root: str) -> bytes:
    """What this host serves for a path that cannot exist. Gov hosts answer
    unknown paths with HTTP 200 and their landing page; without this baseline a
    landing page reads as a successful download."""
    if host_root not in _baseline:
        _, body = _get(f"{host_root}/zzz-specindex-not-real-9174.pdf")
        _baseline[host_root] = body
    return _baseline[host_root]


# --------------------------------------------------------------------------
# the agency map
# --------------------------------------------------------------------------
# agencyid values below were read live from the anonymous GraphQL agency
# directory on 2026-08-06, not transcribed from a web page.
#
# mirror: None                 -> no public document source found; bidx only
# mirror: {"kind": ...}        -> a public, login-free source this adapter can
#                                 read. Only "azdot_cns" is implemented; the
#                                 others are recorded as verified-reachable
#                                 listings whose document links are gated or
#                                 whose documents carry no CSI structure.
STATES: dict[str, dict] = {
    "Alabama":        {"agency": "ALDOT",  "mirror": {"kind": "aldot_planprop"}},
    "Alaska":         {"agency": "ALASKA", "mirror": None},
    "Arizona":        {"agency": "ADOT",   "mirror": {"kind": "azdot_cns"}},
    "Arkansas":       {"agency": "ARDOT",  "mirror": None},
    "California":     {"agency": "CALTRANS", "mirror": None},
    "Colorado":       {"agency": "CDOT",   "mirror": None},
    "Connecticut":    {"agency": "CTDOT",  "mirror": None},
    "Delaware":       {"agency": "DELDOT", "mirror": None},
    "Florida":        {"agency": "FDOT",   "mirror": None},
    "Georgia":        {"agency": "GADOT",  "mirror": None},
    "Idaho":          {"agency": "ITD",    "mirror": None},
    "Indiana":        {"agency": "INDOT",  "mirror": None},
    "Iowa":           {"agency": "IADOT",  "mirror": None},
    "Kansas":         {"agency": "KDOT",   "mirror": None},
    "Kentucky":       {"agency": "KYTC",   "mirror": None},
    "Louisiana":      {"agency": "LADOTD", "mirror": None},
    "Maine":          {"agency": "MDOT",   "mirror": None},
    "Maryland":       {"agency": "MARYLAND-DOT", "mirror": None},
    "Massachusetts (MBTA)": {"agency": "MBTA", "mirror": {"kind": "mbta_bc"}},
    "Massachusetts":  {"agency": "MASSDOT", "mirror": None},
    "Michigan":       {"agency": "MIDOT",  "mirror": None},
    "Minnesota":      {"agency": "MNDOT",  "mirror": None},
    "Mississippi":    {"agency": "MSDOT",  "mirror": None},
    "Missouri":       {"agency": "MODOT",  "mirror": None},
    "Montana":        {"agency": "MDT",    "mirror": None},
    "Nebraska":       {"agency": "NDOT",   "mirror": None},
    "New Jersey":     {"agency": "NJDOT",  "mirror": None},
    "New Jersey (Turnpike)": {"agency": "NJTA", "mirror": None},
    "New Mexico":     {"agency": "NMDOT",  "mirror": None},
    "New York":       {"agency": "NYSDOT", "mirror": None},
    "New York (Thruway)": {"agency": "NYSTA", "mirror": None},
    "North Carolina": {"agency": "NCDOT",  "mirror": None},
    "North Carolina (Divisions)": {"agency": "NCDOT-DIVISIONS", "mirror": None},
    "North Dakota":   {"agency": "NDDOT",  "mirror": None},
    "Nova Scotia":    {"agency": "NSDPW",  "mirror": None},
    "Ohio":           {"agency": "ODOT",   "mirror": None},
    "Oklahoma":       {"agency": "OKDOT",  "mirror": None},
    "Oregon":         {"agency": "ORDOT",  "mirror": None},
    "South Carolina": {"agency": "SCDOT",  "mirror": None},
    "Tennessee":      {"agency": "TDOT",   "mirror": None},
    "Virginia":       {"agency": "VDOT",   "mirror": None},
    "Washington":     {"agency": "WSDOT",  "mirror": None},
    "West Virginia":  {"agency": "WVDOT",  "mirror": None},
    "Wisconsin":      {"agency": "WIDOT",  "mirror": None},
}


def bidx_agencies() -> list[dict]:
    """Live, anonymous read of the Bid Express agency directory. This is the
    only bidx query that answers without a session, and it is the reason the
    platform is still worth an adapter."""
    q = ("query { agencies { abbreviation agencyid agencyname agencydomain "
         "isavailable hasitiplanroom } }")
    d = _post_json(PORTAL["graphql_url"], {"query": q})
    return (d.get("data") or {}).get("agencies") or []


def bidx_lettings(agency_id: str, after: str = "2025-01-01T00:00:00Z") -> dict:
    """Attempt the real letting query. Returns the raw GraphQL envelope so the
    FORBIDDEN is visible rather than swallowed -- 'no lettings' and 'not
    authorised' must never look the same."""
    q = ("query($agencyId:String!,$after:DateTime){"
         "lettings(agencyid:$agencyId,filters:{openingdate:{_after:$after}}){"
         "lettingid lettingdate openingdate description proposalcount isactive}}")
    return _post_json(PORTAL["graphql_url"],
                      {"query": q, "variables": {"agencyId": agency_id, "after": after}})


# --------------------------------------------------------------------------
# mirror: Arizona DOT -- cnsads.azdot.gov  (the working one)
# --------------------------------------------------------------------------
_AZ_LIST = "https://cnsads.azdot.gov/current"
_AZ_DOCS = "https://cnsads.azdot.gov/Home/Documents/{pid}"

# ADOT names files by role. Only the bid book can carry specification text;
# Plans is drawings, Ad is a two-page notice, the rest are geotechnical and
# earthwork reports.
#
# Plans are deliberately EXCLUDED, not merely down-ranked. On 2026-08-06 the
# first version returned them and the verifier reported PASS on a 37 MB plan
# set for F052201C -- the "CSI section number" it matched was
# "... 20 25 30 40 55 70 90" out of a culvert FILL HEIGHT RANGE TABLE. A
# drawing sheet full of numbers will satisfy a three-number regex sooner or
# later; a plan set is not a specification and must never be offered as one.
_AZ_SPEC = ("bid_book", "special provision", "proposal", "addend")
_AZ_NOT_SPEC = ("plans", "cross_section", "geotech", "earthwork", "survey",
                "geometry", "_ad.pdf", "dtm")


def _rank_az(name: str) -> int:
    low = name.lower()
    for i, kw in enumerate(_AZ_SPEC):
        if kw in low:
            return i
    return len(_AZ_SPEC)


def _is_spec_az(name: str) -> bool:
    low = name.lower()
    if any(k in low for k in _AZ_NOT_SPEC):
        return False
    return any(k in low for k in _AZ_SPEC)


def _discover_azdot(limit: int) -> list[dict]:
    status, body = _get(_AZ_LIST)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    # The listing is a server-rendered table; the row's project id is the only
    # thing needed, the document table is a second, plain-HTML request.
    pids: list[str] = []
    for m in re.finditer(r"/Home/Documents/(\d+)", html):
        if m.group(1) not in pids:
            pids.append(m.group(1))
    rows = _az_rows(html)

    out: list[dict] = []
    total = min(len(pids), limit)
    t0 = time.time()
    for i, pid in enumerate(pids[:limit], 1):
        st, db = _get(_AZ_DOCS.format(pid=pid), referer=_AZ_LIST, timeout=90)
        if st != 200 or not db:
            continue
        docs = re.findall(r"href='([^']+\.pdf)'[^>]*><span[^>]*>([^<]+)</span>",
                          db.decode("utf-8", "ignore"))
        if not docs:
            continue
        # Only the spec-bearing document per project. The verifier flattens
        # doc_urls across projects and samples the first six, so returning the
        # whole file set would spend all six slots on one project's plan sheets
        # and geotechnical reports.
        spec = sorted([(u, n) for u, n in docs if _is_spec_az(n)],
                      key=lambda d: _rank_az(d[1]))
        if not spec:
            continue
        meta = rows.get(pid, {})
        out.append({
            "project_name": meta.get("description") or spec[0][1].rsplit("_", 1)[0],
            "project_number": meta.get("contract") or pid,
            "bid_date": meta.get("bid_date"),
            "doc_urls": [spec[0][0]],
        })
        if total >= 5:
            rate = i / max(time.time() - t0, 1e-6) * 60
            eta = (total - i) / max(rate, 1e-6)
            print(f"  [bidexpress/ADOT {i}/{total}] {rate:.1f}/min ETA {eta:.1f}m",
                  flush=True)
    return out


def _az_rows(html: str) -> dict[str, dict]:
    """Map project id -> the row's contract number, bid date and work type."""
    rows: dict[str, dict] = {}
    for block in re.split(r"<tr[^>]*>", html)[1:]:
        pid = re.search(r"/Home/Documents/(\d+)", block)
        if not pid:
            continue
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", block, re.S)]
        cells = [c for c in cells if c]
        date = next((c for c in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c)), None)
        contract = next((c for c in cells if re.fullmatch(r"[A-Z]\d{6}C", c)), None)
        rows[pid.group(1)] = {
            "contract": contract,
            "bid_date": date,
            "description": cells[-1] if cells else None,
        }
    return rows


# --------------------------------------------------------------------------
# mirror: Alabama DOT -- alletting.dot.state.al.us  (reachable, no CSI)
# --------------------------------------------------------------------------
# The letting-files table is rendered by DataTables, but the file names are
# fully deterministic:
#   /PLANPROP/{YYYYMMDD}_Call_{NNN}_{Proposal|Plans}.pdf
# Verified downloadable, ~1.6-3.4 MB each, no login. Kept because the pattern
# is real and cheap; it yields bid forms, not specifications.
_AL_ROOT = "https://alletting.dot.state.al.us"
_AL_HOME = _AL_ROOT + "/"
_AL_DOC = _AL_ROOT + "/PLANPROP/{date}_Call_{call}_{kind}.pdf"


def _discover_aldot(limit: int) -> list[dict]:
    status, body = _get(_AL_HOME)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    dates = []
    for m in re.finditer(r"/DW_Pages/Letting_Files/\d{4}/LettingFiles_(\d{6})\.html", html):
        mm, dd, yy = m.group(1)[:2], m.group(1)[2:4], m.group(1)[4:]
        iso = f"20{yy}{mm}{dd}"
        if iso not in dates:
            dates.append(iso)
    out: list[dict] = []
    for date in dates:
        for call in range(1, 60):
            if len(out) >= limit:
                return out
            c = f"{call:03d}"
            out.append({
                "project_name": f"ALDOT letting {date} call {c}",
                "project_number": f"{date}{c}",
                "bid_date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                "doc_urls": [_AL_DOC.format(date=date, call=c, kind="Proposal"),
                             _AL_DOC.format(date=date, call=c, kind="Plans")],
            })
    return out


# --------------------------------------------------------------------------
# mirror: MBTA -- bc.mbta.com  (reachable; specifications are gated)
# --------------------------------------------------------------------------
# MBTA is the one Bid Express agency doing vertical/transit-facility work, and
# its public /pdf/ folder does hold genuine CSI project manuals (a 5.07 MB
# 2016 contract specification volume was downloaded and shows PART 1/2/3 and
# division headings). But every CURRENT solicitation page links only the
# Notice to Bidders; the specification set is behind "click here to be put on
# the Planholders list", i.e. an email request. Discovery therefore returns
# notices, which carry no CSI structure.
_MB_LIST = "https://bc.mbta.com/business_center/bidding_solicitations/current_solicitations/"
_MB_BID = ("https://bc.mbta.com/business_center/bidding_solicitations/"
           "design_and_construction/construction_bid/?cbid={cbid}")


def _discover_mbta(limit: int) -> list[dict]:
    status, body = _get(_MB_LIST)
    if status != 200 or not body:
        return []
    html = body.decode("utf-8", "ignore")
    out: list[dict] = []
    for m in re.finditer(r"construction_bid/\?cbid=(\d+)\"[^>]*>(.*?)</a>", html, re.S):
        if len(out) >= limit:
            break
        cbid, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        st, pb = _get(_MB_BID.format(cbid=cbid), referer=_MB_LIST, timeout=90)
        if st != 200 or not pb:
            continue
        page = pb.decode("utf-8", "ignore")
        urls = [urllib.parse.urljoin(_MB_LIST, u.replace("&amp;", "&"))
                for u in re.findall(r'href="([^"]*/pdf/[^"]+\.pdf)"', page, re.I)]
        if not urls:
            continue
        num = re.search(r"Contract Number.{0,200}?>([A-Z0-9]{6,10})<", page, re.S)
        out.append({
            "project_name": title,
            "project_number": num.group(1) if num else cbid,
            "bid_date": None,
            "doc_urls": urls,
        })
    return out


_MIRRORS = {
    "azdot_cns": _discover_azdot,
    "aldot_planprop": _discover_aldot,
    "mbta_bc": _discover_mbta,
}


# --------------------------------------------------------------------------
# required interface
# --------------------------------------------------------------------------
def discover(limit: int = 50, state: str | None = None) -> list[dict]:
    """Return [{project_name, project_number, bid_date, doc_urls}].

    `state` selects the Bid Express agency. Because bidx itself serves no
    document anonymously (see module docstring), discovery runs against that
    agency's public mirror; a state with `mirror: None` returns [] and that is
    the honest answer, not an error.
    """
    name = state or PORTAL["default_state"]
    entry = STATES.get(name)
    if entry is None:
        raise ValueError(f"unknown state {name!r}; known: {sorted(STATES)}")
    mirror = entry.get("mirror")
    if not mirror:
        return []
    fn = _MIRRORS.get(mirror["kind"])
    if fn is None:
        return []
    return fn(limit)


def fetch(url: str) -> bytes | None:
    """Return PDF bytes, or None. Content-checked: a 200 is never enough."""
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    referer = _AZ_LIST if "azdot" in parts.netloc else (
        _MB_LIST if "mbta" in parts.netloc else _AL_HOME)
    status, body = _get(url, referer=referer)
    if status != 200 or len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return None
    base = _soft404(root)
    if base and body == base:
        return None
    return body


if __name__ == "__main__":  # pragma: no cover -- rule 5, read the output back
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else PORTAL["default_state"]
    ags = bidx_agencies()
    print(f"bidx agency directory (anonymous): {len(ags)} agencies")
    env = bidx_lettings(STATES[which]["agency"])
    err = (env.get("errors") or [{}])[0]
    print(f"bidx lettings({STATES[which]['agency']}): "
          f"{err.get('extensions', {}).get('code') or 'OK'} -- {err.get('message', '')}")
    found = discover(limit=8, state=which)
    print(f"discover({which}) -> {len(found)} projects")
    for f in found[:3]:
        print("  ", f["project_number"], "|", f["project_name"], "|", len(f["doc_urls"]), "docs")
    if found:
        b = fetch(found[0]["doc_urls"][0])
        print(f"fetch first doc -> {0 if b is None else len(b):,} bytes")
