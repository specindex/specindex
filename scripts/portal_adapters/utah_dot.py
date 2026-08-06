"""UDOT Contractor Zone -- advertised highway projects.

Classification (a): no login, despite every appearance of one.

connect.udot.utah.gov/business/construction points at Contractor Zone, whose
landing page shows only "Sign in" and whose /public/advertisements route renders
an empty shell without a session. That is what put Utah at Tier 2. The Angular
bundle (main.*.js) shows the app talks to a REST API whose advertisement and
file endpoints are open:

    /advertisements/projects?section=advertisements   list of advertised projects
    /project-files/files-count/<record_uuid>          which buckets have files
    /project-files/<record_uuid>/project-files        file names + sizes
    /project-files/download/<record_uuid>/project-files?file_name=<name>

All four answer an unauthenticated urllib request. One trap: dropping the
`?section=` parameter makes /advertisements/projects return HTTP 403 with
"User is not authorized to perform this action" -- a MALFORMED-REQUEST error
wearing an authorization error's clothes. Reading that as a login wall is
exactly the mistake this adapter exists to document; with the parameter present
a bare request (no Referer, no custom headers) returns the full list.

Verified 2026-08-06, no login: project F-0089(640)353 "US-89; State St & 1870 N
Intersection, Lehi", record dcd89098-c16d-4ffe-9331-a89b9ecff88a, file
F-0089(640)353_Adv_Set.pdf, 4,031,763 bytes, %PDF-1.7, 213 pages containing
"SECTION 00221S ... PART 1 GENERAL ... 1.1 SECTION INCLUDES".

CALIBRATION NOTE: UDOT special provisions DO use CSI, but the 1995 five-digit
form (SECTION 00221, 01284, 01554) rather than the current six-digit spaced
form (`01 55 40`). check-portal-adapters.py's CSI_SECTION regex only matches the
spaced form, so the evidence it can find here is the PART 1/2/3 skeleton -- and
that appears deep in the book, past the 25 pages the checker extracts, because
the first ~40 pages are federal-aid boilerplate (EEO, DBE, wage rates). A FAIL
on a UDOT Adv_Set is a page-window artefact, not an empty document.
"""
from __future__ import annotations
import json, re, time, urllib.error, urllib.parse, urllib.request

PORTAL = {
    "state": "Utah",
    "type": "DOT",
    "tier": 1,  # demoted from T2
    "agency": "Utah Department of Transportation, Contracting Services (Contractor Zone)",
    "listing_url": "https://contractorzone.udot.utah.gov/public/advertisements",
    "api_url": "https://contractorzone.udot.utah.gov/advertisements/projects?section=advertisements",
    "needs_browser": False,
    "needs_headers": False,
}

_BASE = "https://contractorzone.udot.utah.gov"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PAUSE = 1.0

# Adv_Set is the advertising special provision book -- the specification text.
# Plans are drawings and routinely 40 MB. NTC is a two-page notice. items is a
# bid schedule.
_NAME_RANK = ("adv_set", "spec", "addend", "ntc", "items", "plans")


def _rank(fname: str) -> int:
    low = fname.lower()
    for i, kw in enumerate(_NAME_RANK):
        if kw in low:
            return i
    return len(_NAME_RANK)


def _get(url: str, timeout: float = 300) -> tuple[int, bytes]:
    h = {"User-Agent": UA, "Accept": "application/json,application/pdf,*/*"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001
        return 0, b""


def _json(path: str):
    status, body = _get(_BASE + path)
    time.sleep(PAUSE)
    if status != 200 or not body:
        return None
    try:
        return json.loads(body)
    except Exception:  # noqa: BLE001
        return None


def discover(limit: int = 50) -> list[dict]:
    d = _json("/advertisements/projects?section=advertisements")
    projects = (d or {}).get("result") or []
    total = min(len(projects), limit)
    out: list[dict] = []
    t0 = time.time()
    for i, p in enumerate(projects[:limit], 1):
        uuid = p.get("record_uuid")
        files = (_json(f"/project-files/{uuid}/project-files") or {}).get("result") or []
        urls = []
        for f in sorted(files, key=lambda f: _rank(f.get("file_name", ""))):
            name = f.get("file_name") or ""
            if not name.lower().endswith(".pdf"):
                continue
            urls.append(f"{_BASE}/project-files/download/{uuid}/project-files"
                        f"?file_name={urllib.parse.quote(name)}")
        if urls:
            out.append({
                "project_name": p.get("project_name"),
                "project_number": p.get("project_number"),
                "bid_date": p.get("bid_opening_date"),
                "doc_urls": urls,
            })
        el = time.time() - t0
        rate = i / el * 60 if el else 0
        print(f"[{i}/{total}] {p.get('project_number')} {len(urls)} pdf(s)  {rate:.0f}/min "
              f"ETA {((total - i) / rate * 60) if rate else 0:.0f}s", flush=True)
    return out


def fetch(url: str) -> bytes | None:
    status, body = _get(url)
    time.sleep(PAUSE)
    if status != 200 or len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return None
    return body


if __name__ == "__main__":  # rule 5: read back what was written
    found = discover(limit=4)
    print(f"discovered {len(found)} advertised projects")
    for f in found:
        b = fetch(f["doc_urls"][0])
        print(f"  {f['project_number']}: {len(b) if b else 0} bytes  {f['doc_urls'][0][-60:]}")
