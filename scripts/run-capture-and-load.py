#!/usr/bin/env python3
"""Capture portal documents and load them, in ONE process.

WHY THIS EXISTS. Capture writes a timestamped pull log to
coverage/pull-log/ and the loader reads it. On a laptop that file persists
between the two commands. In a Cloud Run Job the filesystem is EPHEMERAL: the
container exits, the log goes with it, and the loader -- whenever it next ran --
would read older logs and report +0 while the documents it needed sat in GCS
with nothing pointing at them.

That is this repo's most-repeated failure, arriving in a new place: a step
succeeding into somewhere nothing reads from. It would have been defect #9, and
it would have looked exactly like a successful capture.

The fix is not to delete the file handoff -- that handoff is what makes a load
bug repairable without re-fetching from portals that rate-limit, rotate and
sometimes charge. The fix is to keep producer and consumer inside one execution,
so the file always outlives the step that reads it, and then to PERSIST the log
to GCS as the durable audit copy.

Ordering is a hard dependency, so this runs them in-process rather than trusting
two scheduled jobs to interleave correctly.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LOGDIR = ROOT / "coverage" / "pull-log"
GCS_BUCKET = "specindex-ai-raw-documents"


def run(script: str, argv: list[str]) -> int:
    """Run a pipeline script in-process, so a crash is visible in this log."""
    print(f"\n{'='*66}\n[run] {script} {' '.join(argv)}\n{'='*66}", flush=True)
    sys.argv = [script, *argv]
    try:
        runpy.run_path(str(ROOT / "scripts" / script), run_name="__main__")
        return 0
    except SystemExit as e:                       # normal exit path for these scripts
        return int(e.code or 0)


def upload_logs(before: set[Path]) -> None:
    """Persist any pull log this run produced. The DURABLE copy of the handoff."""
    new = sorted(p for p in LOGDIR.glob("pull-*.csv") if p not in before)
    if not new:
        print("[logs] no new pull log produced", flush=True)
        return
    try:
        from google.cloud import storage
        bucket = storage.Client().bucket(GCS_BUCKET)
        for p in new:
            bucket.blob(f"pull-logs/{p.name}").upload_from_filename(str(p))
            print(f"[logs] gs://{GCS_BUCKET}/pull-logs/{p.name}", flush=True)
    except Exception as e:                        # noqa: BLE001
        # A failed upload must not fail the run: the documents are already in
        # GCS and already loaded by the time this happens.
        print(f"[logs] upload failed ({type(e).__name__}) -- documents are still loaded",
              flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="1")
    ap.add_argument("--states", nargs="*", default=None)
    ap.add_argument("--batch-size", default="10")
    ap.add_argument("--max-minutes", default="240")
    args = ap.parse_args()

    LOGDIR.mkdir(parents=True, exist_ok=True)
    before = set(LOGDIR.glob("pull-*.csv"))

    cap = ["--tier", str(args.tier), "--checkpoint",
           "--batch-size", str(args.batch_size),
           # 0 = every document on the project. Named explicitly because the
           # default being 0 is the whole point of this run: capture used to
           # stop at the first confirmed document and store only spec books.
           "--max-docs", "0",
           "--max-minutes", str(args.max_minutes)]
    if args.states:
        cap += ["--states", *args.states]
    rc = run("run-portal-capture.py", cap)
    if rc != 0:
        print(f"[warn] capture exited {rc}; loading whatever it wrote", flush=True)

    upload_logs(before)

    # Load is NOT conditional on capture's exit code. A capture that dies at
    # portal 30 of 34 has still written 30 portals' worth of documents, and
    # discarding them because the process ended badly is how a partial run
    # becomes a wasted one.
    rc_load = run("load-portal-projects.py", [])

    # ASSERT THE NEXT STEP CAN SEE IT.
    from specindex.db import connect                      # noqa: PLC0415
    cur = connect().cursor()
    cur.execute("SELECT count(*) FROM projects")
    projects = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM project_document_files")
    docs = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM project_document_files
                    WHERE doc_type = 'addendum'""")
    addenda = cur.fetchone()[0]
    print(f"\n[verify] projects={projects:,} documents={docs:,} addenda={addenda:,}",
          flush=True)
    if not docs:
        print("STOP: no documents readable after capture+load", file=sys.stderr)
        return 1
    return rc_load


if __name__ == "__main__":
    raise SystemExit(main())
