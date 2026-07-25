"""SpecIndex read API — Cloud Run front for PostgreSQL."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# specindex-db is db-f1-micro: Postgres max_connections=25, ~9 already used by
# Cloud SQL system overhead. Opening a fresh connection per request (the old
# behavior) exhausts that fast under concurrent load — verified 2026-07-25:
# 13/40 truly simultaneous requests returned 500s before this pool was added.
# maxconn=6 here, paired with `gcloud run services update --max-instances=2`,
# caps worst-case pooled connections at 12 — safely under the 25 limit even
# with system overhead included.
#
# Important: psycopg2's pool does NOT block when exhausted — getconn() raises
# PoolError immediately. A naive fixed-size pool with no retry is *worse* than
# no pool under a burst (verified: 35/40 requests failed on first attempt of
# this fix). get_conn() below retries with backoff so requests queue briefly
# for a free connection instead of failing the instant the pool is full.
POOL_MIN_CONN = 1
POOL_MAX_CONN = 6
POOL_ACQUIRE_TIMEOUT_SECONDS = 5.0
POOL_ACQUIRE_RETRY_INTERVAL_SECONDS = 0.05

app = FastAPI(title="SpecIndex API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            POOL_MIN_CONN, POOL_MAX_CONN, dsn=DATABASE_URL
        )
    return _pool


@app.on_event("shutdown")
def _close_pool() -> None:
    if _pool is not None:
        _pool.closeall()


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = None
    deadline = time.monotonic() + POOL_ACQUIRE_TIMEOUT_SECONDS
    while conn is None:
        try:
            conn = pool.getconn()
        except psycopg2.pool.PoolError:
            if time.monotonic() >= deadline:
                raise HTTPException(
                    status_code=503,
                    detail="Database connection pool exhausted, try again",
                )
            time.sleep(POOL_ACQUIRE_RETRY_INTERVAL_SECONDS)
    try:
        yield conn
    finally:
        # Roll back so a connection left mid-transaction by a failed request
        # doesn't get handed to the next borrower in a dirty state.
        conn.rollback()
        pool.putconn(conn)


def row_to_project(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["project_id"],
        "project_sk": row["project_sk"],
        "external_ids": row["external_ids"] or {},
        "record_type": row["record_type"],
        "name": row["name"],
        "state": row["state"],
        "city": row["city"] or "",
        "county": row["county"] or "",
        "status": row["status"],
        "project_type": row["project_type"] or "other",
        "estimated_value_usd": row["estimated_value_usd"],
        "square_footage": row["square_footage"],
        "owner": row["owner"] or "",
        "architect": row["architect"] or "",
        "general_contractor": row["general_contractor"] or "",
        "opened_or_announced_date": (
            row["opened_or_announced_date"].isoformat()
            if row["opened_or_announced_date"]
            else None
        ),
        "description": row["description"] or "",
        "key_specs": row["key_specs"] or [],
        "mentioned_brands": row["mentioned_brands"] or [],
        "competitor_watch": row["competitor_watch"] or [],
        "sources": row["sources"] or [],
        "open_for": row["open_for"] or "",
    }


@app.get("/health")
def health():
    if not DATABASE_URL:
        return {"ok": False, "database": "not configured"}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"ok": True, "database": "connected"}
    except Exception as exc:
        return {"ok": False, "database": str(exc)}


@app.get("/v1/stats")
def stats():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT total, states, early_stage FROM v_project_stats")
            row = cur.fetchone()
            if not row:
                return {"total": 0, "states": 0, "early_stage": 0}
            return dict(row)


@app.get("/v1/projects")
def list_projects(
    state: str | None = Query(default=None, min_length=2, max_length=2),
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    clauses: list[str] = []
    params: list[Any] = []

    if state:
        clauses.append("state = %s")
        params.append(state.upper())
    if status:
        clauses.append("status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT count(*) AS n FROM projects {where}",
                params,
            )
            total = int(cur.fetchone()["n"])

            cur.execute(
                f"""
                SELECT *
                FROM projects
                {where}
                ORDER BY name
                LIMIT %s OFFSET %s
                """,
                [*params, limit, offset],
            )
            rows = cur.fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "projects": [row_to_project(r) for r in rows],
    }


@app.get("/v1/projects/{project_id}")
def get_project(project_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return row_to_project(row)
