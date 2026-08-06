#!/usr/bin/env python3
"""Find real government documents for projects we hold zero documents for, by
running the search a user would run -- "<project name> documents" -- through
Google Search grounding on Vertex AI.

WHY THIS EXISTS. On 2026-08-06 Asif googled "1326 Saint Antoine St documents"
and got the City of Detroit Planning Commission staff report for a project whose
SpecIndex record held 0 documents, 0 rulings and no owner. The document names
the developer, the storey count and the gross square footage -- every field the
record renders as absent. Nothing in this repo had ever fetched it, and nothing
in this repo had ever looked: grepping the whole tree for "detroitmi" returns
zero hits. Detroit reaches us through one pipe, the BSEED permit ArcGIS layer,
which is metadata and carries no attachments.

NOT scripts/document-research-fallback.py. That asks Gemini to *recall* URLs from
its weights, which is the mode with a measured ~14% hit rate. This grounds every
query in a live Google index through GCP, so the model is summarising search
results rather than reciting memorised strings -- and then every URL it returns
is fetched and inspected before anything is stored.

THE PATH-REPAIR STEP IS THE INTERESTING PART, and it is a direct consequence of
the rule that grounding narrows hallucination without eliminating it. Measured on
the Detroit project, the model returned five URLs. Every single one 404'd as
given. Every single one became a real PDF when "/events/" was inserted into the
path:

    .../files/2025-04/Staff Report - 1326 St Antoine....pdf      -> 404 (HTML)
    .../files/events/2025-04/Staff Report - 1326 St Antoine....pdf -> 200, 363KB PDF

So the model recovers FILENAMES reliably and PATHS unreliably, which makes a
naive url_resolves() check throw away real documents -- it would have scored that
project 0-for-5 when the true answer was 5-for-5. Rather than hardcode Detroit's
layout, TEMPLATES holds the shapes municipal CMSes actually use, and a template
that works for a domain is cached in _LEARNED and tried first for every later URL
on that domain. One probe teaches the crawler the city's layout.

EVERY acceptance is content-checked, never status-checked. A 404 on this host
returns HTTP 404 with a 150KB HTML body, but plenty of government hosts answer
unknown paths with a cheerful 200 and their landing page, so a URL is accepted
only when it returns a real PDF magic number and is not byte-identical to the
baseline that host serves for a path we know is nonsense.

COST IS THE REASON FOR --limit. 589,317 projects hold no documents; grounded
search bills per query, so sweeping all of them is a five-figure decision, not a
default. Run a pilot, read the hit rate this prints, then choose.
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from specindex.db import connect  # noqa: E402

GCS_BUCKET = "specindex-ai-raw-documents"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# Path shapes seen on municipal CMSes. {d} is the directory the model proposed
# (usually a YYYY-MM bucket), {f} the filename. Drupal -- which detroitmi.gov,
# and a large share of US city sites, run -- files meeting attachments under
# /files/events/, while the model reliably guesses plain /files/.
MARKERS = ("events", "meetings", "agendas", "documents", "attachments")

# domain -> template that has already produced a real PDF here. Saves probing
# six shapes per URL once one document from a city has been captured.
_LEARNED: dict[str, str] = {}
_BASELINE: dict[str, bytes] = {}
# domain -> /sites/<host>.<THIS>/ roots already proven to serve real files
_SITE_ROOTS: dict[str, list[str]] = {}


def _get(url: str, timeout: float = 45.0) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:  # noqa: PERF203
        return e.code, b"", ""
    except Exception:  # noqa: BLE001 -- any transport failure means "not a document"
        return 0, b"", ""


def soft_404_baseline(host_root: str) -> bytes:
    """What this host serves for a path that certainly does not exist.

    Required because a government host answering 200-with-landing-page to every
    unknown path will otherwise validate every fabricated filename we probe.
    """
    if host_root not in _BASELINE:
        probe = f"{host_root}/zzz-specindex-not-a-real-file-9174.pdf"
        _, body, _ = _get(probe, timeout=20)
        _BASELINE[host_root] = body
    return _BASELINE[host_root]


def is_real_pdf(body: bytes, host_root: str) -> bool:
    if len(body) < 2048 or not body[:5].startswith(b"%PDF"):
        return False
    base = soft_404_baseline(host_root)
    # Identical bytes to the known-nonsense response means the host is echoing a
    # generic page, whatever status it chose to send with it.
    return not (base and body == base)


def _head(url: str, timeout: float = 20.0) -> tuple[int, str]:
    """Cheap existence probe. Repair tries many candidates per URL, and pulling a
    35MB staff report just to learn a path was wrong is both slow and rude to a
    government host."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def _candidate_paths(directory: str, filename: str, netloc: str) -> list[str]:
    """Every plausible real path for a filename the model located but misfiled.

    Two independent things go wrong, and BOTH have been observed on one document:

      directory  the CMS subfolder. Real: /files/events/2025-04/. Model: /files/
                 2025-04/. The marker segment sits BEFORE the date bucket, not
                 after it -- an earlier version of this function appended it and
                 repaired nothing.
      site root  Drupal multisite. Real: /sites/detroitmi.localhost/. Flash
                 returned /sites/detroitmi.portal.gov/.
    """
    dirs = [directory]
    m = re.match(r"^(/sites/)([^/]+)(/.*)$", directory)
    if m:
        label = netloc.split(".")[0]
        for alt in _SITE_ROOTS.get(netloc, []) + ["localhost", "portal.gov", "gov"]:
            cand = f"{m.group(1)}{label}.{alt}{m.group(3)}"
            if cand not in dirs:
                dirs.append(cand)

    out: list[str] = []
    for d in dirs:
        segs = d.strip("/").split("/")
        out.append("/" + "/".join(segs) + "/" + filename)
        # Insert the marker one level up from the leaf, which is where a date
        # bucket normally sits, and also at the leaf.
        for marker in MARKERS:
            for pos in (max(len(segs) - 1, 0), len(segs)):
                trial = segs[:pos] + [marker] + segs[pos:]
                cand = "/" + "/".join(trial) + "/" + filename
                if cand not in out:
                    out.append(cand)
    return out


def repair_and_verify(url: str, pause: float, max_probes: int = 26) -> tuple[str, bytes] | None:
    """Return (working_url, pdf_bytes) or None.

    Probes with HEAD, downloads only on a hit, then content-checks the body --
    a 200 with an HTML landing page is the normal way a government host says
    "no such file", so status alone never decides.
    """
    parts = urllib.parse.urlsplit(url)
    host_root = f"{parts.scheme}://{parts.netloc}"
    if "/" not in parts.path.strip("/"):
        return None
    directory, filename = parts.path.rsplit("/", 1)

    cands = _candidate_paths(directory, filename, parts.netloc)
    learned = _LEARNED.get(parts.netloc)
    if learned:  # a shape already proven on this domain goes first
        cands.sort(key=lambda c: 0 if learned in c else 1)

    for cand_path in cands[:max_probes]:
        candidate = f"{host_root}{cand_path}"
        status, ctype = _head(candidate)
        time.sleep(pause)  # a ban on a city domain is permanent loss of a source
        if status != 200 or "pdf" not in (ctype or "").lower():
            continue
        st, body, _ = _get(candidate)
        if st != 200 or not is_real_pdf(body, host_root):
            continue
        for marker in MARKERS:
            if f"/{marker}/" in cand_path:
                _LEARNED[parts.netloc] = marker
                break
        rm = re.match(r"^/sites/[^./]+\.([^/]+)/", cand_path)
        if rm:
            roots = _SITE_ROOTS.setdefault(parts.netloc, [])
            if rm.group(1) not in roots:
                roots.insert(0, rm.group(1))
        return candidate, body
    return None


def grounded_search(client, types, model: str, project_name: str, city: str, state: str) -> list[str]:
    """Asif's query, run through Google Search on GCP. Returns candidate URLs
    from BOTH the answer text and the grounding chunks -- the chunks are URLs
    Google actually indexed, so they are the higher-trust half."""
    where = ", ".join(x for x in (city, state) if x)
    # Asif's format, adopted verbatim on 2026-08-06 after it outperformed a
    # documents-only query by hand. Asking for the project narrative FIRST makes
    # the model resolve what the project actually is -- developer, tenant, scope,
    # the fact that it is the old Wayne County juvenile site -- before it looks
    # for files, and the file hunt is better targeted as a result. Part 1 is
    # never stored as fact; it exists to steer part 2.
    prompt = (
        f"Search google for:\n"
        f"1. project details for {project_name} project"
        + (f" in {where}" if where else "")
        + "\n2. document links for me to download\n\n"
        "For part 2 list ONLY direct URLs ending in .pdf on government (.gov/.us/"
        "state/county/city) domains -- planning commission staff reports, public "
        "hearing notices, site plan or architectural presentations, zoning "
        "petitions, council packets.\n"
        "Format part 2 as bare URLs, one per line, no markdown links."
    )
    tool = types.Tool(google_search=types.GoogleSearch())
    resp = client.models.generate_content(
        model=model, contents=prompt, config=types.GenerateContentConfig(tools=[tool])
    )
    urls: list[str] = []
    for m in re.finditer(r"https?://[^\s\)\"'<>]+\.pdf", resp.text or "", re.I):
        urls.append(m.group(0))
    for cand in (resp.candidates or []):
        gm = getattr(cand, "grounding_metadata", None)
        for ch in (getattr(gm, "grounding_chunks", None) or []):
            web = getattr(ch, "web", None)
            uri = getattr(web, "uri", "") if web else ""
            if uri.lower().endswith(".pdf"):
                urls.append(uri)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200,
                    help="projects to search. Grounded search bills per query -- "
                         "this is a cost control, not a paging convenience.")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--min-value", type=float, default=1_000_000)
    ap.add_argument("--state", default=None)
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between HTTP fetches")
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--sentinel", default=None, help="file to touch on clean completion")
    ap.add_argument("--dry-run", action="store_true", help="search and verify; store nothing")
    args = ap.parse_args()

    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    conn = connect()
    cur = conn.cursor()
    # Highest-value, most-recent projects with nothing held. Value ordering is a
    # proxy for "a document was probably published about this", and it is the
    # cohort where a found document is worth the most.
    sql = """
        SELECT p.project_sk, p.project_id, p.name, p.city, p.state
        FROM projects p
        WHERE NOT EXISTS (SELECT 1 FROM project_document_files f
                          WHERE f.project_sk = p.project_sk)
          AND p.opened_or_announced_date >= %s
          AND COALESCE(p.estimated_value_usd, 0) >= %s
          AND p.name IS NOT NULL AND length(p.name) > 6
    """
    params: list = [args.since, args.min_value]
    if args.state:
        sql += " AND p.state = %s"
        params.append(args.state)
    sql += " ORDER BY p.estimated_value_usd DESC NULLS LAST LIMIT %s"
    params.append(args.limit)
    cur.execute(sql, params)
    rows = cur.fetchall()
    print(f"[scope] {len(rows)} zero-document projects since {args.since} "
          f">= ${args.min_value:,.0f}", flush=True)

    bucket = None
    if not args.dry_run:
        from google.cloud import storage
        bucket = storage.Client().bucket(GCS_BUCKET)

    searched = hits = stored = repaired = 0
    t0 = time.time()

    for i, (sk, pid, name, city, state) in enumerate(rows, 1):
        try:
            urls = grounded_search(client, types, args.model, name, city or "", state or "")
        except Exception as e:  # noqa: BLE001 -- one bad project must not end the sweep
            print(f"  [search-error] {pid}: {type(e).__name__}", flush=True)
            continue
        searched += 1
        found_for_project = 0

        for u in urls[:6]:
            got = repair_and_verify(u, args.pause)
            if not got:
                continue
            real_url, body = got
            if real_url != u:
                repaired += 1
            found_for_project += 1

            if args.dry_run:
                print(f"  [would-store] {real_url[:120]} ({len(body):,}B)", flush=True)
                continue

            digest = hashlib.sha256(body).hexdigest()
            ext = mimetypes.guess_extension("application/pdf") or ".pdf"
            blob_path = f"content/{digest}{ext}"
            blob = bucket.blob(blob_path)
            if not blob.exists():
                blob.upload_from_string(body, content_type="application/pdf")
            title = urllib.parse.unquote(real_url.rsplit("/", 1)[-1])
            cur.execute(
                """
                INSERT INTO project_document_files
                    (project_sk, title, url, content_type, gcs_path,
                     content_sha256, fetched_at, computed_at)
                VALUES (%s, %s, %s, 'application/pdf', %s, %s, now(), now())
                ON CONFLICT (project_sk, url) DO UPDATE SET
                    gcs_path = EXCLUDED.gcs_path,
                    content_sha256 = EXCLUDED.content_sha256,
                    fetched_at = now(), computed_at = now()
                """,
                (sk, title[:500], real_url, blob_path, digest),
            )
            stored += 1

        if found_for_project:
            hits += 1
            conn.commit()
            print(f"  [HIT] {pid} :: {name[:56]} -> {found_for_project} doc(s)", flush=True)

        if i % 10 == 0 or i == len(rows):
            el = time.time() - t0
            rate = i / el if el else 0
            eta = (len(rows) - i) / rate / 60 if rate else 0
            print(f"[{i}/{len(rows)}] hit-rate={hits/searched*100:4.1f}% "
                  f"docs={stored} repaired={repaired} "
                  f"{rate*60:.1f}/min ETA {eta:.0f}m", flush=True)

    conn.commit()
    pct = (hits / searched * 100) if searched else 0
    print(f"\n[done] searched={searched} projects_with_docs={hits} ({pct:.1f}%) "
          f"documents_stored={stored} path_repaired={repaired}", flush=True)
    print(f"[learned] path templates: {_LEARNED}", flush=True)
    if args.sentinel:
        Path(args.sentinel).write_text(f"done {stored} docs {pct:.1f}% hit\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
