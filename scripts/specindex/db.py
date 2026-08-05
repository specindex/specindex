"""Postgres access plus the pipeline contracts and work queue.

stage_run() is the important one: it forces a stage to declare what the NEXT
stage can see. The seam bug (10,033 objects in GCS, 2,240 rows in the table,
78% of the corpus unreachable) was invisible precisely because no stage was
ever asked that question.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from contextlib import contextmanager


def url_from_env() -> str:
    u = os.environ.get("DATABASE_URL")
    if u:
        return u
    from pathlib import Path  # noqa: PLC0415

    env = Path(__file__).resolve().parents[2] / ".env"
    vals: dict[str, str] = {}
    if env.is_file():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return (f"postgresql://{vals.get('SPECINDEX_DB_USER','specindex')}:"
            f"{vals.get('SPECINDEX_DB_PASSWORD','')}@localhost:5433/"
            f"{vals.get('SPECINDEX_DB_NAME','specindex')}")


def connect(url: str | None = None, timeout: int = 30):
    import psycopg2  # noqa: PLC0415

    return psycopg2.connect(url or url_from_env(), connect_timeout=timeout)


@contextmanager
def stage_run(conn, stage: str, scope: str | None = None, rows_in: int | None = None):
    """Record a pipeline stage and REQUIRE it to verify its own seam.

        with stage_run(conn, "register", scope="all") as run:
            ...
            run["rows_out"] = n_written
            run["rows_visible_downstream"] = count_next_stage_can_see()

    Leaving rows_visible_downstream unset is recorded as UNVERIFIED rather
    than as success -- an unchecked seam is not a passing seam.
    """
    cur = conn.cursor()
    cur.execute("INSERT INTO pipeline_stage_runs (stage, scope, rows_in) VALUES (%s,%s,%s) RETURNING id",
                (stage, scope, rows_in))
    run_id = cur.fetchone()[0]
    conn.commit()
    state: dict = {"rows_out": None, "rows_visible_downstream": None, "notes": None}
    try:
        yield state
    except Exception as e:  # noqa: BLE001
        cur.execute("UPDATE pipeline_stage_runs SET finished_at=now(), status='failed', error=%s "
                    "WHERE id=%s", (f"{type(e).__name__}: {e}"[:2000], run_id))
        conn.commit()
        raise
    out, vis = state["rows_out"], state["rows_visible_downstream"]
    status = "ok"
    if out and vis is not None and vis < out:
        status = "partial"
    cur.execute("UPDATE pipeline_stage_runs SET finished_at=now(), status=%s, rows_out=%s, "
                "rows_visible_downstream=%s, notes=%s WHERE id=%s",
                (status, out, vis, json.dumps(state["notes"]) if state["notes"] else None, run_id))
    conn.commit()
    if vis is None:
        print(f"[seam] {stage}: UNVERIFIED -- stage did not check what the next "
              f"stage can see", file=sys.stderr)
    elif out and vis < out:
        print(f"[seam] {stage}: LEAKING -- produced {out:,}, downstream sees {vis:,}",
              file=sys.stderr)


# --- work queue -------------------------------------------------------------

def enqueue(conn, kind: str, payload: dict, priority: int = 5,
            dedupe_key: str | None = None) -> bool:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO work_queue (kind, payload, priority, dedupe_key) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT DO NOTHING RETURNING id", (kind, json.dumps(payload), priority, dedupe_key))
    row = cur.fetchone()
    conn.commit()
    return row is not None


@contextmanager
def claim(conn, kind: str, worker: str | None = None):
    """Claim one item with FOR UPDATE SKIP LOCKED.

    This is what makes concurrency a config value rather than a process count,
    and what makes a dead worker's item recoverable instead of silently lost.
    Yields None when the queue is empty.
    """
    worker = worker or f"{socket.gethostname()}:{os.getpid()}"
    cur = conn.cursor()
    cur.execute("""
        UPDATE work_queue SET status='claimed', claimed_at=now(), claimed_by=%s,
               attempts = attempts + 1
        WHERE id = (SELECT id FROM work_queue WHERE kind=%s AND status='pending'
                    ORDER BY priority, id FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING id, payload, attempts, max_attempts""", (worker, kind))
    row = cur.fetchone()
    conn.commit()
    if not row:
        yield None
        return
    item_id, payload, attempts, max_attempts = row
    try:
        yield {"id": item_id, "payload": payload, "attempts": attempts}
    except Exception as e:  # noqa: BLE001
        status = "failed" if attempts < max_attempts else "dead"
        cur.execute("UPDATE work_queue SET status=%s, last_error=%s, finished_at=now() "
                    "WHERE id=%s", (status, f"{type(e).__name__}: {e}"[:2000], item_id))
        conn.commit()
        raise
    cur.execute("UPDATE work_queue SET status='done', finished_at=now() WHERE id=%s", (item_id,))
    conn.commit()


def requeue_stale(conn, minutes: int = 60) -> int:
    cur = conn.cursor()
    cur.execute("SELECT requeue_stale_work(%s)", (minutes,))
    n = cur.fetchone()[0]
    conn.commit()
    if n:
        print(f"[queue] requeued {n} items from vanished workers", file=sys.stderr)
    return n
