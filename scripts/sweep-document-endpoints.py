#!/usr/bin/env python3
"""Find document repositories for a jurisdiction by rule, not by luck.

Why this exists (2026-08-03): Snohomish WA's OpenText document repository -- the
single highest-yield source found so far (12-213 documents per project, median
~40) -- was invisible from its permit feed and was found by accident. Yield per
source class is wildly asymmetric: an EDMS-class county is ~16,000 documents
where an ungated-Accela county is ~1,200. So finding EDMS repositories is the
highest-leverage capability we have, and it must be systematic.

Two independent probes, both read-only:

  1. **ArcGIS service-directory walk.** Enumerate /arcgis/rest/services, recurse
     folders, and inspect each layer's field list for names matching
     url|link|doc|pdf|attach|plan|permit_no. A layer carrying a document URL
     field is a direct path to files. This is the method that actually worked
     (it surfaced Fairfax VA's 151,956-record archive); EDMS path-guessing alone
     did not. Also reports layers with attachments enabled (hasAttachments),
     which is a first-class document path via the /queryAttachments endpoint.

  2. **EDMS path fingerprint.** Probe the well-known mount points for the five
     EDMS products that dominate US local government -- Laserfiche WebLink,
     Hyland OnBase, OpenText Content Server, NextRequest, JustFOIA -- against a
     jurisdiction's domain. Signatures are in
     docs/DOCUMENT_STRATEGY_REVIEW_2026-08-03.md.

Probes are small independent HTTP requests against different hosts, so they run
at high concurrency (default 16). This is the regime where parallelism is a pure
win -- unlike large file transfers, which saturate the ~150-250 KB/s uplink at
about 3 concurrent streams. Do not reuse this worker count for capture.

This script only ever REPORTS. It downloads nothing and writes no config. Every
hit must be verified by hand before wiring, and a well-evidenced negative is a
valid, useful result -- record it rather than leaving a county unexplained.

Usage:
    python3 scripts/sweep-document-endpoints.py --from-configs --top 34
    python3 scripts/sweep-document-endpoints.py --host gis.hctx.net --host www.miamidade.gov
    python3 scripts/sweep-document-endpoints.py --from-configs --json sweep.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "state_agent_pipeline"))

UA = {"User-Agent": "SpecIndex-DocumentSweep/1.0 (+construction data research)"}

# Field names that indicate a layer carries a pointer to an actual document.
# Split by strength, because a broad single regex drowns real leads in noise: a
# first pass matching /url|plan|record|file/ returned 97 "hits" for Harris TX
# that were almost entirely Commissioner-Precinct boundary layers with a
# generic URL field, and one bare `CA_FILE` column on a law-enforcement layer.
#
# STRONG fields name a document outright and count on their own. WEAK fields
# (a bare `URL`) only count when the LAYER is construction-relevant -- a URL on
# a permit layer is a lead, the same URL on a voting-precinct layer is not.
DOC_FIELD_STRONG_RE = re.compile(
    r"(pdf|attach|document|docurl|doc_url|scan|plan_?url|plan_?set|drawing|exhibit|"
    r"permit_?url|case_?url|weblink|laserfiche|onbase)", re.IGNORECASE
)
DOC_FIELD_WEAK_RE = re.compile(r"(^url$|_url$|url_|link|image|file)", re.IGNORECASE)

# Layer names that put a jurisdiction's construction/permitting data in scope.
RELEVANT_LAYER_RE = re.compile(
    r"(permit|building|construction|development|project|site.?plan|land.?use|"
    r"zoning|subdivision|inspection|certificate.?of.?occupancy|plat|case)",
    re.IGNORECASE,
)

# Well-known EDMS mount points. Each entry: (path, product, signature regex that
# must appear in the response body for the hit to count as real -- a 200 alone
# proves nothing, since many portals serve a soft-404 landing page).
EDMS_PROBES = [
    ("/weblink/", "Laserfiche WebLink", r"laserfiche|weblink"),
    ("/WebLink/Browse.aspx", "Laserfiche WebLink", r"laserfiche|weblink"),
    ("/onbase/", "Hyland OnBase", r"onbase|hyland"),
    ("/AppNet/Login.aspx", "Hyland OnBase", r"onbase|hyland|appnet"),
    ("/docpop/docpop.aspx", "Hyland Application Enabler", r"docpop|hyland"),
    ("/otcs/llisapi.dll", "OpenText Content Server", r"opentext|livelink|otcs"),
    ("/Livelink/livelink.exe", "OpenText Livelink", r"opentext|livelink"),
    ("/publicrecords/", "public records portal", r"records|foia|request"),
    ("/nextrequest", "NextRequest", r"nextrequest"),
    ("/justfoia", "JustFOIA", r"justfoia"),
]

ARCGIS_ROOTS = ("/arcgis/rest/services", "/server/rest/services", "/rest/services")


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    """GET a URL, returning (status, body). Never raises -- a failed probe is data."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001 - report, never abort the sweep
        return 0, f"{type(e).__name__}: {str(e)[:60]}"


def soft_404_baseline(host: str) -> tuple[int, str]:
    """Fetch a path that cannot exist, to learn what this host's 404 looks like.

    Municipal sites overwhelmingly answer unknown paths with HTTP 200 and their
    normal landing page. Without this baseline, EVERY probe "succeeds": a sweep
    of 14 counties on 2026-08-04 returned 17 EDMS "hits" across San Diego,
    Tarrant and Wayne, and all 17 were the same landing page -- byte-identical
    to a nonsense URL. The real result was zero.
    """
    return fetch(f"https://{host}/zzzz-specindex-nonexistent-path-9f3a1/", timeout=12)


def probe_edms(host: str) -> list[dict]:
    """Probe a host's well-known EDMS mount points.

    Three conditions must ALL hold for a hit, because any one alone lies:
      1. HTTP 200 -- necessary, nowhere near sufficient.
      2. The body carries the product's own signature (laserfiche, onbase...).
      3. The body DIFFERS from this host's soft-404 baseline. A generic
         signature like /document/ matches nearly every government page, so
         without the baseline the weaker probes fire on everything.
    """
    out = []
    base_status, base_body = soft_404_baseline(host)
    base_len = len(base_body)
    for path, product, sig in EDMS_PROBES:
        url = f"https://{host}{path}"
        status, body = fetch(url, timeout=12)
        if status != 200 or not re.search(sig, body, re.IGNORECASE):
            continue
        # Same length as the soft-404 is the giveaway -- these sites serve the
        # identical landing page. Allow a small delta for per-request nonces
        # and timestamps rather than requiring an exact match.
        if base_status == 200 and abs(len(body) - base_len) < 64:
            continue
        out.append({"kind": "edms", "host": host, "url": url,
                    "product": product, "status": status})
    return out


def walk_arcgis(host: str, max_folders: int = 25, max_services: int = 120) -> list[dict]:
    """Enumerate an ArcGIS REST directory and flag layers with document fields.

    Bounded deliberately: some county servers publish thousands of services and
    an unbounded walk would take longer than it is worth. Folders and services
    are capped; raise the caps for a host that looks promising.
    """
    hits: list[dict] = []
    root = None
    for r in ARCGIS_ROOTS:
        status, body = fetch(f"https://{host}{r}?f=json", timeout=15)
        if status == 200 and '"services"' in body:
            root = f"https://{host}{r}"
            break
    if not root:
        return hits

    try:
        top = json.loads(fetch(f"{root}?f=json")[1])
    except Exception:  # noqa: BLE001
        return hits

    services = list(top.get("services") or [])
    for folder in (top.get("folders") or [])[:max_folders]:
        status, body = fetch(f"{root}/{folder}?f=json", timeout=15)
        if status != 200:
            continue
        try:
            services.extend(json.loads(body).get("services") or [])
        except Exception:  # noqa: BLE001
            continue

    services = [s for s in services if s.get("type") in ("MapServer", "FeatureServer")][:max_services]

    def inspect(svc: dict) -> list[dict]:
        name, typ = svc.get("name"), svc.get("type")
        status, body = fetch(f"{root}/{name}/{typ}?f=json", timeout=15)
        if status != 200:
            return []
        found = []
        try:
            layers = json.loads(body).get("layers") or []
        except Exception:  # noqa: BLE001
            return []
        for lyr in layers[:30]:
            lid = lyr.get("id")
            st2, b2 = fetch(f"{root}/{name}/{typ}/{lid}?f=json", timeout=15)
            if st2 != 200:
                continue
            try:
                meta = json.loads(b2)
            except Exception:  # noqa: BLE001
                continue
            lname = meta.get("name") or ""
            relevant = bool(RELEVANT_LAYER_RE.search(lname))
            names = [f.get("name") for f in (meta.get("fields") or []) if f.get("name")]
            strong = [n for n in names if DOC_FIELD_STRONG_RE.search(n)]
            weak = [n for n in names if DOC_FIELD_WEAK_RE.search(n) and n not in strong]
            has_attach = bool(meta.get("hasAttachments"))

            # Score so the report can lead with real leads. Attachments on a
            # construction layer is the strongest signal available short of
            # downloading a file; a weak URL field on an irrelevant layer is
            # dropped entirely rather than reported as a hit.
            score = 0
            if has_attach:
                score += 3
            if strong:
                score += 3
            if relevant:
                score += 2
            if weak and relevant:
                score += 1
            if score < 3:
                continue
            found.append({
                "kind": "arcgis-layer", "host": host,
                "url": f"{root}/{name}/{typ}/{lid}",
                "layer_name": lname,
                "doc_fields": (strong + weak)[:8],
                "has_attachments": has_attach,
                "construction_relevant": relevant,
                "score": score,
            })
        return found

    with ThreadPoolExecutor(max_workers=8) as pool:
        for fut in as_completed([pool.submit(inspect, s) for s in services]):
            hits.extend(fut.result())
    return hits


def hosts_from_configs(top: int) -> list[str]:
    """Harvest real hostnames already proven to serve a jurisdiction.

    Starting from endpoints we know work beats guessing hostnames: these are
    confirmed-live hosts, and an EDMS is very often mounted on the same domain
    as the GIS or permit portal.
    """
    from core.state_configs import STATE_CONFIGS  # noqa: PLC0415

    seen: dict[str, None] = {}
    for cfg in STATE_CONFIGS.values():
        ep = str(cfg.get("endpoint") or "")
        if not ep.startswith("http"):
            continue
        host = urllib.parse.urlparse(ep).netloc
        # Esri-hosted multitenant domains never carry a county's own EDMS.
        if re.match(r"^services\d*\.arcgis\.com$", host) or host.endswith("accela.com"):
            continue
        seen.setdefault(host, None)
    return list(seen)[: top * 4]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", action="append", default=[], help="Explicit host to sweep.")
    ap.add_argument("--from-configs", action="store_true",
                    help="Harvest hosts from STATE_CONFIGS endpoints.")
    ap.add_argument("--top", type=int, default=34, help="Scale the harvest (default 34).")
    ap.add_argument("--workers", type=int, default=16,
                    help="Concurrent probes (default 16). Probes are small and independent; "
                         "do NOT reuse this for file transfers, which saturate uplink at ~3.")
    ap.add_argument("--skip-arcgis", action="store_true", help="EDMS path probes only.")
    ap.add_argument("--json", help="Write full results to this path.")
    args = ap.parse_args(argv)

    hosts = list(args.host)
    if args.from_configs:
        hosts.extend(h for h in hosts_from_configs(args.top) if h not in hosts)
    if not hosts:
        ap.error("no hosts: pass --host or --from-configs")

    print(f"Sweeping {len(hosts)} hosts with {args.workers} workers "
          f"(EDMS probes{'' if args.skip_arcgis else ' + ArcGIS walk'})\n", flush=True)

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {}
        for h in hosts:
            futs[pool.submit(probe_edms, h)] = ("edms", h)
            if not args.skip_arcgis:
                futs[pool.submit(walk_arcgis, h)] = ("arcgis", h)
        for fut in as_completed(futs):
            kind, h = futs[fut]
            try:
                found = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  {h:<40} {kind} FAILED {type(e).__name__}", flush=True)
                continue
            if found:
                for f in found:
                    if f["kind"] == "edms":
                        print(f"  EDMS {h:<38} {f['product']}  {f['url']}", flush=True)
                results.extend(found)

    edms = [r for r in results if r["kind"] == "edms"]
    layers = sorted((r for r in results if r["kind"] == "arcgis-layer"),
                    key=lambda r: -r["score"])
    attach = [r for r in layers if r["has_attachments"]]

    # Layers are reported at the end, ranked, rather than streamed -- streaming
    # them interleaved is what made the first run unreadable.
    if layers:
        print(f"\n{'-'*70}\nArcGIS layers with a document path (ranked; score >= 6 is worth wiring):")
        for r in layers[:60]:
            tags = []
            if r["has_attachments"]:
                tags.append("ATTACHMENTS")
            if r["construction_relevant"]:
                tags.append("construction")
            if r["doc_fields"]:
                tags.append(",".join(r["doc_fields"][:3]))
            print(f"  [{r['score']}] {r['host']:<34} {(r['layer_name'] or '?')[:34]:<35} {' | '.join(tags)}")
            print(f"      {r['url']}")

    print(f"\n{'='*70}")
    print(f"hosts swept          : {len(hosts)}")
    print(f"EDMS repositories    : {len(edms)}")
    print(f"ArcGIS doc-path lyrs : {len(layers)}  (of which attachments-enabled: {len(attach)})")
    print("\nEvery hit needs hand-verification before wiring -- confirm a real file")
    print("actually downloads. A confirmed negative is also a result: record it in")
    print("data/jurisdiction_health_matrix.json rather than leaving a county blank.")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
