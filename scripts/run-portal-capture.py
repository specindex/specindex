#!/usr/bin/env python3
"""A3 runner -- drives the verified portal adapters, classifies, logs.

WHY THIS EXISTS SEPARATELY FROM THE ADAPTERS. 23 adapters were verified and
nothing drove them, so the weekly schedule pointed at a script that did not
exist -- a cron job that looks scheduled and is a no-op. This is the thing that
turns adapters into a pull.

STANDING RULES, ENFORCED HERE:
  * Public data only. Adapters never create an account, pay, or submit.
  * Every logged row carries its source URL and the fetch date (rule 5).
  * Blockers are OUTCOMES, not failures to route around: `registration
    required`, `unreadable format`, `dead link`, `needs browser`. A run that
    reports a wall is working correctly.
  * On a 404, the migrated URL is the fix -- flagged in the log as `dead link`
    with the portal so a human updates the source CSV and notes it in the commit.

THE LOG IS APPEND-ONLY. One file per run keyed by date, never rewritten, so a
crash mid-run cannot destroy earlier rows and two runs cannot interleave. The
funnel is derived from the logs, not stored -- a stored percentage goes stale the
moment anything is appended.

CHECKPOINT PER BATCH. A 34-portal crawl that writes once at the end hands over
nothing if it dies at portal 30. That already cost a DOT run its entire manifest.
"""
from __future__ import annotations
import argparse, csv, datetime, importlib.util, io, re, sys, time, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "scripts" / "portal_adapters"
LOGDIR = ROOT / "coverage" / "pull-log"

# The bucket the pipeline already writes to, confirmed with Asif 2026-08-06 and
# probed at OBJECT level (bucket.exists() lies when credentials are stale).
# The repo holds code and source tables only -- a spec book is 300-1,000+ pages
# and never belongs in git.
GCS_BUCKET = "specindex-ai-raw-documents"

FIELDS = ["state", "type", "portal", "project_id", "project_name", "bid_due_date",
          "document_url", "file_name", "file_size", "spec_format", "divisions",
          "gcs_path", "retrieved_date", "status",
          # doc_type is decided here, from the filename, at the only moment the
          # filename is authoritative. Downstream must not re-derive it: the
          # loader writes the project number into `title`, so classifying from
          # title returned "other" and skipped the spec book entirely.
          "doc_type"]

# Classifier, straight from the skill's rule 6. BOTH formats count.
CSI_PARTS = re.compile(r"PART\s+[123]\s*[-–—]?\s*(GENERAL|PRODUCTS|EXECUTION)", re.I)
CSI_DIVISION = re.compile(r"\bDIVISION\s+(\d{1,2})\b", re.I)
CSI_SECTION = re.compile(r"\b(0[0-9]|1[0-4]|2[0-8]|3[0-5])\s\d{2}\s\d{2}\b")
DOT_SECTION = re.compile(r"\bSECTION\s+\d{3,5}\b", re.I)
DOT_SKELETON = re.compile(r"\b(BASIS\s+OF\s+PAYMENT|METHOD\s+OF\s+MEASUREMENT|"
                          r"CONSTRUCTION\s+REQUIREMENTS|MATERIALS?\s+REQUIREMENTS)\b", re.I)


def classify(body: bytes) -> tuple[str, str]:
    """Returns (spec_format, divisions). ('', '') means not a spec document."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(body))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:90])
    except Exception:  # noqa: BLE001
        return "", ""
    if not text.strip():
        return "unreadable", ""
    divs = sorted({m.group(1).zfill(2) for m in CSI_DIVISION.finditer(text)})
    if CSI_PARTS.search(text) or divs:
        return "CSI", ";".join(divs)
    if DOT_SECTION.search(text) and DOT_SKELETON.search(text):
        return "DOT SS/SP", ""
    return "", ""


def store(bucket, body: bytes, *, state: str, project_id: str, doc_type: str,
          filename: str, source_url: str, portal: str) -> str:
    """gs://{bucket}/specs/{STATE}/{project_id}/{doc_type}_{filename}.pdf

    Object metadata carries the provenance, so a document lifted out of the
    bucket alone still answers where it came from and when -- skill rule 5. A
    fact without a citation is worthless, and an object without metadata becomes
    one the moment it is copied.
    """
    # PLATFORM ADAPTERS SERVE MANY STATES, so PORTAL["state"] is not always one
    # state: Bonfire reports "Utah, Washington" and Bid Express reports "multi".
    # Those went straight into the object path and produced
    # specs/UTAH, WASHINGTON/... -- a comma in a GCS path is legal and awful,
    # and it makes per-state listing impossible for exactly the adapters that
    # cover the most ground.
    #
    # A multi-state adapter cannot know the state from the platform alone, so
    # the honest bucket is MULTI rather than a guess. The per-project state is
    # carried in the object METADATA, where it can be corrected later without
    # rewriting paths.
    st = (state or "").strip()
    if not st or "," in st or st.lower() in ("multi", "multiple", "various"):
        st = "MULTI"
    st = re.sub(r"[^A-Za-z0-9_-]+", "-", st).upper()[:24] or "MULTI"

    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename)[:120] or "document.pdf"
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    pid = re.sub(r"[^A-Za-z0-9._-]+", "-", project_id or "unknown")[:80]
    path = f"specs/{st}/{pid}/{doc_type}_{safe}"
    blob = bucket.blob(path)
    if not blob.exists():
        blob.metadata = {"source_url": source_url, "portal": portal,
                         "doc_type": doc_type,
                         # Verbatim, even when it is a list -- the path had to be
                         # normalised, the provenance does not.
                         "portal_state": (state or "").strip(),
                         "fetch_date": datetime.date.today().isoformat()}
        blob.upload_from_string(body, content_type="application/pdf")
    return f"gs://{GCS_BUCKET}/{path}"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, default=None)
    ap.add_argument("--states", nargs="*", default=None)
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--checkpoint", action="store_true")
    ap.add_argument("--delta-only", action="store_true",
                    help="discovery only, no downloads -- the daily cheap signal")
    ap.add_argument("--max-docs", type=int, default=0,
                    help="0 = every document on the project (default)")
    # NO RECORD CAP BY DEFAULT. Discovery was hardcoded to 25 per adapter, so a
    # national run and a Maine-only deep run returned the SAME 25 Maine projects
    # -- the corpus was limited by an argument, not by what the portals publish.
    #
    # Replacing 25 with 200 would repeat the mistake in a larger size. A record
    # cap silently truncates: 25 of 200 available reads exactly like "this portal
    # has 25 projects", and nothing in the output distinguishes them. That is the
    # failure mode this repo keeps hitting.
    #
    # The real constraints are runtime and politeness to government servers, so
    # those are bounded explicitly instead -- and when a bound is hit the log
    # SAYS SO, which a record cap never did. 0 means take everything the portal
    # offers.
    ap.add_argument("--discover-limit", type=int, default=0,
                    help="0 = no cap (default). Set only to sample deliberately.")
    # A runaway GUARD, not a cap. Set high enough that a normal portal finishes
    # inside it; if it is ever hit the log says PARTIAL and a row records it, so
    # an incomplete pull can never read as a complete one.
    ap.add_argument("--max-minutes", type=float, default=240,
                    help="per-adapter runaway guard; hitting it is logged loudly")
    ap.add_argument("--no-store", action="store_true",
                    help="classify and log without writing to GCS")
    args = ap.parse_args()

    bucket = None
    if not (args.no_store or args.delta_only):
        from google.cloud import storage
        bucket = storage.Client().bucket(GCS_BUCKET)

    files = sorted(p for p in ADAPTERS.glob("*.py") if p.name != "__init__.py")
    mods = []
    for f in files:
        try:
            m = load(f)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip] {f.stem}: import failed {type(e).__name__}", flush=True)
            continue
        if not hasattr(m, "PORTAL"):
            continue
        if args.tier and int(m.PORTAL.get("tier", 0)) != args.tier:
            continue
        if args.states and m.PORTAL.get("state") not in args.states:
            continue
        mods.append((f.stem, m))

    LOGDIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logpath = LOGDIR / f"pull-{stamp}.csv"
    today = datetime.date.today().isoformat()
    print(f"[scope] {len(mods)} adapters -> {logpath.relative_to(ROOT)}", flush=True)

    rows: list[dict] = []
    projects = docs = specs = 0

    def flush():
        """Append-only: header written once, rows only ever appended."""
        new = not logpath.exists()
        with logpath.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)
        rows.clear()

    for i, (name, m) in enumerate(mods, 1):
        P = m.PORTAL
        base = dict(state=P.get("state"), type=P.get("type"), portal=name,
                    retrieved_date=today, bid_due_date="", divisions="",
                    spec_format="", gcs_path="")
        try:
            # A very large number rather than None: every adapter signature
            # takes an int, and this keeps one code path.
            found = m.discover(limit=args.discover_limit or 100_000)
        except Exception as e:  # noqa: BLE001
            rows.append({**base, "project_id": "", "project_name": "",
                         "document_url": P.get("listing_url", ""), "file_name": "",
                         "file_size": "", "status": f"dead link ({type(e).__name__})"})
            print(f"  [{i}/{len(mods)}] {name}: discover failed {type(e).__name__}", flush=True)
            found = []

        if not found:
            rows.append({**base, "project_id": "", "project_name": "",
                         "document_url": P.get("listing_url", ""), "file_name": "",
                         "file_size": "", "status": "no active solicitations"})

        adapter_start = time.time()
        truncated = False
        for proj in found:
            if (time.time() - adapter_start) / 60 > args.max_minutes:
                # Loud, and recorded in the log as a row, so a partial pull can
                # never be mistaken for a complete one.
                truncated = True
                print(f"  [{name}] TIME BUDGET {args.max_minutes}m hit after "
                      f"{projects} projects -- PARTIAL, rerun to continue", flush=True)
                rows.append({**base, "project_id": "", "project_name": "",
                             "document_url": P.get("listing_url", ""), "file_name": "",
                             "file_size": "", "status": "partial: time budget reached"})
                break
            projects += 1
            urls = proj.get("doc_urls") or []
            if args.delta_only:
                rows.append({**base, "project_id": proj.get("project_number") or "",
                             "project_name": (proj.get("project_name") or "")[:200],
                             "document_url": urls[0] if urls else "", "file_name": "",
                             "file_size": "", "status": "listed, not fetched (delta)"})
                continue
            for u in (urls[:args.max_docs] if args.max_docs else urls):
                try:
                    body = m.fetch(u)
                except Exception:  # noqa: BLE001
                    body = None
                time.sleep(1.0)          # never faster than 1 req/s per host
                if not body:
                    rows.append({**base, "project_id": proj.get("project_number") or "",
                                 "project_name": (proj.get("project_name") or "")[:200],
                                 "document_url": u, "file_name": u.rsplit("/", 1)[-1][:120],
                                 "file_size": "", "status": "dead link"})
                    continue
                docs += 1
                fmt, divs = classify(body)
                gcs = ""
                if fmt in ("CSI", "DOT SS/SP"):
                    specs += 1

                # Filename decides doc_type, not the CSI test. A drawing set
                # references divisions on its sheet index, so
                # "_O2512-01 - Final Plans.pdf" (22MB) classified as CSI and was
                # stored as a specbook. Content proves it IS a specification
                # document; the name says which KIND.
                low = urllib.parse.unquote(u).lower()
                if re.search(r"\bplans?\b|drawing|sheet", low):
                    doc_type = "drawings"
                elif re.search(r"addend", low):
                    doc_type = "addendum"
                elif re.search(r"tabulation|bid[_\- ]?tab", low):
                    doc_type = "bid_tab"
                elif re.search(r"legal[_\- ]?ad|advertis", low):
                    doc_type = "advertisement"
                elif re.search(r"notice", low):
                    doc_type = "notice"
                elif fmt == "DOT SS/SP" or re.search(r"proposal", low):
                    doc_type = "proposal"
                elif fmt in ("CSI", "DOT SS/SP"):
                    doc_type = "specbook"
                else:
                    doc_type = "other"

                if fmt == "unreadable":
                    status = "unreadable format"
                elif bucket is not None:
                    # STORE EVERY FETCHED PDF, not only the spec-confirmed ones.
                    #
                    # This used to be gated on `fmt in (CSI, DOT SS/SP)` with the
                    # reasoning that "the moat is the specification, not the
                    # paperwork around it". Measured on Maine 2026-08-07: 381
                    # documents downloaded, 74 stored -- exactly the spec-confirmed
                    # count. The other 307 were fetched, content-checked, and
                    # discarded, and because the pull log still said "downloaded"
                    # they looked captured.
                    #
                    # The discarded set is not paperwork. It is every ADDENDUM (the
                    # change record, and the only place a DISPLACED manufacturer is
                    # ever visible) and every BID TABULATION (who bid, and what
                    # they bid). A one-page addendum has no CSI structure, so the
                    # spec test can never accept it -- the filter was structurally
                    # incapable of keeping the documents it most needed to keep.
                    #
                    # A document not fetched is gone once the jurisdiction rotates
                    # its site; storage is the cheap side of that trade.
                    try:
                        gcs = store(bucket, body, state=P.get("state") or "",
                                    project_id=proj.get("project_number") or "",
                                    doc_type=doc_type,
                                    filename=u.rsplit("/", 1)[-1],
                                    source_url=u, portal=name)
                        status = "downloaded"
                    except Exception as e:  # noqa: BLE001
                        status = f"verified, not stored ({type(e).__name__})"
                else:
                    status = "verified, not stored"
                rows.append({**base, "project_id": proj.get("project_number") or "",
                             "project_name": (proj.get("project_name") or "")[:200],
                             "document_url": u, "file_name": u.rsplit("/", 1)[-1][:120],
                             "file_size": len(body), "spec_format": fmt,
                             "divisions": divs, "gcs_path": gcs, "status": status,
                             "doc_type": doc_type})
                # NO BREAK. This used to stop after the first confirmed document
                # per project, because the funnel metric counts "projects with a
                # spec doc" and one was enough to answer it. But a project manual,
                # its addenda and its drawings are DIFFERENT documents with
                # different divisions -- taking only the first discards the rest,
                # and an addendum is where substitution rulings live.
                #
                # The metric was shaping the capture. Capture everything; compute
                # the metric from what is held.

        if args.checkpoint and i % args.batch_size == 0:
            flush()
            print(f"  [checkpoint] {i}/{len(mods)} adapters, log appended", flush=True)

    flush()
    pct_d = docs / projects * 100 if projects else 0
    pct_s = specs / docs * 100 if docs else 0
    print(f"\n[funnel] projects={projects}  with-documents={docs} ({pct_d:.1f}%)  "
          f"confirmed-spec-docs={specs} ({pct_s:.1f}% of documents)")
    print(f"[log] {logpath.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
