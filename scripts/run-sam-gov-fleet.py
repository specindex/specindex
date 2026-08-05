#!/usr/bin/env python3
"""Run the SAM.gov document pull across all states through a BOUNDED pool.

WHY NOT 50 PARALLEL PROCESSES. Three reasons, two of them measured on this
machine:

  1. Bandwidth is the ceiling, not concurrency. ~100 GB at the measured
     ~360 KB/s effective rate is ~3 days no matter how many processes run.
     Fifty processes split one pipe fifty ways; they do not widen it.
  2. This stack collapses well before that. Document capture at 8 concurrent
     transfers produced 0 uploads and OSError 65 "no route to host" in four
     minutes; at 3 workers it produced 8 uploads in 3.3 minutes with zero
     errors. Past the uplink limit throughput goes DOWN, not up.
  3. fetch-sam-gov-documents.py has no rate limiting of its own. Fifty
     unthrottled processes against api.sam.gov is how a source gets blocked,
     and SAM.gov is currently the only source delivering BOTH full project
     manuals and amendments (federal addenda). A ban there is a permanent
     loss of the wedge, not a temporary inconvenience.

So: every state is queued, a small number run at once, and the pool is the
throttle. "All 50 states" is the work; it is not the concurrency.

ORDERING MATTERS. States are run in descending order of indexed SAM
opportunities, so the states carrying the most federal construction land
first. extract-spec-book.py then gets a real corpus in hours instead of
waiting days for the alphabet to reach it.

Usage:
  python3 scripts/run-sam-gov-fleet.py --workers 4
  python3 scripts/run-sam-gov-fleet.py --workers 4 --dry-run
  python3 scripts/run-sam-gov-fleet.py --workers 4 --only ca,tx,fl
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATES_DIR = ROOT / "data" / "states"

_lock = threading.Lock()


def log(msg: str) -> None:
    with _lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sam_counts() -> list[tuple[str, int]]:
    """(state_code, indexed SAM opportunities), descending.

    Read from the state files rather than the DB so this runs even when the
    Cloud SQL proxy is down -- the fleet should not be blocked on a database
    it does not otherwise need.
    """
    out = []
    for f in sorted(STATES_DIR.glob("*.json")):
        code = f.stem
        if len(code) != 2:
            continue
        try:
            data = json.loads(f.read_text())
        except Exception:  # noqa: BLE001 -- a malformed state file must not stop the fleet
            continue
        projects = data.get("projects") or []
        n = sum(1 for p in projects if str(p.get("id", "")).startswith(f"{code}-sam-"))
        if n:
            out.append((code, n))
    out.sort(key=lambda kv: -kv[1])
    return out


def run_state(code: str, n: int, dry_run: bool, logdir: Path) -> tuple[str, int, str]:
    logfile = logdir / f"sam-{code}.log"
    cmd = [sys.executable, str(ROOT / "scripts" / "fetch-sam-gov-documents.py"),
           "--state-file", str(STATES_DIR / f"{code}.json"),
           "--id-prefix", f"{code}-sam"]
    if dry_run:
        cmd.append("--dry-run")
    log(f"START  {code} ({n} opportunities)")
    t0 = time.time()
    with logfile.open("w") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=str(ROOT))
    mins = (time.time() - t0) / 60
    text = logfile.read_text(errors="replace")
    uploads = len(re.findall(r"\buploaded\b", text, re.I))
    # OSError 65 is the specific signature of a saturated uplink. Surface it
    # loudly -- it means the pool is too wide, not that the source is empty.
    if "OSError" in text and "65" in text:
        log(f"  !! {code}: OSError 65 present -- uplink saturated, LOWER --workers")
    log(f"DONE   {code} rc={proc.returncode} uploads~{uploads} {mins:.1f}min -> {logfile.name}")
    return code, uploads, str(logfile)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4,
                    help="Concurrent states. KEEP SMALL: 8 concurrent transfers "
                         "measured 0 uploads + OSError 65; 3 measured clean.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="comma list of state codes")
    ap.add_argument("--logdir", type=Path,
                    default=Path("/private/tmp/claude-501/-Users-ahussain2373-Projects-specindex/"
                                 "9d44cdb2-8492-4fbc-a1f7-0d5aa3b60029/scratchpad/samfleet"))
    args = ap.parse_args()

    if args.workers > 6:
        print(f"REFUSING --workers {args.workers}: past the measured uplink limit this "
              f"produces FEWER uploads and risks a SAM.gov block, which would be a "
              f"permanent loss of the only source carrying both project manuals and "
              f"amendments. Use 6 or fewer.", file=sys.stderr)
        return 2

    args.logdir.mkdir(parents=True, exist_ok=True)
    states = sam_counts()
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        states = [(c, n) for c, n in states if c in want]

    total_opps = sum(n for _, n in states)
    log(f"states with SAM opportunities: {len(states)}   total opportunities: {total_opps:,}")
    log(f"workers={args.workers} dry_run={args.dry_run}")
    log("order (descending opportunities): " + ", ".join(f"{c}:{n}" for c, n in states[:12]) + " ...")

    q: queue.Queue = queue.Queue()
    for item in states:
        q.put(item)
    results: list[tuple[str, int, str]] = []

    def worker() -> None:
        while True:
            try:
                code, n = q.get_nowait()
            except queue.Empty:
                return
            try:
                results.append(run_state(code, n, args.dry_run, args.logdir))
            except Exception as e:  # noqa: BLE001 -- one bad state must not end the fleet
                log(f"FAILED {code}: {type(e).__name__}: {e}")
            finally:
                q.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.workers)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log("\n=== FLEET SUMMARY ===")
    for code, uploads, _ in sorted(results, key=lambda r: -r[1]):
        log(f"  {code:<4} uploads~{uploads}")
    log(f"  states processed: {len(results)}  elapsed: {(time.time()-t0)/3600:.2f}h")
    log(f"  logs: {args.logdir}")
    log("SAM FLEET COMPLETE")  # sentinel for wait loops -- never pgrep for this script
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
