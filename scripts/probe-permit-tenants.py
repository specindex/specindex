#!/usr/bin/env python3
"""Probe candidate Accela / EnerGov tenants for a county, and report what's usable.

Why this exists (2026-08-04): this is the method that found San Bernardino
County's own Accela tenant (SBCO) after it had sat at ONE project with no
health-matrix entry at all. Catalog search (Socrata/ArcGIS Online) does not
find these -- permit portals are not open-data datasets -- and guessing
hostnames does not work either. What works is trying plausible AGENCY CODES
against the known multitenant host and reading the live search form.

It serves breadth and documents at once, which is the point: Accela and
EnerGov are the only source classes that have ever yielded construction
documents, so a tenant found here is simultaneously a coverage win and a
document candidate. Bulk feeds (Socrata/ArcGIS/CSV) can never be, having no
per-record attachment endpoint.

What counts as a usable tenant, checked live rather than assumed:
  * the ACA general-search form exists (#...ddlGSPermitType present)
  * it offers a genuinely COMMERCIAL permit type, not just "Building"
  * it exposes the standard date-range inputs -- without them the search runs
    unfiltered over the tenant's whole history (see CLAUDE.md, Accela section)

Hit rate is low by nature -- 1 of 18 guessed codes hit in one earlier run --
so this is deliberately cheap per attempt and heavily parallel. A miss is not
evidence the county has no portal, only that the guessed code was wrong.

Usage:
    python3 scripts/probe-permit-tenants.py --county "Alameda,CA" --county "Fresno,CA"
    python3 scripts/probe-permit-tenants.py --from-json /tmp/targets.json --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
ACA_HOST = "https://aca-prod.accela.com"
COMMERCIAL = re.compile(r"commercial|non-?residential|tenant improve|industrial", re.I)


def candidate_codes(county: str, cities: list[str]) -> list[str]:
    """Agency codes worth trying for a county.

    Both the COUNTY and its cities matter: San Bernardino's win was the county
    code (SBCO) while its city codes were useless, and Hidalgo's only win was a
    city (PHARR). Codes are uppercase, unspaced, sometimes abbreviated.
    """
    base = [county] + cities
    out: list[str] = []
    for name in base:
        n = re.sub(r"[^A-Za-z]", "", name).upper()
        if not n:
            continue
        out += [n, n + "CO", n + "COUNTY"]
        if len(n) > 6:
            out.append(n[:6])
    seen: dict[str, None] = {}
    for c in out:
        seen.setdefault(c, None)
    return list(seen)


def fetch(url: str, timeout: int = 15) -> tuple[int, str]:
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        return r.status, r.read(120_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def probe_accela(code: str) -> dict | None:
    """Is there a real ACA tenant at this agency code?"""
    status, body = fetch(f"{ACA_HOST}/{code}/Cap/CapHome.aspx?module=Building", 18)
    if status != 200 or not ("Accela" in body or "ACA_" in body or "PlaceHolderMain" in body):
        return None
    return {
        "kind": "accela", "code": code, "url": f"{ACA_HOST}/{code}",
        # These two decide whether the tenant is actually usable; both are read
        # off the live form by the caller, not inferred from the code existing.
        "has_permit_type_select": "ddlGSPermitType" in body,
        "has_date_fields": "txtGSStartDate" in body and "txtGSEndDate" in body,
    }


def probe_energov(sub: str) -> dict | None:
    for host in (f"{sub}-energovweb.tylerhost.net", f"{sub}-energovpub.tylerhost.net"):
        status, _ = fetch(f"https://{host}/apps/selfservice/#/home", 15)
        if status == 200:
            return {"kind": "energov", "code": sub, "url": f"https://{host}"}
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--county", action="append", default=[], help='"County,ST" (repeatable)')
    ap.add_argument("--from-json", help="JSON list of {county,state} to probe.")
    ap.add_argument("--cities", action="append", default=[],
                    help="Extra city names to try, applies to all counties.")
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--json", help="Write hits here.")
    args = ap.parse_args(argv)

    targets: list[tuple[str, str]] = []
    for c in args.county:
        cty, _, st = c.rpartition(",")
        targets.append((cty.strip(), st.strip().upper()))
    if args.from_json:
        for row in json.loads(Path(args.from_json).read_text()):
            targets.append((row["county"], row["state"]))
    if not targets:
        ap.error("pass --county or --from-json")

    jobs: list[tuple[str, str, str, str]] = []
    for cty, st in targets:
        for code in candidate_codes(cty, args.cities):
            jobs.append((cty, st, "accela", code))
            jobs.append((cty, st, "energov", code.lower()))
    print(f"probing {len(jobs)} candidates across {len(targets)} counties "
          f"({args.workers} workers)\n", flush=True)

    hits: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {}
        for cty, st, kind, code in jobs:
            fn = probe_accela if kind == "accela" else probe_energov
            futs[pool.submit(fn, code)] = (cty, st)
        for f in as_completed(futs):
            cty, st = futs[f]
            try:
                r = f.result()
            except Exception:  # noqa: BLE001
                continue
            if not r:
                continue
            r["county"], r["state"] = cty, st
            hits.append(r)
            usable = r.get("has_permit_type_select") and r.get("has_date_fields")
            flag = "USABLE" if usable else "needs-check"
            print(f"  HIT {cty+', '+st:<24}{r['kind']:<9}{r['code']:<18}{flag}", flush=True)

    print(f"\n{'='*70}\ncounties probed: {len(targets)}   tenants found: {len(hits)}")
    usable = [h for h in hits if h.get("has_permit_type_select") and h.get("has_date_fields")]
    print(f"immediately usable (permit-type select + date fields): {len(usable)}")
    print("\nEvery hit still needs its permit-type list read live before wiring -- a\n"
          "tenant can expose the form and still offer no commercial type (Fontana),\n"
          "and a missing date field means the search runs unfiltered.")
    if args.json:
        Path(args.json).write_text(json.dumps(hits, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
