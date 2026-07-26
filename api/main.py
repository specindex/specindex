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

# Standard county/county-equivalent counts per state, used only to compute
# "how much room is left" in the /v1/coverage/insights endpoint -- not
# authoritative for anything billing- or legal-critical. A few states have
# genuinely ambiguous counts (CT reorganized into 9 planning regions in
# 2022 but 8 legacy counties are still commonly cited; VA/MO include
# independent cities as county-equivalents) -- picked the commonly-cited
# figure in each case rather than resolve every edge case.
US_COUNTY_TOTALS: dict[str, int] = {
    "AL": 67, "AK": 29, "AZ": 15, "AR": 75, "CA": 58, "CO": 64, "CT": 8,
    "DE": 3, "FL": 67, "GA": 159, "HI": 5, "ID": 44, "IL": 102, "IN": 92,
    "IA": 99, "KS": 105, "KY": 120, "LA": 64, "ME": 16, "MD": 24, "MA": 14,
    "MI": 83, "MN": 87, "MS": 82, "MO": 115, "MT": 56, "NE": 93, "NV": 17,
    "NH": 10, "NJ": 21, "NM": 33, "NY": 62, "NC": 100, "ND": 53, "OH": 88,
    "OK": 77, "OR": 36, "PA": 67, "RI": 5, "SC": 46, "SD": 66, "TN": 95,
    "TX": 254, "UT": 29, "VT": 14, "VA": 133, "WA": 39, "WV": 55, "WI": 72,
    "WY": 23,
}

# specindex-db was upgraded 2026-07-26 from db-f1-micro (max_connections=25)
# to db-custom-2-7680 (max_connections=400) specifically because the old
# 25-connection ceiling was causing real `next build` failures once the
# corpus + per-request enrichment queries (project_sources/events/news
# joins) grew past what a handful of pooled connections could absorb under
# the many parallel workers a static-export build spawns. maxconn=20 here,
# paired with `--max-instances=5` on the Cloud Run deploy, caps worst-case
# pooled connections at 100 — comfortable headroom under 400, not just
# barely-safe the way the old 6/25 split was.
#
# Important: psycopg2's pool does NOT block when exhausted — getconn() raises
# PoolError immediately. A naive fixed-size pool with no retry is *worse* than
# no pool under a burst (verified 2026-07-25: 35/40 requests failed on first
# attempt of this fix). get_conn() below retries with backoff so requests
# queue briefly for a free connection instead of failing the instant the
# pool is full.
POOL_MIN_CONN = 1
POOL_MAX_CONN = 20
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


def spx_id(project_sk: int) -> str:
    """The one identifier customers should ever see or reference -- a
    branded, permanent number wrapping project_sk (the real permanent
    key; project_id is just a URL-routing slug). See the MLS-positioning
    plan notes: don't surface project_sk or project_id as "the ID"
    anywhere a human looks -- pick one branded format and keep the other
    two as internal plumbing, or customers see three different-looking
    identifiers for the same project."""
    return f"SPX-{project_sk:06d}"


def fetch_enrichment(conn, sks: list[int]) -> dict[int, dict[str, Any]]:
    """Bulk-fetch score/timeline/provenance/news for a page of projects in
    a handful of queries keyed by project_sk, instead of one query per
    project (N+1) -- same pattern as the rest of this API's list
    endpoints. Powers the project detail page's Amazon-listing-style
    sections (see docs/PROJECT_PAGE_REDESIGN.md)."""
    if not sks:
        return {}
    out: dict[int, dict[str, Any]] = {sk: {"score": None, "events": [], "sources": [], "news": []} for sk in sks}

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT project_sk, score, value_score, recency_score, news_score "
            "FROM project_scores WHERE project_sk = ANY(%s)",
            (sks,),
        )
        for r in cur.fetchall():
            out[r["project_sk"]]["score"] = {
                "total": r["score"],
                "value": r["value_score"],
                "recency": r["recency_score"],
                "news": r["news_score"],
            }

        cur.execute(
            "SELECT project_sk, event_type, event_date, source_name, source_url "
            "FROM project_events WHERE project_sk = ANY(%s) ORDER BY event_date",
            (sks,),
        )
        for r in cur.fetchall():
            out[r["project_sk"]]["events"].append(
                {
                    "event_type": r["event_type"],
                    "event_date": r["event_date"].isoformat() if r["event_date"] else None,
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                }
            )

        cur.execute(
            "SELECT project_sk, source_name, source_url, is_primary "
            "FROM project_sources WHERE project_sk = ANY(%s)",
            (sks,),
        )
        for r in cur.fetchall():
            out[r["project_sk"]]["sources"].append(
                {
                    "source_name": r["source_name"],
                    "source_url": r["source_url"],
                    "is_primary": r["is_primary"],
                }
            )

        cur.execute(
            "SELECT project_sk, title, url, source_name, published_at "
            "FROM project_news WHERE project_sk = ANY(%s) ORDER BY published_at DESC NULLS LAST",
            (sks,),
        )
        for r in cur.fetchall():
            out[r["project_sk"]]["news"].append(
                {
                    "title": r["title"],
                    "url": r["url"],
                    "source_name": r["source_name"],
                    "published_at": r["published_at"].isoformat() if r["published_at"] else None,
                }
            )

    return out


def row_to_project(row: dict[str, Any], enrichment: dict[str, Any] | None = None) -> dict[str, Any]:
    enrichment = enrichment or {"score": None, "events": [], "sources": [], "news": []}
    return {
        "id": row["project_id"],
        "spx_id": spx_id(row["project_sk"]),
        "project_sk": row["project_sk"],
        "score": enrichment["score"],
        "timeline": enrichment["events"],
        "provenance": enrichment["sources"],
        "news": enrichment["news"],
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
        "latitude": float(row["latitude"]) if row.get("latitude") is not None else None,
        "longitude": float(row["longitude"]) if row.get("longitude") is not None else None,
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
            enrichment = fetch_enrichment(conn, [r["project_sk"] for r in rows])

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "projects": [row_to_project(r, enrichment.get(r["project_sk"])) for r in rows],
    }


@app.get("/v1/coverage")
def list_coverage(
    state: str | None = Query(default=None, min_length=2, max_length=2),
    coverage_type: str | None = Query(default=None, pattern="^(deep|thin)$"),
):
    """Backs the /coverage page -- see scripts/compute-county-coverage.py
    for how county_coverage is populated (derived from project_id prefixes,
    not a stored source column; refreshed on demand, not live per-request)."""
    clauses: list[str] = []
    params: list[Any] = []
    if state:
        clauses.append("state = %s")
        params.append(state.upper())
    if coverage_type:
        clauses.append("coverage_type = %s")
        params.append(coverage_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT state, county, project_count, sources, coverage_type, computed_at
                FROM county_coverage
                {where}
                ORDER BY project_count DESC
                """,
                params,
            )
            rows = cur.fetchall()

    return {
        "total": len(rows),
        "coverage": [
            {
                "state": r["state"],
                "county": r["county"],
                "project_count": r["project_count"],
                "sources": r["sources"] or [],
                "coverage_type": r["coverage_type"],
                "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
            }
            for r in rows
        ],
    }


@app.get("/v1/coverage/insights")
def coverage_insights():
    """Powers the Insights tab on /coverage: per-state rollup (how many
    counties total vs. covered vs. deep/thin) plus the top 3 projects (by
    estimated value, falling back to most recent) in every covered county --
    the two things needed to decide where to point the next pull script."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT state,
                       count(*) AS counties_covered,
                       count(*) FILTER (WHERE coverage_type = 'deep') AS deep,
                       count(*) FILTER (WHERE coverage_type = 'thin') AS thin,
                       sum(project_count) AS total_projects,
                       sum(delta) AS net_delta
                FROM county_coverage
                GROUP BY state
                """
            )
            state_rows = cur.fetchall()

            cur.execute(
                """
                SELECT state, county, name, status, estimated_value_usd,
                       opened_or_announced_date, project_id
                FROM (
                    SELECT p.state, p.county, p.name, p.status, p.estimated_value_usd,
                           p.opened_or_announced_date, p.project_id,
                           row_number() OVER (
                             PARTITION BY p.state, p.county
                             ORDER BY p.estimated_value_usd DESC NULLS LAST,
                                      p.opened_or_announced_date DESC NULLS LAST
                           ) AS rn
                    FROM projects p
                    WHERE p.county IS NOT NULL AND p.county != ''
                ) ranked
                WHERE rn <= 3
                ORDER BY state, county, rn
                """
            )
            top_rows = cur.fetchall()

    top_by_county: dict[str, list[dict[str, Any]]] = {}
    for r in top_rows:
        key = f"{r['state']}|{r['county']}"
        top_by_county.setdefault(key, []).append(
            {
                "id": r["project_id"],
                "name": r["name"],
                "status": r["status"],
                "estimated_value_usd": r["estimated_value_usd"],
                "opened_or_announced_date": (
                    r["opened_or_announced_date"].isoformat()
                    if r["opened_or_announced_date"]
                    else None
                ),
            }
        )

    state_summary = []
    for r in state_rows:
        state = r["state"]
        total = US_COUNTY_TOTALS.get(state)
        covered = r["counties_covered"]
        state_summary.append(
            {
                "state": state,
                "total_us_counties": total,
                "counties_covered": covered,
                "counties_uncovered": (total - covered) if total is not None else None,
                "coverage_pct": round(100 * covered / total, 1) if total else None,
                "deep": r["deep"],
                "thin": r["thin"],
                "total_projects": r["total_projects"],
                "net_delta": r["net_delta"],
            }
        )
    state_summary.sort(key=lambda s: s["coverage_pct"] or 0, reverse=True)

    return {"state_summary": state_summary, "top_projects_by_county": top_by_county}


@app.get("/v1/quality")
def list_quality(state: str | None = Query(default=None, min_length=2, max_length=2)):
    """Backs the Quality tab on /coverage -- see scripts/compute-state-quality.py
    for how state_quality is populated (field completeness + freshness per
    state, refreshed on demand, not live per-request)."""
    clauses: list[str] = []
    params: list[Any] = []
    if state:
        clauses.append("state = %s")
        params.append(state.upper())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT state, total_projects, pct_has_city, pct_has_value,
                       pct_has_contractor, pct_has_date, freshness_days, computed_at
                FROM state_quality
                {where}
                ORDER BY state
                """,
                params,
            )
            rows = cur.fetchall()

    return {
        "total": len(rows),
        "quality": [
            {
                "state": r["state"],
                "total_projects": r["total_projects"],
                "pct_has_city": float(r["pct_has_city"]),
                "pct_has_value": float(r["pct_has_value"]),
                "pct_has_contractor": float(r["pct_has_contractor"]),
                "pct_has_date": float(r["pct_has_date"]),
                "freshness_days": r["freshness_days"],
                "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
            }
            for r in rows
        ],
    }


@app.get("/v1/ops/pipeline-runs")
def list_pipeline_runs(
    workflow: str | None = Query(default=None),
    limit: int = Query(default=30, le=200),
):
    """Backs the /ops dashboard's pipeline health view -- see
    scripts/log-pipeline-run.py for how pipeline_runs gets written (one row
    per GitHub Actions run of pull-national.yml / pull-state.yml)."""
    clauses: list[str] = []
    params: list[Any] = []
    if workflow:
        clauses.append("workflow = %s")
        params.append(workflow)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, workflow, run_url, started_at, projects_before, projects_after,
                       step_outcomes, top_movers, overall_status
                FROM pipeline_runs
                {where}
                ORDER BY started_at DESC
                LIMIT %s
                """,
                [*params, limit],
            )
            rows = cur.fetchall()

            cur.execute("SELECT workflow, count(*) AS n FROM pipeline_runs GROUP BY workflow")
            run_counts = {r["workflow"]: r["n"] for r in cur.fetchall()}

    return {
        "total": len(rows),
        "run_counts": run_counts,
        "runs": [
            {
                "id": r["id"],
                "workflow": r["workflow"],
                "run_url": r["run_url"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "projects_before": r["projects_before"],
                "projects_after": r["projects_after"],
                "step_outcomes": r["step_outcomes"] or {},
                "top_movers": r["top_movers"],
                "overall_status": r["overall_status"],
            }
            for r in rows
        ],
    }


MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")
MAPBOX_MONTHLY_QUOTA = 45_000  # ~10% under the Mapbox GL JS free-tier limit


@app.get("/v1/ops/mapbox-token")
def get_mapbox_token():
    """Gatekeeper for the /map/ admin page's Mapbox GL token -- see
    db/migrations/011_mapbox_usage.sql. Every map init calls this instead
    of bundling the token at build time, so a hard monthly quota can stop
    issuing tokens before Mapbox billing kicks in. Complements (does not
    replace) URL-restricting the token itself in the Mapbox dashboard."""
    if not MAPBOX_TOKEN:
        raise HTTPException(status_code=503, detail="MAPBOX_TOKEN is not configured")

    month = time.strftime("%Y-%m", time.gmtime())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mapbox_usage (month, load_count) VALUES (%s, 1)
                ON CONFLICT (month) DO UPDATE SET load_count = mapbox_usage.load_count + 1
                RETURNING load_count
                """,
                (month,),
            )
            load_count = cur.fetchone()[0]
        conn.commit()

    if load_count > MAPBOX_MONTHLY_QUOTA:
        raise HTTPException(status_code=429, detail="Map quota exceeded for this month")

    return {"token": MAPBOX_TOKEN, "remaining": MAPBOX_MONTHLY_QUOTA - load_count}


@app.get("/v1/ops/map-points")
def map_points(
    county: str | None = Query(default=None),
    city: str | None = Query(default=None),
):
    """Backs the /map/ admin page. Lightweight -- id/name/coords/location
    only, not the full project row -- since this returns every geocoded
    project in one response rather than paginating (cheap at today's
    scale: a few hundred rows with real lat/lon, see docs/AGENT_STRATEGY.md
    plan notes on why zip filtering isn't offered here yet)."""
    clauses = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params: list[Any] = []
    if county:
        clauses.append("county = %s")
        params.append(county)
    if city:
        clauses.append("city = %s")
        params.append(city)
    where = f"WHERE {' AND '.join(clauses)}"

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT project_id, name, state, county, city, latitude, longitude
                FROM projects
                {where}
                """,
                params,
            )
            rows = cur.fetchall()

    return {
        "total": len(rows),
        "points": [
            {
                "id": r["project_id"],
                "name": r["name"],
                "state": r["state"],
                "county": r["county"],
                "city": r["city"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
            }
            for r in rows
        ],
    }


@app.get("/v1/ops/db-health")
def db_health():
    """Live connection-pool utilization -- see the POOL_MIN_CONN/MAX_CONN
    comment above for why this pool is small and retry-on-exhaustion
    rather than blocking (db-f1-micro's 25-connection ceiling)."""
    pool = _get_pool()
    # psycopg2's pool doesn't expose a public utilization API; _pool/_used
    # are the underlying lists it tracks internally (available vs
    # checked-out connections) -- reading them for an ops view is fine,
    # mutating them would not be.
    in_use = len(getattr(pool, "_used", {}))
    idle = len(getattr(pool, "_pool", []))
    return {
        "min_conn": POOL_MIN_CONN,
        "max_conn": POOL_MAX_CONN,
        "in_use": in_use,
        "idle": idle,
    }


@app.get("/v1/projects/{project_id}")
def get_project(project_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        enrichment = fetch_enrichment(conn, [row["project_sk"]])

    return row_to_project(row, enrichment.get(row["project_sk"]))
