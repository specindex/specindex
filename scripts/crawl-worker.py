#!/usr/bin/env python3
"""Drain work_queue. Long-running, restartable, and safe to run N at a time.

Replaces shell orchestration entirely. There are NO wait loops here -- the
worker blocks on an empty queue by sleeping, never by polling for another
process, so the `pgrep -f` self-match deadlock that stalled steps 8-10 for
fifteen hours cannot recur.

Isolation is the point. A SAM.gov state run previously died on ONE GCS upload
timeout and abandoned 163 remaining opportunities. Here a failing item fails
alone, is retried up to max_attempts, and the worker moves on.

Usage:
  python3 scripts/crawl-worker.py --kinds crawl:sam,crawl:accela
  python3 scripts/crawl-worker.py --once          # drain and exit
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db  # noqa: E402

# kind -> how to run it. Kept as subprocess calls so existing scripts are
# reused rather than rewritten; the queue supplies isolation and retry.
HANDLERS: dict[str, list[str]] = {
    "crawl:sam": [sys.executable, str(ROOT / "scripts" / "fetch-sam-gov-documents.py")],
    "crawl:accela": [sys.executable, str(ROOT / "scripts" / "fetch-accela-documents.py")],
    "crawl:owner_standards": [sys.executable, str(ROOT / "scripts" / "harvest-owner-standards.py")],
}


def run_item(kind: str, payload: dict) -> None:
    base = HANDLERS.get(kind)
    if not base:
        raise RuntimeError(f"no handler for {kind}")
    cmd = list(base)
    if kind == "crawl:sam":
        # READ FROM POSTGRES, NOT THE STATE FILES. This passed --state-file
        # data/states/{st}.json, which has drifted from the database. On
        # 2026-08-08 all 50 crawl:sam items completed successfully and captured
        # ZERO documents: coverage was 44.5% before and after, 2,592 documented
        # projects before and after. Every item re-walked a file whose contents
        # were already captured on 08-05, found nothing, and exited 0.
        #
        # --from-db selects SAM projects that have a parseable notice id and no
        # documents yet: 1,324 of them, of which 946 are Solicitation or
        # Combined Synopsis/Solicitation, notice types that publish bid
        # documents by definition. The fetcher now also exits non-zero when it
        # checks projects and captures nothing, so this can never again drain
        # the queue while achieving nothing.
        #
        # --limit keeps one queue item to a bounded chunk; consecutive items
        # walk further because completed projects stop matching the selection.
        cmd += ["--from-db", "--limit", str(payload.get("limit") or 50)]
    elif kind == "crawl:accela":
        cmd += ["--tenant", payload.get("source_key", "").split(":", 1)[-1]]
    elif kind == "crawl:owner_standards":
        # harvest-owner-standards.py REQUIRES --seeds and --out. There was no
        # branch here at all, so it was invoked bare and every item died on
        # `rc=2: usage:` -- 17 queued items, none of which could ever run.
        # Hidden until 2026-08-08 because continuous-crawl.yml's bare `wait`
        # swallowed worker exit codes; the queue just grew. Paths follow the
        # usage in the script's own docstring. --out is per-item so concurrent
        # workers cannot half-write each other's manifest.
        seeds = payload.get("seeds") or "data/seeds/owner_standards_seeds.json"
        slug = re.sub(r"[^a-z0-9]+", "-", str(payload.get("source_key") or "all").lower()).strip("-")
        cmd += ["--seeds", str(ROOT / seeds),
                "--out", str(ROOT / "data" / "raw" / f"owner_standards_manifest_{slug}.json")]
    # timeout so a hung source cannot hold a worker forever -- the failure
    # mode that makes "running" and "stalled" indistinguishable.
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=7200)
    if r.returncode != 0:
        raise RuntimeError(f"rc={r.returncode}: {(r.stderr or r.stdout)[-400:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default=",".join(HANDLERS))
    ap.add_argument("--once", action="store_true", help="exit when the queue is empty")
    ap.add_argument("--idle-sleep", type=float, default=60.0)
    args = ap.parse_args()

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    conn = db.connect()
    db.requeue_stale(conn, minutes=90)
    print(f"worker draining {kinds}")

    idle = 0
    while True:
        did = False
        for kind in kinds:
            with db.claim(conn, kind) as item:
                if item is None:
                    continue
                did = True
                key = item["payload"].get("source_key", "?")
                print(f"[{time.strftime('%H:%M:%S')}] {kind} {key} "
                      f"(attempt {item['attempts']})", flush=True)
                t0 = time.time()
                run_item(kind, item["payload"])
                print(f"    ok in {(time.time()-t0)/60:.1f}m", flush=True)
        if did:
            idle = 0
            continue
        if args.once:
            print("queue empty; exiting")
            return 0
        idle += 1
        if idle % 10 == 1:
            print(f"[{time.strftime('%H:%M:%S')}] idle", flush=True)
        time.sleep(args.idle_sleep)


if __name__ == "__main__":
    raise SystemExit(main())
