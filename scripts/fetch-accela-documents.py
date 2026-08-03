#!/usr/bin/env python3
"""Pull real permit documents from the ungated Accela Citizen Access tenants
straight to GCS -- no local copy of the binaries kept.

Six Accela tenants serve attachments to ANONYMOUS users (no login, no
account, no CAPTCHA), verified live 2026-08-03. Accela is an ASP.NET
WebForms app driven by ViewState + __doPostBack, so raw curl cannot walk
it; this uses Playwright, the same approach as
scripts/state_agent_pipeline/core/ingestion/accela_provider.py.

The access pattern is a SESSION-SCOPED three step flow:

  1. General Search on {base}/Cap/CapHome.aspx?module={MODULE} -- select the
     permit type, click search, then harvest capID1/capID2/capID3 AND
     agencyCode from the results grid's own row hrefs.
  2. GET {base}/Cap/CapDetail.aspx?Module={M}&TabName={M}&capID1=..&capID2=..
     &capID3=..&agencyCode={AGENCY} -- this is both a data source (applicant,
     owner, a fuller scope-of-work description than the grid carries) and a
     REQUIRED session side effect for step 3.
  3. GET {base}/FileUpload/AttachmentsList.aspx?iframeid=ctl00_PlaceHolderMain
     _attachmentEdit&module={M}&...&agencyCode={AGENCY}&isForConditionDocument=N
     -- note there is NO capID in this URL. It resolves against the
     last-viewed record in the session, so step 2 MUST immediately precede it
     on the same page/context. Each row's download is fired by
     __doPostBack('attachmentList$gdvAttachmentList$ctlNN$lnkFileName','').

Two traps that make a viable tenant look broken (both cost real time
2026-08-03 -- do not "fix" either back):

  * The agency code is NOT the URL path segment on custom-domain tenants
    (Boise serves from permits.cityofboise.org/CitizenAccess but its
    agencyCode is not "CitizenAccess"). Always harvest agencyCode from the
    results grid hrefs; never parse it out of the endpoint URL.
  * A populated date range SUPPRESSES the results grid entirely on ACFW,
    BUTLER and OLMSTED -- they return no grid at all with Start/End Date
    filled and work fine with them blank. Per-tenant `use_date_range` below
    records which tenants tolerate dates; only INDY/BOISE do.

Storage: gs://specindex-ai-raw-documents/{state}/{project_id}/{filename},
the same {state}/{project_id}/{filename} layout fetch-snohomish-documents.py
and fetch-sam-gov-documents.py use, so nothing downstream needs a parser
change. Bytes go from the browser's download temp file straight into the
upload call and the temp file is deleted immediately; nothing is staged
inside the repo and no binary is ever committed.

project_id is derived with exactly the same rule AccelaProvider.to_projects()
uses -- {state}-{county}-accela-{slug(county-permit_number)} truncated to 80
chars -- so documents land under the ids the corpus ingest already assigns.

Usage:
    python3 scripts/fetch-accela-documents.py --tenant OK-OKLAHOMA --limit 3 --dry-run
    python3 scripts/fetch-accela-documents.py --tenant OK-OKLAHOMA --limit 3
    python3 scripts/fetch-accela-documents.py --tenant ALL --limit 200 --workers 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GCS_BUCKET = "specindex-ai-raw-documents"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SEARCH_TYPE_SELECT = "#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType"
SEARCH_BUTTON = "#ctl00_PlaceHolderMain_btnNewSearch"
RESULT_GRID = "#ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList"
START_DATE_IDS = [
    "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "ctl00_PlaceHolderMain_generalSearchForm_txtGSPermitDateFrom",
]
END_DATE_IDS = [
    "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "ctl00_PlaceHolderMain_generalSearchForm_txtGSPermitDateTo",
]
ATT_URL = (
    "{base}/FileUpload/AttachmentsList.aspx?iframeid=ctl00_PlaceHolderMain_attachmentEdit"
    "&module={mod}&isInConfirm=False&isdetail=True&isaccountmanager=False&isAdmin=False"
    "&isPeopleDocument=&agencyCode={ag}&isForConditionDocument=N"
)
DETAIL_URL = (
    "{base}/Cap/CapDetail.aspx?Module={mod}&TabName={mod}"
    "&capID1={c1}&capID2={c2}&capID3={c3}&agencyCode={ag}"
)

# The six tenants that actually serve attachments anonymously, with the
# live-measured hit rate from the 2026-08-03 recon (documents found on N of
# M sampled records). endpoint/module/permit_type_label mirror
# scripts/state_agent_pipeline/core/state_configs.py -- keep them in sync.
TENANTS: dict[str, dict[str, Any]] = {
    "IN-INDIANAPOLIS": {
        "state_code": "IN",
        "state_dir": "indiana",
        "county": "Marion",
        "base_url": "https://aca-prod.accela.com/INDY",
        "module": "Permits",
        "permit_type_label": "Improvement Location Permit-Non-Residential",
        "use_date_range": True,
        "hit_rate": "3/3 (incl. an 8.9 MB architectural sheet set)",
    },
    "ID-ADA": {
        "state_code": "ID",
        "state_dir": "idaho",
        "county": "Ada",
        # Custom domain, not aca-prod -- and "CitizenAccess" here is a URL
        # path segment, NOT the agency code. agencyCode is harvested live.
        "base_url": "https://permits.cityofboise.org/CitizenAccess",
        "module": "Building",
        "permit_type_label": "502-New or Added Commercial",
        "use_date_range": True,
        "hit_rate": "5/5",
    },
    "IN-ALLEN": {
        "state_code": "IN",
        "state_dir": "indiana",
        "county": "Allen",
        "base_url": "https://aca-prod.accela.com/ACFW",
        "module": "Planning",
        "permit_type_label": (
            "08. Site Plan Review (Commercial, Industrial, Multifamily, "
            "School, Religious Institution)"
        ),
        # Dates suppress the grid on this tenant -- verified live.
        "use_date_range": False,
        "hit_rate": "5/5",
    },
    "OH-BUTLER": {
        "state_code": "OH",
        "state_dir": "ohio",
        "county": "Butler",
        "base_url": "https://aca-prod.accela.com/BUTLER",
        "module": "Building",
        "permit_type_label": "Building/Commercial/Alterations/Other",
        "use_date_range": False,
        "hit_rate": "4/5",
    },
    "MN-OLMSTED": {
        "state_code": "MN",
        "state_dir": "minnesota",
        "county": "Olmsted",
        "base_url": "https://aca-prod.accela.com/OLMSTED",
        "module": "Building",
        "permit_type_label": "Commercial Building (New Building)",
        "use_date_range": False,
        "hit_rate": "2/5",
    },
    "OK-OKLAHOMA": {
        "state_code": "OK",
        "state_dir": "oklahoma",
        "county": "Oklahoma",
        "base_url": "https://aca-prod.accela.com/OKC",
        "module": "Permits",
        "permit_type_label": "Building - Commercial",
        "use_date_range": True,
        "hit_rate": "7/7",
    },
}

# Attachment names worth skipping outright -- pure transactional trivia, same
# triage idea as fetch-snohomish-documents.py's tier 3.
SKIP_NAME_HINTS = [
    "receipt", "invoice", "fee ", "payment", "inspection card", "placard",
    "refund", "transaction",
]

SIZE_RE = re.compile(r"([\d,.]+)\s*(KB|MB|GB|bytes?|B)\b", re.I)


def parse_size(text: str) -> int | None:
    m = SIZE_RE.search(text or "")
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = m.group(2).upper()
    mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}.get(unit, 1)
    return int(n * mult)


def safe_name(name: str) -> str:
    """Accela hands back some genuinely hostile filenames (Indianapolis
    surfaces the full FileNet path: '__isipp01apps_apps$_filenet_...pdf').
    Keep it recognisable but make it a legal single GCS object name."""
    name = re.sub(r"[\\/]+", "_", (name or "").strip()) or "document"
    return name[-180:]


def project_id_for(tenant: dict[str, Any], permit_number: str) -> str:
    from project_identity import slugify

    county = tenant["county"]
    uid = slugify(f"{county}-{permit_number}")
    return f"{tenant['state_code'].lower()}-{county.lower().replace(' ', '')}-accela-{uid}"[:80]


# --------------------------------------------------------------------------
# phase 1: harvest records (one session, one page) --------------------------
# --------------------------------------------------------------------------

def harvest_records(
    page,
    tenant: dict[str, Any],
    *,
    lookback_days: int,
    max_pages: int,
    sleep: float,
) -> list[dict[str, Any]]:
    base, mod = tenant["base_url"], tenant["module"]
    page.goto(f"{base}/Cap/CapHome.aspx?module={mod}", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    label = tenant.get("permit_type_label")
    if label and page.locator(SEARCH_TYPE_SELECT).count():
        opts = page.eval_on_selector_all(
            SEARCH_TYPE_SELECT + " option", "os => os.map(o => o.textContent.trim())"
        )
        pick = next((o for o in opts if o.lower() == label.lower()), None)
        if pick is None:
            pick = next(
                (o for o in opts if "commercial" in o.lower() and ("new" in o.lower() or "building" in o.lower())),
                None,
            )
        if pick:
            try:
                page.select_option(SEARCH_TYPE_SELECT, label=pick)
                print(f"  permit type: {pick!r}", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                print(f"  [warn] permit type not selectable ({e}); searching all types", file=sys.stderr)

    if tenant.get("use_date_range"):
        start = (date.today() - timedelta(days=lookback_days)).strftime("%m/%d/%Y")
        end = date.today().strftime("%m/%d/%Y")
        for fid in START_DATE_IDS:
            if page.locator("#" + fid).count():
                page.fill("#" + fid, start)
                break
        for fid in END_DATE_IDS:
            if page.locator("#" + fid).count():
                page.fill("#" + fid, end)
                break
        print(f"  date window: {start}..{end}", file=sys.stderr)
    else:
        # NOT an oversight: filling these blanks out the results grid on
        # ACFW/BUTLER/OLMSTED. See module docstring.
        print("  date window: (blank -- this tenant suppresses results with dates set)", file=sys.stderr)

    if page.locator(SEARCH_BUTTON).count() == 0:
        print("  [error] no search button on CapHome (wrong module?)", file=sys.stderr)
        return []
    page.locator(SEARCH_BUTTON).first.click()
    try:
        page.wait_for_load_state("networkidle", timeout=50000)
    except Exception:  # noqa: BLE001 -- networkidle is best-effort on ACA
        pass
    page.wait_for_timeout(2500)

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for page_num in range(1, max_pages + 1):
        rows = _grid_rows_stable(page)
        if not rows and page_num == 1:
            body = re.sub(r"\s+", " ", page.inner_text("body"))[:200]
            print(f"  [error] no capID rows in results grid; body={body}", file=sys.stderr)
            break
        new = 0
        for r in rows:
            key = (r["capID1"], r["capID2"], r["capID3"])
            if key in seen:
                continue
            seen.add(key)
            records.append(r)
            new += 1
        print(f"  page {page_num}: {new} new record(s), {len(records)} total", file=sys.stderr)

        nxt = page.locator("a:has-text('Next >')").first
        if nxt.count() == 0:
            break
        try:
            nxt.click()
            page.wait_for_load_state("networkidle", timeout=40000)
        except Exception as e:  # noqa: BLE001 -- ACA throttles long anon paging
            print(f"  [warn] paging stopped at page {page_num}: {str(e)[:90]}", file=sys.stderr)
            break
        page.wait_for_timeout(int(sleep * 1000))
    return records


def _grid_rows_stable(page, tries: int = 8, wait_ms: int = 1200) -> list[dict[str, Any]]:
    """Poll until the row count stops growing.

    Real bug found live 2026-08-03 on OKC: reading the grid straight after
    'networkidle' returned 3 of the page's 10 rows -- the remaining anchors
    were still being rendered, so a single read silently dropped 70% of
    page 1. Same failure mode AccelaProvider already polls around for its
    header row."""
    best: list[dict[str, Any]] = []
    stable = 0
    for _ in range(tries):
        try:
            rows = _grid_rows(page)
        except Exception:  # noqa: BLE001 -- mid-render navigation
            rows = []
        if len(rows) > len(best):
            best, stable = rows, 0
        elif best:
            stable += 1
            if stable >= 2:
                break
        page.wait_for_timeout(wait_ms)
    return best


def _grid_rows(page) -> list[dict[str, Any]]:
    """One dict per results-grid row: capIDs + agencyCode harvested from the
    row's OWN href (never guessed from the endpoint path), plus the row's
    cell text so a permit number is available without a detail fetch.

    Fewer rows than the grid shows is EXPECTED, not a parse failure: OKC page
    1 renders 10 rows but only 3 are hyperlinked, because unissued temporary
    applications ('26TMP-069032') have no CapDetail link at all -- only
    issued records ('BLDC-2026-05539') do, and only those can have
    attachments. Harvesting by href therefore filters to exactly the
    records worth fetching."""
    raw = page.eval_on_selector_all(
        f"{RESULT_GRID} a[href*='capID1'], a[href*='capID1']",
        "as => as.map(a => ({href: a.getAttribute('href'), text: a.innerText.trim(),"
        " row: a.closest('tr') ? Array.from(a.closest('tr').querySelectorAll('td'))"
        ".map(td => td.innerText.trim()) : []}))",
    )
    out = []
    for item in raw:
        href = item.get("href") or ""
        m = re.search(r"capID1=([^&'\"]+)&capID2=([^&'\"]+)&capID3=([^&'\"]+)", href)
        if not m:
            continue
        ag = re.search(r"agencyCode=([A-Za-z0-9_\-]+)", href)
        cells = item.get("row") or []
        permit = item.get("text") or ""
        if not re.search(r"\d", permit):
            permit = next((c for c in cells if re.search(r"\d{3}", c) and "/" not in c), permit)
        row_date = next((c for c in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c.strip())), "")
        out.append(
            {
                "capID1": m.group(1),
                "capID2": m.group(2),
                "capID3": m.group(3),
                "agency_code": ag.group(1) if ag else "",
                "permit_number": permit.strip(),
                "row_date": row_date,
                "row_cells": cells[:12],
            }
        )
    return out


# --------------------------------------------------------------------------
# phase 2: per-record detail + attachments ---------------------------------
# --------------------------------------------------------------------------

DETAIL_FIELDS = [
    ("applicant", r"Applicant:?\s*(.{0,160}?)(?:Owner|Project|Description|Record|$)"),
    ("owner", r"Owner:?\s*(.{0,160}?)(?:Applicant|Project|Description|Record|$)"),
    (
        "description",
        r"(?:Description of Work|Project Description|Detail Information|Description):?\s*(.{0,700}?)"
        r"(?:More Details|Application Information|Record Status|$)",
    ),
]


def scrape_detail(page, tenant: dict[str, Any], rec: dict[str, Any], sleep: float) -> dict[str, Any]:
    url = DETAIL_URL.format(
        base=tenant["base_url"],
        mod=tenant["module"],
        c1=rec["capID1"],
        c2=rec["capID2"],
        c3=rec["capID3"],
        ag=rec["agency_code"],
    )
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(int(sleep * 1000) + 1500)
    txt = re.sub(r"\s+", " ", page.inner_text("body"))
    detail: dict[str, Any] = {"detail_url": url}
    for field, pattern in DETAIL_FIELDS:
        m = re.search(pattern, txt, re.I)
        if m and m.group(1).strip():
            detail[field] = m.group(1).strip()[:600]
    if not rec.get("permit_number"):
        m = re.search(r"Record ([A-Z0-9\-]{4,30}):", txt) or re.search(r"Permit ([A-Z0-9\-]{4,30}):", txt)
        if m:
            rec["permit_number"] = m.group(1)
    return detail


def list_attachments(page, tenant: dict[str, Any], rec: dict[str, Any], sleep: float) -> list[dict[str, Any]]:
    """MUST be called immediately after scrape_detail() on the same page --
    this URL carries no capID and binds to the session's last-viewed record."""
    url = ATT_URL.format(base=tenant["base_url"], mod=tenant["module"], ag=rec["agency_code"])
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(int(sleep * 1000) + 1500)
    if page.locator("table[id*='gdvAttachmentList']").count() == 0:
        return []
    raw = page.eval_on_selector_all(
        "a[href*='lnkFileName']",
        "as => as.map(a => ({href: a.getAttribute('href'), name: a.innerText.trim(),"
        " cells: a.closest('tr') ? Array.from(a.closest('tr').querySelectorAll('td'))"
        ".map(td => td.innerText.trim()) : []}))",
    )
    docs = []
    for item in raw:
        href = item.get("href") or ""
        m = re.search(r"__doPostBack\(&#39;([^&]+?)&#39;|__doPostBack\('([^']+)'", href)
        target = (m.group(1) or m.group(2)) if m else ""
        cells = item.get("cells") or []
        size = next((parse_size(c) for c in cells if parse_size(c)), None)
        docs.append(
            {
                "filename": item.get("name") or "",
                "postback_target": target,
                "size_hint": size,
                "row_cells": cells[:8],
            }
        )
    return [d for d in docs if d["filename"]]


def should_skip(doc: dict[str, Any]) -> bool:
    hay = f"{doc['filename']} {' '.join(doc.get('row_cells') or [])}".lower()
    return any(h in hay for h in SKIP_NAME_HINTS)


def gcs_bucket(mode: str):
    if mode == "adc":
        # Same credential note as fetch-snohomish-documents.py: the step-8
        # service account has Cloud SQL + Vertex but 403s on
        # storage.objects.create for this bucket; dropping the env var falls
        # back to the gcloud user ADC, which does have access.
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    from google.cloud import storage

    return storage.Client(project="specindex-ai").bucket(GCS_BUCKET)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant", default="ALL", help="config key (e.g. OK-OKLAHOMA), comma list, or ALL")
    ap.add_argument("--limit", type=int, default=0, help="cap records processed per tenant, 0 = no cap")
    ap.add_argument("--offset", type=int, default=0, help="skip this many records first (resume)")
    ap.add_argument("--max-docs-per-project", type=int, default=4)
    ap.add_argument("--max-bytes-per-doc", type=int, default=25 * 1024 * 1024)
    ap.add_argument("--lookback-days", type=int, default=(date.today() - date(2025, 1, 1)).days,
                    help="only used by tenants with use_date_range=True; defaults to the standing 2025-01-01 anchor")
    ap.add_argument("--max-pages", type=int, default=15, help="results pages to harvest (ACA throttles ~40-60)")
    ap.add_argument("--sleep", type=float, default=1.0, help="politeness delay between requests, seconds")
    ap.add_argument(
        "--workers",
        type=int,
        default=3,
        help=(
            "records processed concurrently, each with its OWN browser context "
            "(default 3). MEASURED 2026-08-03 -- do not raise blindly: at 8 "
            "workers the uplink saturated and produced 0 uploads plus 'No route "
            "to host' (OSError 65); at 3 it ran clean. Parallelism is across "
            "PROJECTS -- never within a project, because the AttachmentsList "
            "URL binds to the session's last-viewed record."
        ),
    )
    ap.add_argument("--records-per-session", type=int, default=40,
                    help="recycle each worker's browser context after this many records (ACA throttles long anon sessions)")
    ap.add_argument("--max-consecutive-errors", type=int, default=8)
    ap.add_argument("--credentials", choices=["adc", "env"], default="adc")
    ap.add_argument("--manifest-dir", default=str(ROOT / "data" / "documents"),
                    help="manifests are written to {dir}/{source}/manifest.json")
    ap.add_argument("--headed", action="store_true", help="run the browser headed (debugging)")
    ap.add_argument("--dry-run", action="store_true", help="enumerate records + attachments, download/upload nothing")
    args = ap.parse_args(argv)

    keys = list(TENANTS) if args.tenant.upper() == "ALL" else [k.strip().upper() for k in args.tenant.split(",")]
    unknown = [k for k in keys if k not in TENANTS]
    if unknown:
        print(f"unknown tenant(s): {unknown}; known: {list(TENANTS)}", file=sys.stderr)
        return 2

    bucket = None if args.dry_run else gcs_bucket(args.credentials)
    overall: dict[str, Any] = {}
    for key in keys:
        overall[key] = run_tenant(key, TENANTS[key], args, bucket)
    print(json.dumps(overall, indent=2))
    return 0


def run_tenant(key: str, tenant: dict[str, Any], args, bucket) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    source = f"accela-{key.lower()}"
    manifest_path = Path(args.manifest_dir) / source / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    by_project: dict[str, Any] = manifest.get("by_project", {})

    summary = {
        "tenant": key,
        "agency_code": "",
        "records_harvested": 0,
        "records_attempted": 0,
        "records_with_docs": 0,
        "docs_found": 0,
        "docs_selected": 0,
        "docs_uploaded": 0,
        "docs_skipped_existing": 0,
        "docs_skipped_trivia": 0,
        "docs_skipped_cap": 0,
        "docs_skipped_too_large": 0,
        "errors": 0,
        "bytes_uploaded": 0,
    }
    print(f"\n=== {key} ({tenant['base_url']}, module={tenant['module']}) ===", file=sys.stderr)

    # Phase 1 -- a single session harvests the record list.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(user_agent=USER_AGENT, accept_downloads=True)
        page = ctx.new_page()
        try:
            records = harvest_records(
                page, tenant, lookback_days=args.lookback_days, max_pages=args.max_pages, sleep=args.sleep
            )
        except Exception as e:  # noqa: BLE001
            print(f"  [error] harvest failed: {type(e).__name__}: {str(e)[:160]}", file=sys.stderr)
            records = []
        finally:
            browser.close()

    summary["records_harvested"] = len(records)
    if records:
        summary["agency_code"] = records[0]["agency_code"]
    records = records[args.offset:]
    if args.limit:
        records = records[: args.limit]
    print(f"  processing {len(records)} record(s) (offset={args.offset}, limit={args.limit})", file=sys.stderr)
    if not records:
        return summary

    lock = threading.Lock()
    abort = threading.Event()
    consecutive = {"n": 0}

    def bump_error(fatal_class: bool = True) -> None:
        with lock:
            summary["errors"] += 1
            if fatal_class:
                consecutive["n"] += 1
                if consecutive["n"] >= args.max_consecutive_errors:
                    print("  [abort] too many consecutive errors -- stopping early", file=sys.stderr)
                    abort.set()

    def write_manifest() -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "source": f"{tenant['county']} County {tenant['state_code']} -- Accela Citizen Access ({key})",
                    "endpoint": tenant["base_url"],
                    "module": tenant["module"],
                    "permit_type_label": tenant.get("permit_type_label"),
                    "gcs_prefix": f"gs://{GCS_BUCKET}/{tenant['state_dir']}/",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "by_project": by_project,
                },
                indent=2,
            )
            + "\n"
        )

    def process(page, rec: dict[str, Any]) -> None:
        with lock:
            summary["records_attempted"] += 1
        try:
            detail = scrape_detail(page, tenant, rec, args.sleep)
            docs = list_attachments(page, tenant, rec, args.sleep)
            with lock:
                consecutive["n"] = 0
        except Exception as e:  # noqa: BLE001
            print(f"  [error] {rec.get('permit_number') or rec['capID3']}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            bump_error()
            return
        with lock:
            summary["docs_found"] += len(docs)
        if not docs:
            return

        permit = rec.get("permit_number") or f"{rec['capID1']}-{rec['capID2']}-{rec['capID3']}"
        pid = project_id_for(tenant, permit)

        selected = [d for d in docs if not should_skip(d)]
        with lock:
            summary["docs_skipped_trivia"] += len(docs) - len(selected)
        oversized = [d for d in selected if (d.get("size_hint") or 0) > args.max_bytes_per_doc]
        if oversized:
            with lock:
                summary["docs_skipped_too_large"] += len(oversized)
            selected = [d for d in selected if d not in oversized]
        if args.max_docs_per_project and len(selected) > args.max_docs_per_project:
            with lock:
                summary["docs_skipped_cap"] += len(selected) - args.max_docs_per_project
            selected = selected[: args.max_docs_per_project]
        with lock:
            summary["docs_selected"] += len(selected)

        print(f"  {pid} ({permit}): {len(docs)} attachment(s), {len(selected)} selected", file=sys.stderr)
        if args.dry_run:
            for d in selected:
                print(f"    - {d['filename']} ({d.get('size_hint') or 0:,} B hint)", file=sys.stderr)
            return

        with lock:
            entry = by_project.setdefault(pid, {"permit_number": permit, "documents": []})
            entry.update({k: v for k, v in detail.items() if v})
            entry["county"] = tenant["county"]
            entry["state"] = tenant["state_code"]
            entry["permit_date"] = rec.get("row_date") or entry.get("permit_date")
            have = {doc["filename"] for doc in entry["documents"]}

        captured = False
        for d in selected:
            if abort.is_set():
                return
            fname = safe_name(d["filename"])
            if fname in have:
                with lock:
                    summary["docs_skipped_existing"] += 1
                captured = True
                continue
            blob_path = f"{tenant['state_dir']}/{pid}/{fname}"
            blob = bucket.blob(blob_path)
            if blob.exists():
                with lock:
                    summary["docs_skipped_existing"] += 1
                captured = True
                continue

            started = time.monotonic()
            tmp_path = None
            try:
                with page.expect_download(timeout=180000) as di:
                    page.evaluate(f"__doPostBack({json.dumps(d['postback_target'])}, '')")
                dl = di.value
                fd, tmp_path = tempfile.mkstemp(prefix="accela-doc-")
                os.close(fd)
                dl.save_as(tmp_path)
                payload = Path(tmp_path).read_bytes()
            except Exception as e:  # noqa: BLE001
                print(f"    [error] download failed for {fname}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
                bump_error()
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                # Attachment postbacks are session-scoped: after a failure the
                # page may have navigated, so re-bind before the next doc.
                try:
                    list_attachments(page, tenant, rec, args.sleep)
                except Exception:  # noqa: BLE001
                    return
                continue
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            with lock:
                consecutive["n"] = 0
            if not payload:
                with lock:
                    summary["errors"] += 1
                continue
            if len(payload) > args.max_bytes_per_doc:
                with lock:
                    summary["docs_skipped_too_large"] += 1
                print(f"    [skip] too large ({len(payload):,} B): {fname}", file=sys.stderr)
                continue

            ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            try:
                blob.chunk_size = 8 * 1024 * 1024
                blob.upload_from_string(payload, content_type=ctype, timeout=600)
            except Exception as e:  # noqa: BLE001 -- an upload failure must not kill the run
                with lock:
                    summary["errors"] += 1
                print(f"    [error] upload failed for {fname}: {str(e)[:120]}", file=sys.stderr)
                continue

            digest = hashlib.sha256(payload).hexdigest()
            captured = True
            with lock:
                summary["docs_uploaded"] += 1
                summary["bytes_uploaded"] += len(payload)
                entry["documents"].append(
                    {
                        "filename": fname,
                        "title": d["filename"],
                        "url": f"https://storage.googleapis.com/{GCS_BUCKET}/{urllib.parse.quote(blob_path)}",
                        "gcs_path": blob_path,
                        "content_type": ctype,
                        "size_bytes": len(payload),
                        "content_sha256": digest,
                        "source_permit": permit,
                    }
                )
            print(f"    [uploaded] {blob_path} ({len(payload):,} B, {time.monotonic() - started:.1f}s)", file=sys.stderr)
            time.sleep(args.sleep)
            # Re-bind the session to this record's attachment list before the
            # next postback -- the download navigation can drop the binding.
            try:
                list_attachments(page, tenant, rec, args.sleep)
            except Exception:  # noqa: BLE001
                break

        if captured:
            with lock:
                summary["records_with_docs"] += 1
        with lock:
            write_manifest()

    def worker(shard: list[dict[str, Any]]) -> None:
        """One browser per worker, recycled every --records-per-session
        records. Playwright's sync API is not thread-safe across threads, so
        each worker starts its own sync_playwright()."""
        if not shard:
            return
        def warm(page) -> None:
            """A brand-new context that jumps straight to CapDetail gets an
            EMPTY AttachmentsList -- verified live 2026-08-03 on ACFW: 9
            records harvested, 0 attachments found, where the same records
            yielded 5/5 when the session had been through CapHome first.
            The module context has to be established on the session before
            the capID-less AttachmentsList URL will resolve."""
            page.goto(
                f"{tenant['base_url']}/Cap/CapHome.aspx?module={tenant['module']}",
                timeout=60000,
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(1500)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            ctx = browser.new_context(user_agent=USER_AGENT, accept_downloads=True)
            page = ctx.new_page()
            warm(page)
            done = 0
            try:
                for rec in shard:
                    if abort.is_set():
                        break
                    if done and done % args.records_per_session == 0:
                        page.close()
                        ctx.close()
                        ctx = browser.new_context(user_agent=USER_AGENT, accept_downloads=True)
                        page = ctx.new_page()
                        warm(page)
                        print("  [session] recycled browser context", file=sys.stderr)
                    process(page, rec)
                    done += 1
                    time.sleep(args.sleep)
            finally:
                browser.close()

    workers = max(1, args.workers)
    shards = [records[i::workers] for i in range(workers)]
    if workers == 1:
        worker(shards[0])
    else:
        threads = [threading.Thread(target=worker, args=(s,), daemon=True) for s in shards]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    if not args.dry_run:
        write_manifest()
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
