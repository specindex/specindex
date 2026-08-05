#!/usr/bin/env python3
"""Enqueue every source whose cadence says it is due. Run this on a timer.

The scheduler does NOT crawl. It only decides what is due and puts it on
work_queue; workers drain the queue. Separating them is what makes crawling
continuous rather than a script somebody remembers to run:

  * the scheduler is idempotent and instant, so running it every 15 minutes
    costs nothing and a missed tick self-heals on the next one
  * workers can be started, stopped, or scaled without touching scheduling
  * concurrency is a worker-count decision, not baked into an orchestration
    script -- which is what previously produced a `while pgrep` wait loop that
    matched its own argv and stalled for fifteen hours

Priority carries the moat ordering: hot sources (open solicitations whose
addenda VANISH after award) outrank everything, because a missed hot crawl is
data permanently lost while a missed cold crawl is data collected next month.

Usage:
  python3 scripts/schedule-crawls.py                 # enqueue due sources
  python3 scripts/schedule-crawls.py --dry-run
  python3 scripts/schedule-crawls.py --retune        # adjust cadence from observed change
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db  # noqa: E402

PRIORITY = {"hot": 1, "warm": 5, "cold": 8, "frozen": 9}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--retune", action="store_true",
                    help="adjust cadence_hours from observed change history")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = db.connect()
    cur = conn.cursor()

    # Recover anything a dead worker was holding BEFORE enqueueing more, or
    # those items sit 'claimed' forever and the queue silently shrinks.
    db.requeue_stale(conn, minutes=90)

    if args.retune:
        cur.execute("SELECT retune_source_cadence()")
        print(f"cadence retuned for {cur.fetchone()[0]} sources")
        conn.commit()

    cur.execute("""
        SELECT id, source_key, kind, volatility, cadence_hours, state, county, url, config
        FROM source_registry
        WHERE status = 'active' AND next_due_at <= now()
        ORDER BY CASE volatility WHEN 'hot' THEN 1 WHEN 'warm' THEN 2
                                 WHEN 'cold' THEN 3 ELSE 4 END, next_due_at
    """)
    due = cur.fetchall()
    if args.limit:
        due = due[: args.limit]
    print(f"sources due: {len(due)}")

    enq = 0
    for sid, key, kind, vol, cad, state, county, url, config in due:
        payload = {"source_id": sid, "source_key": key, "kind": kind,
                   "state": state, "county": county, "url": url, "config": config}
        if args.dry_run:
            print(f"  would enqueue [{vol}] {key}")
            continue
        # dedupe_key keeps a source from being queued twice when the scheduler
        # runs again before a worker has picked the item up.
        if db.enqueue(conn, f"crawl:{kind}", payload,
                      priority=PRIORITY.get(vol, 5), dedupe_key=key):
            enq += 1
            # Move next_due_at forward NOW, not after the crawl. Otherwise the
            # scheduler re-enqueues the same source on every tick while a long
            # crawl is still running.
            cur.execute("UPDATE source_registry SET next_due_at = now() + make_interval(hours => %s) "
                        "WHERE id = %s", (cad, sid))
            conn.commit()
    print(f"enqueued: {enq}")

    cur.execute("SELECT kind, status, items FROM work_queue_health WHERE kind LIKE 'crawl:%'")
    for r in cur.fetchall():
        print(f"  queue {r[0]:<24} {r[1]:<10} {r[2]}")
    print("SCHEDULE COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
