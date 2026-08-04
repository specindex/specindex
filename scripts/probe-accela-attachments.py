#!/usr/bin/env python3
"""Does this Accela tenant actually SERVE documents? One record is enough to know.

Why this exists (2026-08-04): 62 Accela configs are wired for permits, but only
8 have ever been tested for documents. The other 54 -- 42 distinct tenants --
have been pulling permit metadata for months while nobody checked whether their
records expose downloadable attachments. That is the cheapest remaining source
of document depth: no discovery needed, the tenants are already proven live.

It also settles the distinction that cost a day of effort on Los Angeles:
**"doc-capable provider" is NOT "doc-bearing tenant"**. LA has 7 doc-capable
configs and returned zero attachments across 148 harvested records. Provider
type predicts nothing; only opening a real record does.

Method mirrors fetch-accela-documents.py's proven three-step session, because a
context that jumps straight to CapDetail gets an EMPTY AttachmentsList
regardless of what the record holds (verified live 2026-08-03 on ACFW):

  1. CapHome.aspx?module=M   -- establishes the session AND harvests agencyCode
  2. search, open the first record's CapDetail
  3. AttachmentsList.aspx    -- read the attachment table

Reports per tenant: whether the search returned records, whether the first few
records list attachments, and what those attachments look like. It downloads
nothing -- this answers "is there anything here", and capture is a separate,
much slower job that should only run against tenants this says yes to.

Usage:
    python3 scripts/probe-accela-attachments.py --all-untested
    python3 scripts/probe-accela-attachments.py --state-key FL-PINELLAS --records 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "state_agent_pipeline"))

ATTACH_URL = (
    "{base}/FileUpload/AttachmentsList.aspx?iframeid=ctl00_PlaceHolderMain_attachmentEdit"
    "&module={mod}&isInConfirm=False&isdetail=True&isaccountmanager=False&isAdmin=False"
    "&agencyCode={agency}&isForConditionDocument=N"
)


def untested_tenants() -> list[dict]:
    """One entry per distinct tenant that has no document-registry entry."""
    from core.state_configs import STATE_CONFIGS  # noqa: PLC0415

    registered = set(re.findall(
        r'"([A-Z]{2}-[A-Z0-9-]+)":\s*\{',
        (ROOT / "scripts" / "fetch-accela-documents.py").read_text()))
    by_endpoint: dict[str, dict] = {}
    for key, cfg in STATE_CONFIGS.items():
        if cfg.get("provider_type") != "accela" or key in registered:
            continue
        ep = cfg["endpoint"]
        # Several configs share one tenant via permit-type splits; probing the
        # tenant once is enough, so keep the first and remember the rest.
        if ep in by_endpoint:
            by_endpoint[ep]["also"].append(key)
            continue
        by_endpoint[ep] = {
            "key": key, "base_url": ep, "county": cfg.get("county"),
            "state": cfg.get("state_code"),
            "module": cfg.get("module") or "Building",
            "permit_type_label": cfg.get("permit_type_label", "Building"),
            "also": [],
        }
    return list(by_endpoint.values())


def probe(tenant: dict, records: int, timeout_ms: int) -> dict:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    base, mod = tenant["base_url"].rstrip("/"), tenant["module"]
    out = {**{k: tenant[k] for k in ("key", "county", "state", "base_url")},
           "records_seen": 0, "records_with_attachments": 0,
           "attachment_names": [], "note": ""}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 SpecIndex-DocFeasibility/0.1")
        try:
            page.goto(f"{base}/Cap/CapHome.aspx?module={mod}",
                      timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # agencyCode is not guessable from the URL on self-hosted tenants
            # -- harvest it from a row href, exactly as the capture script does.
            html = page.content()
            m = re.search(r"agencyCode=([A-Za-z0-9_]+)", html)
            agency = m.group(1) if m else base.rstrip("/").rsplit("/", 1)[-1]

            sel = "#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType"
            if page.locator(sel).count():
                try:
                    page.select_option(sel, label=tenant["permit_type_label"], timeout=8000)
                except Exception:  # noqa: BLE001 - fall back to whatever is selected
                    pass
            page.click("#ctl00_PlaceHolderMain_btnNewSearch", timeout=25000)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2500)

            links = page.locator("a[href*='CapDetail.aspx']")
            n = links.count()
            out["records_seen"] = n
            if n == 0:
                out["note"] = "search returned no records with a detail link"
                return out

            for i in range(min(records, n)):
                try:
                    # Re-run from the results grid each time; going back is more
                    # reliable than holding stale locators across postbacks.
                    if i:
                        page.go_back(timeout=20000)
                        page.wait_for_timeout(2000)
                    page.locator("a[href*='CapDetail.aspx']").nth(i).click(timeout=20000)
                    page.wait_for_timeout(3000)
                    page.goto(ATTACH_URL.format(base=base, mod=mod, agency=agency),
                              timeout=timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    body = page.inner_text("body")
                    names = re.findall(r"([\w\-. ()]+\.(?:pdf|dwg|docx?|xlsx?|jpg|png|tif))",
                                       body, re.I)
                    if names:
                        out["records_with_attachments"] += 1
                        out["attachment_names"].extend(names[:4])
                except Exception as e:  # noqa: BLE001
                    out["note"] = f"{type(e).__name__} on record {i}"
                    break
        except Exception as e:  # noqa: BLE001
            out["note"] = f"{type(e).__name__}: {str(e)[:60]}"
        finally:
            browser.close()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all-untested", action="store_true",
                    help="Probe every Accela tenant with no document-registry entry.")
    ap.add_argument("--state-key", action="append", default=[])
    ap.add_argument("--records", type=int, default=2,
                    help="Records to open per tenant (default 2). One is usually "
                         "enough to tell yes from no; two guards against a record "
                         "that legitimately has none.")
    ap.add_argument("--timeout-ms", type=int, default=45000)
    ap.add_argument("--json", help="Write full results here.")
    args = ap.parse_args(argv)

    if args.all_untested:
        tenants = untested_tenants()
    else:
        from core.state_configs import STATE_CONFIGS  # noqa: PLC0415
        tenants = [{
            "key": k, "base_url": STATE_CONFIGS[k]["endpoint"],
            "county": STATE_CONFIGS[k].get("county"),
            "state": STATE_CONFIGS[k].get("state_code"),
            "module": STATE_CONFIGS[k].get("module") or "Building",
            "permit_type_label": STATE_CONFIGS[k].get("permit_type_label", "Building"),
            "also": [],
        } for k in args.state_key]
    if not tenants:
        ap.error("pass --all-untested or --state-key")

    print(f"probing {len(tenants)} tenants, {args.records} record(s) each\n", flush=True)
    results = []
    # Serial on purpose: each probe drives a browser, and concurrent Chromium
    # instances failed to launch at all under load earlier today.
    for i, t in enumerate(tenants, 1):
        r = probe(t, args.records, args.timeout_ms)
        results.append(r)
        verdict = ("DOCS" if r["records_with_attachments"] else
                   ("no-docs" if r["records_seen"] else "no-records"))
        print(f"  [{i}/{len(tenants)}] {(r['county'] or '?')+', '+(r['state'] or '?'):<24}"
              f"{r['key']:<26}seen={r['records_seen']:<4}with_docs="
              f"{r['records_with_attachments']}  {verdict}"
              + (f"  [{r['note']}]" if r["note"] else ""), flush=True)
        if r["attachment_names"]:
            print(f"        e.g. {r['attachment_names'][:3]}", flush=True)

    hits = [r for r in results if r["records_with_attachments"]]
    print(f"\n{'='*72}\ntenants probed: {len(results)}   SERVING DOCUMENTS: {len(hits)}")
    for r in hits:
        print(f"   {r['county']}, {r['state']}  ({r['key']})  {r['base_url']}")
    print("\nA 'no-docs' verdict on 2 records is suggestive, not proof -- some "
          "record types\ncarry attachments and others do not. A 'DOCS' verdict is "
          "actionable now: add the\ntenant to fetch-accela-documents.py and capture.")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
