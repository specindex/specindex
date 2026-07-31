"""SpecIndex read API — Cloud Run front for PostgreSQL."""

from __future__ import annotations

import json
import os
import smtplib
import sys
import time
import urllib.parse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, Field, field_validator

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DOCUMENTS_GCS_BUCKET = "specindex-ai-raw-documents"

# Firebase Auth (see db/migrations/021_user_profiles.sql, /v1/me/profile
# below). Replaced Clerk 2026-07-29 -- same GCP project ("specindex-ai")
# already backs Postgres/Cloud Run/Vertex, so this is one fewer auth vendor
# to run, not an additional one. verify_firebase_token checks the token's
# signature against Google's public certs, its issuer
# (https://securetoken.google.com/{project}), and its audience (the
# project id) in one call -- no service-account credential needed for
# verification itself, the same "public-key verification only" shape the
# old Clerk JWKS check had.
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")
_google_auth_request: google_auth_requests.Request | None = None

_firebase_admin_app = None


def _get_firebase_admin_auth():
    """Lazily initializes the firebase_admin SDK (separate from the
    manual google-auth token verification above, which only checks
    signatures -- this is needed for revoke_refresh_tokens, which requires
    an authenticated Admin SDK client, not just public-key verification).
    Uses Application Default Credentials -- the same Cloud Run service
    account already used for Cloud SQL/Storage, no new credential to
    provision."""
    global _firebase_admin_app
    import firebase_admin
    from firebase_admin import auth as firebase_admin_auth

    if _firebase_admin_app is None:
        _firebase_admin_app = firebase_admin.initialize_app(
            options={"projectId": FIREBASE_PROJECT_ID} if FIREBASE_PROJECT_ID else None
        )
    return firebase_admin_auth


def _get_google_auth_request() -> google_auth_requests.Request:
    global _google_auth_request
    if _google_auth_request is None:
        _google_auth_request = google_auth_requests.Request()
    return _google_auth_request


def _verify_firebase_token(request: Request) -> dict[str, Any]:
    """Verifies the bearer token as a Firebase ID token, returns the full
    claims dict. Raises 401 on anything wrong. Only wired into /v1/me/*
    endpoints -- every other endpoint stays untouched/anonymous.

    Google's public certs are cached in-process by the underlying HTTP
    transport after first fetch (same tradeoff the old Clerk JWKS client
    had) -- a cache miss is a synchronous network call that blocks the
    handling thread, accepted at this traffic level."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.removeprefix("Bearer ")
    try:
        claims = google_id_token.verify_firebase_token(
            token, _get_google_auth_request(), audience=FIREBASE_PROJECT_ID
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return claims


def require_firebase_user(request: Request) -> str:
    """FastAPI dependency returning just the Firebase user id (`sub` claim,
    aka the Firebase uid).

    Also enforces user_profiles.is_active here, not just in require_role --
    Firebase ID tokens self-expire in ~1hr and the client SDK silently
    refreshes them, so a role-only check does nothing for a deactivated
    user's still-valid token on the many endpoints that only depend on
    this function. Checking is_active at this layer makes deactivation
    take effect on the very next request instead of up to an hour later.
    No row in user_profiles yet (e.g. first request before onboarding)
    is treated as active -- there's nothing to deactivate yet."""
    uid = _verify_firebase_token(request)["sub"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT is_active FROM user_profiles WHERE firebase_uid = %s", (uid,))
        row = cur.fetchone()
    if row is not None and row[0] is False:
        raise HTTPException(status_code=403, detail="Account deactivated")
    return uid


# `next build` (generateStaticParams, getStats/getSampleProjects at build
# time -- see lib/projects.ts) reads bulk project data server-side with no
# Firebase session to attach, so a plain require_firebase_user gate on
# /v1/projects would 401 the build itself. SPECINDEX_BUILD_TOKEN is a
# second, separate credential (not a user token) the build environment
# sends instead; either it or a valid Firebase session satisfies this
# dependency. Rotate by changing the env var on Cloud Run + the CI build
# secret together -- there's no per-token revocation, it's a single shared
# static string.
SPECINDEX_BUILD_TOKEN = os.environ.get("SPECINDEX_BUILD_TOKEN", "")


def require_firebase_user_or_build_token(request: Request) -> str:
    """FastAPI dependency: accepts either a valid Firebase session (browser,
    signed-in user) or the build-time shared secret via X-Build-Token
    (next build's server-side data fetches). Returns the Firebase uid, or
    the literal string "build" when authorized via the build token, so
    callers that don't care which can just depend on this."""
    build_token = request.headers.get("x-build-token", "")
    if SPECINDEX_BUILD_TOKEN and build_token and build_token == SPECINDEX_BUILD_TOKEN:
        return "build"
    return require_firebase_user(request)


def require_firebase_user_with_email(request: Request) -> tuple[str, str]:
    """FastAPI dependency returning (firebase_uid, email). Firebase ID
    tokens carry `email` natively for any provider that returns one (Google
    sign-in, email/password, etc.) -- no dashboard-configured claims
    template needed, unlike Clerk."""
    claims = _verify_firebase_token(request)
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Token missing email claim")
    return claims["sub"], email


# /ops/crm (docs/PRD_SIGNUP_CRM.md Section 3) renders real names, emails,
# and phone numbers -- unlike the rest of /v1/ops/*, which is
# unauthenticated-but-noindex because it exposes only operational metadata
# nobody could misuse. A page rendering real PII needs actual auth, not
# just an unlinked URL -- this was a specific finding from an earlier
# design review of this feature, not a style choice. Comma-separated env
# var rather than a DB table: the allowlist is expected to stay tiny
# (founder + maybe one or two people), and changing it via a Cloud Run env
# var update is simpler than building admin-user management for a list
# this short.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def require_admin_user(request: Request) -> str:
    """FastAPI dependency: valid Firebase session AND the caller's email is
    on the ADMIN_EMAILS allowlist. Verifies the token itself (does not
    trust a prior require_firebase_user_with_email call elsewhere in the
    dependency chain) so this check can't be bypassed by hitting this
    endpoint directly. Returns the email on success; raises 403 (not 401)
    for a valid-but-non-admin session so the two failure modes are
    distinguishable in logs.

    Superseded by require_role() below for new endpoints -- kept only
    because ADMIN_EMAILS is still the bootstrap seed data for
    user_staff_roles (see db/migrations/027_user_staff_roles.sql). Don't
    add new callers of this function; use require_role("super_admin")
    instead so authorization lives in one place (Postgres), not two."""
    _uid, email = require_firebase_user_with_email(request)
    if email.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Not authorized")
    return email


def require_role(*allowed: str):
    """Factory: FastAPI dependency requiring one of the given
    user_staff_roles rows, on top of a valid (and active -- see
    require_firebase_user) Firebase session. Verifies the token itself
    rather than trusting an upstream dependency ran first, same
    non-bypassable-by-hitting-the-endpoint-directly guarantee
    require_admin_user already documented."""

    def _dep(request: Request) -> str:
        firebase_uid = require_firebase_user(request)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM user_staff_roles WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            roles = {r[0] for r in cur.fetchall()}
        if not roles & set(allowed):
            raise HTTPException(status_code=403, detail="Not authorized")
        return firebase_uid

    return _dep


# API-key auth foundation (docs/architecture-2026/04-productization.md) --
# the shared prerequisite for MCP access and Enterprise billing. Not wired
# into any endpoint yet; this is the primitive other work builds on.
def _hash_api_key(raw_key: str) -> str:
    import hashlib

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def require_api_key(request: Request) -> str:
    """FastAPI dependency: validates an X-Api-Key header against api_keys
    (hashed, never stored in plaintext). Returns the owning firebase_uid.
    Records last_used_at best-effort -- a logging failure must never fail
    the actual request."""
    raw_key = request.headers.get("x-api-key", "")
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing X-Api-Key header")
    key_hash = _hash_api_key(raw_key)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, firebase_uid FROM api_keys WHERE key_hash = %s AND revoked_at IS NULL",
            (key_hash,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        key_id, firebase_uid = row
        try:
            cur.execute("UPDATE api_keys SET last_used_at = now() WHERE id = %s", (key_id,))
            cur.execute(
                "INSERT INTO api_key_usage (api_key_id, endpoint) VALUES (%s, %s)",
                (key_id, request.url.path),
            )
            conn.commit()
        except Exception:  # noqa: BLE001 -- usage logging must never fail the request
            conn.rollback()
    return firebase_uid


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


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
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.post("/v1/me/api-keys")
def create_api_key(body: ApiKeyCreate, firebase_uid: str = Depends(require_firebase_user)):
    """Returns the raw key exactly once -- it is not recoverable from the
    database afterward, only key_prefix is kept for the customer to
    identify it later in a list view."""
    import secrets

    raw_key = f"spx_{secrets.token_urlsafe(32)}"
    key_hash = _hash_api_key(raw_key)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_keys (firebase_uid, key_hash, key_prefix, name) VALUES (%s, %s, %s, %s) RETURNING id",
                (firebase_uid, key_hash, raw_key[:12], body.name),
            )
            key_id = cur.fetchone()[0]
        conn.commit()
    return {"id": key_id, "api_key": raw_key, "name": body.name}


@app.get("/v1/me/api-keys")
def list_api_keys(firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, key_prefix, name, created_at, last_used_at, revoked_at "
                "FROM api_keys WHERE firebase_uid = %s ORDER BY created_at DESC",
                (firebase_uid,),
            )
            rows = cur.fetchall()
    return {"keys": rows}


@app.delete("/v1/me/api-keys/{key_id}")
def revoke_api_key(key_id: int, firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE api_keys SET revoked_at = now() WHERE id = %s AND firebase_uid = %s AND revoked_at IS NULL",
                (key_id, firebase_uid),
            )
        conn.commit()
    return {"ok": True}


_pool: psycopg2.pool.ThreadedConnectionPool | None = None

# Lazy singleton -- only imported/constructed the first time a document is
# actually requested, so the common request path (project reads) doesn't
# pay for the google-cloud-storage import or a client handshake it never
# uses.
_gcs_bucket = None


def _get_gcs_bucket():
    global _gcs_bucket
    if _gcs_bucket is None:
        from google.cloud import storage

        _gcs_bucket = storage.Client().bucket(DOCUMENTS_GCS_BUCKET)
    return _gcs_bucket


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
    out: dict[int, dict[str, Any]] = {
        sk: {"score": None, "events": [], "sources": [], "news": [], "document_count": 0} for sk in sks
    }

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

        cur.execute(
            "SELECT project_sk, document_count FROM project_documents WHERE project_sk = ANY(%s)",
            (sks,),
        )
        for r in cur.fetchall():
            out[r["project_sk"]]["document_count"] = r["document_count"]

    return out


def row_to_project(row: dict[str, Any], enrichment: dict[str, Any] | None = None) -> dict[str, Any]:
    enrichment = enrichment or {"score": None, "events": [], "sources": [], "news": [], "document_count": 0}
    return {
        "id": row["project_id"],
        "spx_id": spx_id(row["project_sk"]),
        "project_sk": row["project_sk"],
        "score": enrichment["score"],
        "timeline": enrichment["events"],
        "provenance": enrichment["sources"],
        "news": enrichment["news"],
        "document_count": enrichment["document_count"],
        "has_documents": enrichment["document_count"] > 0,
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
        "first_seen_at": (
            row["first_seen_at"].isoformat() if row.get("first_seen_at") else None
        ),
    }


# Public fields for an anonymous/build-time view of a single project detail
# page (app/projects/[id]/page.tsx, ~200 pages pre-rendered at `next build`
# with no user session available). Everything else -- exact value, square
# footage, owner/architect/GC names, brand mentions, sources, exact
# lat/lng, news, documents -- is the reason someone signs in, not SEO
# copy, so it's dropped here rather than baked into public static HTML.
_PUBLIC_TEASER_FIELDS = (
    "id", "spx_id", "name", "state", "city", "county", "status",
    "project_type", "description", "opened_or_announced_date",
)


def _to_public_teaser(detail: dict[str, Any]) -> dict[str, Any]:
    return {k: detail.get(k) for k in _PUBLIC_TEASER_FIELDS} | {"gated": True}


def _has_real_firebase_session(request: Request) -> bool:
    """True only for an actual signed-in browser session -- NOT the build
    token, which authorizes bulk build-time reads but should still only
    ever see the public teaser (the whole point is the static HTML build
    output must not contain gated fields)."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return False
    try:
        _verify_firebase_token(request)
        return True
    except HTTPException:
        return False


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


def _project_filter_clauses(
    state: str | None,
    status: str | None,
    project_type: str | None,
    county: str | None,
    category: str | None,
    year: int | None,
    q: str | None,
    new_since_days: int | None,
    has_documents: bool | None = None,
    document_type: str | None = None,
) -> tuple[list[str], list[Any]]:
    """Shared WHERE-clause builder for /v1/projects and /v1/projects/map-points
    -- both need the same filter set (the map is meant to show pins bounded
    to whatever the list is currently filtered to, not the full corpus)."""
    clauses: list[str] = []
    params: list[Any] = []

    if state:
        codes = [s.strip().upper() for s in state.split(",") if s.strip()]
        if codes:
            clauses.append("p.state = ANY(%s)")
            params.append(codes)
    if status:
        clauses.append("p.status = %s")
        params.append(status)
    if project_type:
        clauses.append("p.project_type = %s")
        params.append(project_type)
    if county:
        clauses.append("p.county = %s")
        params.append(county)
    if category:
        clauses.append(
            "EXISTS (SELECT 1 FROM jsonb_array_elements_text(p.competitor_watch) elem WHERE elem ILIKE %s)"
        )
        params.append(f"%{category}%")
    if year:
        clauses.append("EXTRACT(YEAR FROM p.opened_or_announced_date) = %s")
        params.append(year)
    if q:
        clauses.append(
            "(p.name ILIKE %s OR p.city ILIKE %s OR p.owner ILIKE %s OR "
            "p.general_contractor ILIKE %s OR p.description ILIKE %s)"
        )
        params.extend([f"%{q}%"] * 5)
    if new_since_days:
        clauses.append("p.first_seen_at >= now() - make_interval(days => %s)")
        params.append(new_since_days)
    if has_documents is not None:
        exists = "EXISTS" if has_documents else "NOT EXISTS"
        clauses.append(
            f"{exists} (SELECT 1 FROM project_documents pd WHERE pd.project_sk = p.project_sk AND pd.has_documents)"
        )
    if document_type:
        # Deterministic, keyword-based categories from
        # compute-project-documents.py's classify_document_type() --
        # 'other' is a real, meaningful bucket (uncategorized documents),
        # not excluded here.
        clauses.append(
            "EXISTS (SELECT 1 FROM project_document_files pdf "
            "WHERE pdf.project_sk = p.project_sk AND pdf.document_type = %s)"
        )
        params.append(document_type)

    return clauses, params


@app.get("/v1/projects")
def list_projects(
    state: str | None = Query(default=None, description="Comma-separated state codes, e.g. NC,SC,VA"),
    status: str | None = None,
    project_type: str | None = None,
    county: str | None = None,
    category: str | None = Query(default=None, description="Matches any entry in competitor_watch"),
    year: int | None = None,
    q: str | None = Query(default=None, description="Free-text search across name/city/owner/GC/description"),
    new_since_days: int | None = Query(
        default=None, ge=1, le=365, description="Only projects first seen in the last N days"
    ),
    has_documents: bool | None = Query(
        default=None, description="True = only projects with attached documents, False = only without"
    ),
    document_type: str | None = Query(
        default=None,
        description=(
            "Filter to projects with at least one document of this type: "
            "specifications, drawings_plans, structural_engineering, "
            "staff_report, meeting_agenda, permit_application, other"
        ),
    ),
    sort: str = Query(default="score", pattern="^(score|name|value|recency)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _auth: str = Depends(require_firebase_user_or_build_token),
):
    clauses, params = _project_filter_clauses(
        state, status, project_type, county, category, year, q, new_since_days, has_documents, document_type
    )

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_by = {
        "score": "COALESCE(ps.score, 0) DESC, p.name ASC",
        "name": "p.name ASC",
        "value": "p.estimated_value_usd DESC NULLS LAST, p.name ASC",
        "recency": "p.opened_or_announced_date DESC NULLS LAST, p.name ASC",
    }[sort]

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT count(*) AS n FROM projects p {where}",
                params,
            )
            total = int(cur.fetchone()["n"])

            cur.execute(
                f"""
                SELECT p.*
                FROM projects p
                LEFT JOIN project_scores ps ON ps.project_sk = p.project_sk
                {where}
                ORDER BY {order_by}
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


@app.get("/v1/projects/facets")
def project_facets(state: str | None = Query(default=None, description="Comma-separated state codes")):
    """Distinct filter values for the /projects search UI -- lets the
    frontend populate state/county/type/category/year dropdowns without
    fetching the full corpus (the whole point of paginating list_projects
    above). county/category/year are scoped to the selected state(s) when
    provided, matching how the old client-side-filtered UI narrowed county
    options by state."""
    state_clause = ""
    state_params: list[Any] = []
    if state:
        codes = [s.strip().upper() for s in state.split(",") if s.strip()]
        if codes:
            state_clause = "WHERE state = ANY(%s)"
            state_params = [codes]

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT state FROM projects WHERE state IS NOT NULL ORDER BY state")
            states = [r["state"] for r in cur.fetchall()]

            cur.execute(
                f"SELECT DISTINCT county FROM projects {state_clause} "
                f"{'AND' if state_clause else 'WHERE'} county IS NOT NULL AND county != '' ORDER BY county",
                state_params,
            )
            counties = [r["county"] for r in cur.fetchall()]

            cur.execute("SELECT DISTINCT project_type FROM projects WHERE project_type IS NOT NULL ORDER BY project_type")
            types = [r["project_type"] for r in cur.fetchall()]

            cur.execute("SELECT DISTINCT status FROM projects WHERE status IS NOT NULL ORDER BY status")
            statuses = [r["status"] for r in cur.fetchall()]

            cur.execute(
                "SELECT DISTINCT elem AS category FROM projects, "
                "jsonb_array_elements_text(competitor_watch) elem ORDER BY category"
            )
            categories = [r["category"] for r in cur.fetchall()]

            cur.execute(
                "SELECT DISTINCT EXTRACT(YEAR FROM opened_or_announced_date)::int AS year "
                "FROM projects WHERE opened_or_announced_date IS NOT NULL ORDER BY year DESC"
            )
            years = [r["year"] for r in cur.fetchall()]

    return {
        "states": states,
        "counties": counties,
        "project_types": types,
        "statuses": statuses,
        "categories": categories,
        "years": years,
    }


@app.get("/v1/projects/map-points")
def project_map_points(
    state: str | None = Query(default=None, description="Comma-separated state codes, e.g. NC,SC,VA"),
    status: str | None = None,
    project_type: str | None = None,
    county: str | None = None,
    category: str | None = Query(default=None, description="Matches any entry in competitor_watch"),
    year: int | None = None,
    q: str | None = Query(default=None, description="Free-text search across name/city/owner/GC/description"),
    new_since_days: int | None = Query(default=None, ge=1, le=365),
    has_documents: bool | None = Query(default=None),
    document_type: str | None = Query(default=None),
    _auth: str = Depends(require_firebase_user_or_build_token),
):
    """Customer-facing equivalent of /v1/ops/map-points -- bounded
    to whatever filters the visitor currently has set on /projects rather
    than returning every geocoded project (that endpoint stays internal,
    used only by the Mapbox GL admin map at /map/). Lightweight rows only,
    same as the ops version, since a map pin doesn't need the full project
    payload."""
    clauses, params = _project_filter_clauses(
        state, status, project_type, county, category, year, q, new_since_days, has_documents, document_type
    )
    clauses += ["p.latitude IS NOT NULL", "p.longitude IS NOT NULL"]
    where = f"WHERE {' AND '.join(clauses)}"

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT p.project_id, p.project_sk, p.name, p.state, p.county, p.city,
                       p.latitude, p.longitude, p.status, p.estimated_value_usd,
                       COALESCE(ps.score, 0) AS score
                FROM projects p
                LEFT JOIN project_scores ps ON ps.project_sk = p.project_sk
                {where}
                ORDER BY score DESC
                LIMIT 2000
                """,
                params,
            )
            rows = cur.fetchall()

    return {
        "total": len(rows),
        "points": [
            {
                "id": r["project_id"],
                "spx_id": spx_id(r["project_sk"]),
                "name": r["name"],
                "state": r["state"],
                "county": r["county"],
                "city": r["city"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "status": r["status"],
                "estimated_value_usd": r["estimated_value_usd"],
                "score": r["score"],
            }
            for r in rows
        ],
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


@app.get("/v1/ops/crm")
def list_crm_contacts(_admin: str = Depends(require_role("support_admin", "super_admin"))):
    """Read-only -- docs/PRD_SIGNUP_CRM.md deliberately cuts a custom
    editable UI in favor of a database GUI/psql directly against Cloud SQL
    for stage/notes updates until real lead volume justifies more. Sorting/
    filtering is left to the frontend -- table size here is tiny (pre-
    revenue), so a server-side query-param API isn't worth the surface area
    yet."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT contact_key, name, email, company, phone, role_title,
                       territory_states, categories, lifecycle_stage, lead_source,
                       demo_request_source, demo_requested_at, onboarded_at, notes,
                       is_active, last_login_at
                FROM crm_contacts
                ORDER BY COALESCE(onboarded_at, demo_requested_at) DESC NULLS LAST
                """
            )
            rows = cur.fetchall()
    return {"contacts": rows}


def _resolve_org_id(cur, firebase_uid: str, create_if_missing: bool = False) -> int | None:
    """Real `organizations` row (migration 040) -- NOT the earlier "org_id
    = owner's own firebase_uid" shortcut migration 039 originally shipped
    with, which a same-day Gemini review flagged as breaking on owner
    account deletion, ownership transfer, and tier downgrade (an orphaned
    firebase_uid used as a foreign key has no row of its own to update).
    A member who accepted an invite is looked up via org_members; an owner
    who doesn't have an organizations row yet gets one created lazily on
    their first invite (create_if_missing), not eagerly for every user --
    most users never invite anyone and shouldn't get a row for it."""
    cur.execute(
        "SELECT org_id FROM org_members WHERE firebase_uid = %s AND role = 'member'",
        (firebase_uid,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("SELECT id FROM organizations WHERE owner_uid = %s", (firebase_uid,))
    row = cur.fetchone()
    if row:
        return row[0]
    if not create_if_missing:
        return None

    cur.execute(
        "INSERT INTO organizations (owner_uid) VALUES (%s) RETURNING id", (firebase_uid,)
    )
    return cur.fetchone()[0]


class OrgInviteRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_looks_like_email(cls, v: str) -> str:
        if "@" not in v or " " in v:
            raise ValueError("not a valid email address")
        return v


def _send_org_invite_email(to_email: str, invite_token: str) -> str | None:
    if not EMAIL_SMTP_USERNAME or not EMAIL_SMTP_PASSWORD:
        return "EMAIL_SMTP_USERNAME/PASSWORD not configured"
    try:
        msg = EmailMessage()
        msg["Subject"] = "You've been invited to a SpecIndex team"
        msg["From"] = EMAIL_SMTP_USERNAME
        msg["To"] = to_email
        msg.set_content(
            "You've been invited to join a team on SpecIndex.\n\n"
            f"Accept your invite: https://specindex.ai/account/team/accept?token={invite_token}\n"
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(EMAIL_SMTP_USERNAME, EMAIL_SMTP_PASSWORD)
            smtp.send_message(msg)
        return None
    except Exception as e:  # noqa: BLE001 -- see _send_contact_notification
        return str(e)


@app.get("/v1/org/members")
def list_org_members(firebase_uid: str = Depends(require_firebase_user)):
    """Team roster -- the caller's org (their own org if they're an owner
    who has invited before, or the org they accepted an invite into). A
    caller with no organizations row yet and no accepted invite has no
    team -- returns an empty roster rather than lazily creating one just
    to view an empty page."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            org_id = _resolve_org_id(cur, firebase_uid)
            if org_id is None:
                return {"org_id": None, "members": []}
            cur.execute(
                """
                SELECT id, email, role, invited_at, joined_at,
                       (firebase_uid IS NOT NULL) AS accepted
                FROM org_members
                WHERE org_id = %s
                ORDER BY invited_at
                """,
                (org_id,),
            )
            members = cur.fetchall()
    return {"org_id": org_id, "members": members}


@app.post("/v1/org/invite")
def invite_org_member(
    body: OrgInviteRequest, firebase_uid: str = Depends(require_firebase_user)
):
    """Only the org owner can invite -- a member (role='member' in
    org_members) does not itself own an org to invite into. Creates the
    caller's organizations row on first use (see _resolve_org_id)."""
    import secrets

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT 1 FROM org_members WHERE firebase_uid = %s AND role = 'member'",
                (firebase_uid,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=403, detail="Only the team owner can invite members")

            org_id = _resolve_org_id(cur, firebase_uid, create_if_missing=True)
            invite_token = secrets.token_urlsafe(24)
            cur.execute(
                """
                INSERT INTO org_members (org_id, email, role, invited_by, invite_token)
                VALUES (%s, %s, 'member', %s, %s)
                ON CONFLICT (org_id, email) DO UPDATE SET
                    invite_token = EXCLUDED.invite_token,
                    invited_at = now()
                RETURNING id
                """,
                (org_id, body.email, firebase_uid, invite_token),
            )
            member_id = cur.fetchone()["id"]
        conn.commit()

    email_error = _send_org_invite_email(body.email, invite_token)
    return {"id": member_id, "email_sent": email_error is None, "email_error": email_error}


@app.post("/v1/org/accept")
def accept_org_invite(
    invite_token: str, firebase_uid: str = Depends(require_firebase_user)
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE org_members
                SET firebase_uid = %s, joined_at = now(), invite_token = NULL
                WHERE invite_token = %s AND firebase_uid IS NULL
                RETURNING org_id
                """,
                (firebase_uid, invite_token),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Invite not found or already accepted")
        conn.commit()
    return {"org_id": row[0]}


@app.delete("/v1/org/members/{member_id}")
def remove_org_member(member_id: int, firebase_uid: str = Depends(require_firebase_user)):
    """Only the org owner can remove a member -- resolves the caller's own
    organizations row first rather than comparing against firebase_uid
    directly (that comparison was only ever correct under the old
    org_id-is-a-uid shortcut, now replaced by migration 040)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM organizations WHERE owner_uid = %s", (firebase_uid,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Member not found")
            cur.execute(
                "DELETE FROM org_members WHERE id = %s AND org_id = %s AND role = 'member'",
                (member_id, row[0]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Member not found")
        conn.commit()
    return {"removed": True}


@app.get("/v1/ops/leads")
def list_leads(_admin: str = Depends(require_role("support_admin", "super_admin"))):
    """lead_scores (migration 038) joined onto crm_contacts, sorted by score
    -- docs/architecture-2026/03-growth.md P3. Scores are precomputed by
    scripts/compute-lead-scores.py, not computed on request."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.contact_key, c.name, c.email, c.company, c.lifecycle_stage,
                       c.demo_requested_at, c.onboarded_at,
                       s.score, s.intent_score, s.pipeline_depth_score,
                       s.engagement_score, s.territory_score, s.recency_score,
                       s.computed_at
                FROM lead_scores s
                JOIN crm_contacts c ON c.contact_key = s.contact_key
                ORDER BY s.score DESC
                """
            )
            rows = cur.fetchall()
    return {"leads": rows}


@app.get("/v1/ops/customer/{firebase_uid}")
def view_as_customer(
    firebase_uid: str, _admin: str = Depends(require_role("support_admin", "super_admin"))
):
    """Read-only 'view as customer' query path (docs/architecture-2026/
    02-identity-portals.md Phase 4 -- "explicitly praised as an excellent
    security control" in that doc's Gemini review, versus live impersonation
    tokens). Deliberately does NOT mint a real session for this user or
    return anything that would let the caller act as them (no auth token,
    no write access) -- it's a read query an admin runs, not a login.
    Real short-lived createCustomToken-based impersonation is P3, and only
    if this read-only view proves insufficient."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT firebase_uid, email, company, territory_states, categories,
                       full_name, phone, role_title, lead_source, lifecycle_stage,
                       notes, onboarded_at, created_at, subscription_tier, is_active
                FROM user_profiles
                WHERE firebase_uid = %s
                """,
                (firebase_uid,),
            )
            profile = cur.fetchone()
            if not profile:
                raise HTTPException(status_code=404, detail="No profile found for this user")

            cur.execute(
                """
                SELECT t.stage, t.note, t.created_at, t.updated_at,
                       p.project_id, p.name, p.state, p.status
                FROM user_tracked_projects t
                JOIN projects p ON p.project_sk = t.project_sk
                WHERE t.firebase_uid = %s
                ORDER BY t.updated_at DESC
                """,
                (firebase_uid,),
            )
            tracked = cur.fetchall()

    return {"profile": profile, "tracked_projects": tracked}


def _deactivate_account(firebase_uid: str) -> dict:
    """Shared by the admin ops action and the self-service delete-account
    endpoint below. Sets user_profiles.is_active = false (already enforced
    on every request by require_firebase_user, docs/architecture-2026/
    02-identity-portals.md) AND revokes the user's Firebase refresh tokens,
    so their still-valid ID token can't be silently refreshed into a new
    one either -- belt-and-suspenders: is_active alone already blocks our
    API, this additionally kills their Firebase session itself.

    Also revokes any live API keys (migration 031) -- caught by a Gemini
    review pass: deactivating a user only through Firebase/is_active left
    their API keys (a separate auth path, require_api_key) still fully
    functional, since require_api_key never checks user_profiles.is_active
    at all. api_keys.revoked_at already existed and require_api_key already
    checks it, so this is just wiring the existing revoke path in, not new
    schema.

    Refuses to deactivate an org owner with active members (409) -- a
    third review pass flagged that deactivating an org's owner would
    otherwise leave the organization headless (no one able to manage the
    roster or resolve billing) while member rows silently keep pointing at
    it. Ownership must be transferred (or members removed) first; this
    endpoint deliberately does not do that automatically, since picking a
    new owner is a business decision, not a safe default to guess at.

    This is a soft delete (is_active=false), not a row-level DELETE -- no
    hard-delete exists anywhere in this codebase yet. Matches the existing
    admin-side deactivation pattern rather than introducing a second,
    inconsistent deletion model; a real data-erasure pass (e.g. for a
    formal privacy/GDPR request) is separate, deliberate work, not
    something to bundle into a self-service button."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.id FROM organizations o
                WHERE o.owner_uid = %s
                  AND EXISTS (SELECT 1 FROM org_members m WHERE m.org_id = o.id AND m.role = 'member')
                """,
                (firebase_uid,),
            )
            if cur.fetchone() is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This user owns a team with active members -- transfer ownership or remove members before deactivating",
                )

            cur.execute(
                "UPDATE user_profiles SET is_active = false WHERE firebase_uid = %s RETURNING firebase_uid",
                (firebase_uid,),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="No profile found for this user")
            cur.execute(
                "UPDATE api_keys SET revoked_at = now() WHERE firebase_uid = %s AND revoked_at IS NULL",
                (firebase_uid,),
            )
        conn.commit()

    try:
        _get_firebase_admin_auth().revoke_refresh_tokens(firebase_uid)
        revoked = True
    except Exception:  # noqa: BLE001 -- deactivation (the DB write above) already succeeded either way
        revoked = False

    return {"deactivated": True, "tokens_revoked": revoked}


@app.post("/v1/ops/customer/{firebase_uid}/deactivate")
def deactivate_customer(
    firebase_uid: str, _admin: str = Depends(require_role("support_admin", "super_admin"))
):
    return _deactivate_account(firebase_uid)


@app.post("/v1/me/delete-account")
def delete_own_account(firebase_uid: str = Depends(require_firebase_user)):
    """Self-service equivalent of deactivate_customer above, scoped to the
    caller's own account only -- firebase_uid comes from the verified
    token (require_firebase_user), never from a request body/path param,
    so a signed-in user can only ever deactivate themselves, not someone
    else's account."""
    return _deactivate_account(firebase_uid)


@app.post("/v1/ops/customer/{firebase_uid}/reactivate")
def reactivate_customer(
    firebase_uid: str, _admin: str = Depends(require_role("support_admin", "super_admin"))
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_profiles SET is_active = true WHERE firebase_uid = %s RETURNING firebase_uid",
                (firebase_uid,),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="No profile found for this user")
        conn.commit()
    return {"reactivated": True}


def fetch_enrichment_detail(conn, sk: int) -> dict[str, Any]:
    """Full project_enrichment rows grouped by section, for the detail page
    only -- not included in the bulk list response (fetch_enrichment above)
    since list pages don't render CSI scope/team/permits/contacts text and
    fetching it for every row on every page load would be wasted work.

    Also includes checked_at from project_enrichment_checks -- a real,
    already-written timestamp of when the pipeline last ran against this
    project (whether or not that run found anything new), not a fabricated
    "last verified" claim -- the detail page previously had no freshness
    indicator at all despite the design artifact it's matching having one.
    """
    sections: dict[str, Any] = {
        "executive_brief": [], "csi_scope": [], "team": [], "permit": [], "contact": [],
        "checked_at": None,
    }
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT section, field_key, field_label, field_value, confidence, sources "
            "FROM project_enrichment WHERE project_sk = %s ORDER BY id",
            (sk,),
        )
        for r in cur.fetchall():
            sections.setdefault(r["section"], []).append(
                {
                    "field_key": r["field_key"],
                    "label": r["field_label"],
                    "value": r["field_value"],
                    "confidence": r["confidence"],
                    "sources": r["sources"],
                }
            )
        cur.execute(
            "SELECT checked_at FROM project_enrichment_checks WHERE project_sk = %s",
            (sk,),
        )
        checked = cur.fetchone()
        if checked and checked["checked_at"]:
            sections["checked_at"] = checked["checked_at"].isoformat()
    return sections


def fetch_document_files(conn, sk: int, base_url: str) -> list[dict[str, Any]]:
    """`url` here is what the frontend actually links to -- our own
    /v1/documents/{id} proxy when the document has been through
    scripts/fetch-and-store-documents.py (gcs_path set), falling back to
    the original external URL for documents not yet migrated to that
    pipeline. Either way the frontend just links to `url` with no branching
    of its own -- the resolution happens here."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, title, url, content_type, document_type, gcs_path FROM project_document_files "
            "WHERE project_sk = %s ORDER BY title",
            (sk,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if r.pop("gcs_path", None):
            r["url"] = f"{base_url}v1/documents/{r.pop('id')}"
        else:
            r.pop("id", None)
    return rows


@app.get("/v1/projects/{project_id}")
def get_project(project_id: str, request: Request):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        enrichment = fetch_enrichment(conn, [row["project_sk"]])
        detail = row_to_project(row, enrichment.get(row["project_sk"]))
        detail["enrichment"] = fetch_enrichment_detail(conn, row["project_sk"])
        # request.base_url reports the scheme Starlette sees on the
        # connection *inside* Cloud Run, which is plain HTTP -- TLS is
        # terminated at Cloud Run's edge and forwarded internally over
        # HTTP, so trusting it directly produces http:// links from an
        # https-only service. X-Forwarded-Proto (set by Cloud Run's
        # proxy) has the real client-facing scheme.
        signed_in = _has_real_firebase_session(request)
        if not signed_in:
            return _to_public_teaser(detail)

        proto = request.headers.get("x-forwarded-proto", "https")
        host = request.headers.get("host", request.url.netloc)
        base_url = f"{proto}://{host}/"
        detail["documents"] = fetch_document_files(conn, row["project_sk"], base_url)

    return detail


@app.get("/v1/documents/{document_id}")
def get_document(document_id: int):
    """Streams a GCS-stored document straight through Cloud Run -- not a
    signed-URL redirect, since the service account has roles/editor but
    not iam.serviceAccounts.signBlob (would need an extra IAM grant to
    self-impersonate for V4 signing). Proxying works today with existing
    permissions; revisit as a scaling optimization once document
    traffic/file sizes justify avoiding the extra egress hop through the
    API. This is also the seam a future paid document API would gate
    (auth/rate-limiting/usage tracking), without touching how documents
    are stored -- see scripts/fetch-and-store-documents.py."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT title, content_type, gcs_path FROM project_document_files WHERE id = %s",
                (document_id,),
            )
            row = cur.fetchone()
    if not row or not row["gcs_path"]:
        raise HTTPException(status_code=404, detail="Document not found")

    blob = _get_gcs_bucket().blob(row["gcs_path"])
    try:
        data = blob.download_as_bytes()
    except Exception as e:  # noqa: BLE001 -- surface as a clean 404, not a 500 stack trace
        raise HTTPException(status_code=404, detail="Document not found in storage") from e

    # HTTP headers are Latin-1 only -- most real document titles here
    # (scraped from real pages) contain characters like em dashes that
    # aren't Latin-1-safe, so a plain filename="..." 500s. ASCII fallback
    # for old clients, RFC 5987 filename* for everything else.
    ascii_title = row["title"].encode("ascii", "replace").decode("ascii")
    encoded_title = urllib.parse.quote(row["title"])
    return Response(
        content=data,
        media_type=row["content_type"] or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename=\"{ascii_title}\"; filename*=UTF-8''{encoded_title}"
        },
    )


# ---------------------------------------------------------------------------
# Gemini-grounded "ask" endpoints -- /v1/projects/{id}/ask (one project) and
# /v1/me/ask (everything in the signed-in user's territory). Deliberately
# NOT the search-grounded google_search tool used by
# scripts/enrich-project-details.py -- that pipeline is for *discovering*
# facts about a project from the open web; this is for *answering questions
# about what's already in our own database*, so the only context handed to
# the model is real rows pulled from Postgres. The system prompt tells it
# to say so rather than guess when the answer isn't in that context, so a
# question about something SpecIndex doesn't track (e.g. "what's the
# subcontractor's phone number") gets an honest "not in our data" instead of
# a fabricated-sounding answer.
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or "specindex-ai"
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
GEMINI_ASK_MODEL = "gemini-2.5-flash"

_genai_client = None


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client(
            vertexai=True, project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION
        )
    return _genai_client


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


def _ask_gemini(context: str, question: str) -> str:
    from google.genai import types

    prompt = (
        "You are SpecIndex's project data assistant. Answer the user's question using ONLY "
        "the project data below -- do not use outside knowledge and do not search the web. "
        "If the answer isn't in the data, say plainly that SpecIndex doesn't have that "
        "information yet rather than guessing. Be concise (2-4 sentences unless the question "
        "asks for a list).\n\n"
        f"--- PROJECT DATA ---\n{context}\n--- END PROJECT DATA ---\n\n"
        f"Question: {question}"
    )
    client = _get_genai_client()
    resp = client.models.generate_content(
        model=GEMINI_ASK_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return (resp.text or "").strip()


def _log_ask(conn, firebase_uid: str, scope: str, question: str, answer: str, project_id: str | None = None) -> None:
    """Best-effort -- a logging failure must never fail the actual answer
    that's already been generated and is about to be returned to the
    user. Also the shared write path the MCP server's ask_about_territory
    tool (P2) reuses, so usage is metered once, not twice."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ask_log (firebase_uid, scope, project_id, question, answer) "
                "VALUES (%s, %s, %s, %s, %s)",
                (firebase_uid, scope, project_id, question, answer),
            )
        conn.commit()
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] ask_log insert failed: {e}", file=sys.stderr)


def _project_ask_context(conn, project_id: str) -> tuple[str, dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    enrichment = fetch_enrichment(conn, [row["project_sk"]])
    project = row_to_project(row, enrichment.get(row["project_sk"]))
    project["enrichment"] = fetch_enrichment_detail(conn, row["project_sk"])

    lines = [
        f"Name: {project['name']}",
        f"Location: {project['city']}, {project['county']} County, {project['state']}",
        f"Status: {project['status']} ({project['project_type']})",
        f"Estimated value: {project['estimated_value_usd']}",
        f"Square footage: {project['square_footage']}",
        f"Owner: {project['owner'] or 'not reported'}",
        f"Architect: {project['architect'] or 'not reported'}",
        f"General contractor: {project['general_contractor'] or 'not reported'}",
        f"Description: {project['description']}",
        f"Key specs: {', '.join(project['key_specs']) or 'none reported'}",
        f"Mentioned brands: {', '.join(project['mentioned_brands']) or 'none reported'}",
        f"Priority score: {project['score']['total'] if project['score'] else 'not scored'}/100",
    ]
    enr = project.get("enrichment") or {}
    for fact in (enr.get("executive_brief") or [])[:15]:
        lines.append(f"Executive brief -- {fact.get('label', '')}: {fact.get('value', '')}")
    for fact in (enr.get("csi_scope") or [])[:15]:
        lines.append(f"CSI scope -- {fact.get('label', '')}: {fact.get('value', '')}")
    for fact in (enr.get("team") or [])[:15]:
        lines.append(f"Team -- {fact.get('label', '')}: {fact.get('value', '')}")
    return "\n".join(lines), project


@app.post("/v1/projects/{project_id}/ask")
def ask_about_project(project_id: str, body: AskRequest, firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        context, _ = _project_ask_context(conn, project_id)
        answer = _ask_gemini(context, body.question)
        _log_ask(conn, firebase_uid, "project", body.question, answer, project_id=project_id)
    return {"answer": answer}


def _territory_ask_context(conn, firebase_uid: str) -> str:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT territory_states, categories FROM user_profiles WHERE firebase_uid = %s",
            (firebase_uid,),
        )
        profile_row = cur.fetchone()
    territory = (profile_row or {}).get("territory_states") or []
    categories = (profile_row or {}).get("categories") or []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.project_id, p.name, p.city, p.county, p.state, p.status,
                   p.estimated_value_usd, ps.score AS score_total, t.stage AS your_stage
            FROM projects p
            LEFT JOIN project_scores ps ON ps.project_sk = p.project_sk
            LEFT JOIN user_tracked_projects t
                ON t.project_sk = p.project_sk AND t.firebase_uid = %s
            WHERE (%s::text[] = '{}' OR p.state = ANY(%s::text[]))
            ORDER BY (t.id IS NOT NULL) DESC, ps.score DESC NULLS LAST
            LIMIT 40
            """,
            (firebase_uid, territory, territory),
        )
        rows = cur.fetchall()

    lines = [
        f"User's saved territory: {', '.join(territory) or 'nationwide (no territory set)'}",
        f"User's saved categories: {', '.join(categories) or 'none set'}",
        "Projects (highest priority first, tracked projects first):",
    ]
    for r in rows:
        tracked_note = f", you are tracking this at stage '{r['your_stage']}'" if r["your_stage"] else ""
        lines.append(
            f"- {r['name']} ({r['city']}, {r['county']} County, {r['state']}) -- {r['status']}, "
            f"value {r['estimated_value_usd']}, priority score {r['score_total']}{tracked_note}"
        )
    return "\n".join(lines)


@app.post("/v1/me/ask")
def ask_about_my_territory(body: AskRequest, firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        context = _territory_ask_context(conn, firebase_uid)
        answer = _ask_gemini(context, body.question)
        _log_ask(conn, firebase_uid, "territory", body.question, answer)
    return {"answer": answer}


# Gmail SMTP creds -- same credential pair already used by the pipeline
# health-email GitHub Action (EMAIL_SMTP_USERNAME/PASSWORD secrets), set
# here as Cloud Run env vars instead. Notification is best-effort: a
# missing/misconfigured credential must never lose a real submission, it
# just goes unnotified (see notify_error on the row).
EMAIL_SMTP_USERNAME = os.environ.get("EMAIL_SMTP_USERNAME", "")
EMAIL_SMTP_PASSWORD = os.environ.get("EMAIL_SMTP_PASSWORD", "")
CONTACT_NOTIFY_TO = os.environ.get("CONTACT_NOTIFY_TO", "hello@specindex.ai")


class ContactSubmission(BaseModel):
    first_name: str = Field(min_length=1, max_length=200)
    last_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    company: str = Field(min_length=1, max_length=200)
    categories: str = Field(default="", max_length=500)
    source_path: str = Field(default="", max_length=200)
    # Client sends this when the visitor happens to be signed in at the
    # moment they submit the demo form -- not verified server-side (this
    # endpoint stays anonymous/unauthenticated on purpose, same as before),
    # just a best-effort join key for crm_contacts (db/migrations/
    # 026_crm_contacts.sql). A forged value here only ever links a demo
    # request to the wrong *already-anonymous* row in the internal CRM view,
    # not a security-relevant trust boundary.
    firebase_uid: str | None = Field(default=None, max_length=200)
    # First-touch attribution, captured client-side into localStorage on
    # first landing (not PostHog alone) -- a Gemini review of the growth
    # architecture flagged that ad-blockers silently drop 20-35% of
    # client-side analytics tracking for this ICP, so this first-party
    # capture is the primary attribution source, not a PostHog convenience.
    utm_source: str | None = Field(default=None, max_length=200)
    utm_medium: str | None = Field(default=None, max_length=200)
    utm_campaign: str | None = Field(default=None, max_length=200)
    referrer: str | None = Field(default=None, max_length=500)
    # PostHog's anonymous distinct_id -- joins this submission to the
    # visitor's pre-signup session/replay in PostHog, and later to their
    # firebase_uid once identify() fires on sign-in. Session-replay/funnel
    # data only, same non-primary-attribution caveat as above.
    posthog_distinct_id: str | None = Field(default=None, max_length=200)
    # See components/marketing/DemoModal.tsx's DemoPersona -- copy/context
    # variant the visitor saw, not a different field set or endpoint.
    persona: str | None = Field(default=None, max_length=50)

    @field_validator("email")
    @classmethod
    def email_looks_like_email(cls, v: str) -> str:
        if "@" not in v or " " in v:
            raise ValueError("not a valid email address")
        return v


def _send_contact_notification(sub: ContactSubmission) -> str | None:
    """Returns an error string on failure, None on success/skip. Never
    raises -- called from the request path after the row is already
    committed, so a notification failure must not turn into a 500 for a
    submission that was, in fact, saved."""
    if not EMAIL_SMTP_USERNAME or not EMAIL_SMTP_PASSWORD:
        return "EMAIL_SMTP_USERNAME/PASSWORD not configured"
    try:
        msg = EmailMessage()
        msg["Subject"] = f"SpecIndex demo request: {sub.company}"
        msg["From"] = EMAIL_SMTP_USERNAME
        msg["To"] = CONTACT_NOTIFY_TO
        msg["Reply-To"] = sub.email
        msg.set_content(
            "New demo request from specindex.ai\n\n"
            f"Name: {sub.first_name} {sub.last_name}\n"
            f"Email: {sub.email}\n"
            f"Company: {sub.company}\n"
            f"Product categories: {sub.categories or 'Not specified'}\n"
            f"Page: {sub.source_path or 'unknown'}\n"
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(EMAIL_SMTP_USERNAME, EMAIL_SMTP_PASSWORD)
            smtp.send_message(msg)
        return None
    except Exception as e:  # noqa: BLE001 -- deliberately broad, see docstring
        return str(e)


@app.post("/v1/contact")
def submit_contact(sub: ContactSubmission):
    """Backs the homepage demo-request form (components/marketing/
    DemoSection.tsx). Replaces the previous mailto:/optional-Google-Sheet-
    webhook approach -- every submission is now durably stored even if
    email notification isn't configured or fails."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_submissions
                    (first_name, last_name, email, company, categories, source_path, firebase_uid,
                     utm_source, utm_medium, utm_campaign, referrer, posthog_distinct_id, persona)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    sub.first_name,
                    sub.last_name,
                    sub.email,
                    sub.company,
                    sub.categories,
                    sub.source_path,
                    sub.firebase_uid,
                    sub.utm_source,
                    sub.utm_medium,
                    sub.utm_campaign,
                    sub.referrer,
                    sub.posthog_distinct_id,
                    sub.persona,
                ),
            )
            submission_id = cur.fetchone()[0]
        conn.commit()

        error = _send_contact_notification(sub)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE contact_submissions SET notified_at = %s, notify_error = %s WHERE id = %s",
                (None if error else datetime.now(timezone.utc), error, submission_id),
            )
        conn.commit()

    return {"ok": True, "id": submission_id, "notified": error is None}


class UserProfileUpdate(BaseModel):
    company: str | None = Field(default=None, max_length=200)
    territory_states: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    # CRM fields (docs/PRD_SIGNUP_CRM.md Phase 2). full_name/lead_source are
    # captured client-side from the signed-in user's own auth state/current
    # page at submit time (ProfileCaptureModal), not asked as separate typed
    # fields -- phone/role_title are the only genuinely new form inputs.
    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    role_title: str | None = Field(default=None, max_length=200)
    lead_source: str | None = Field(default=None, max_length=200)

    @field_validator("territory_states")
    @classmethod
    def states_are_two_letter(cls, v: list[str]) -> list[str]:
        for s in v:
            if len(s) != 2:
                raise ValueError(f"not a valid state code: {s!r}")
        return [s.upper() for s in v]


@app.get("/v1/me/profile")
def get_my_profile(firebase_uid: str = Depends(require_firebase_user)):
    """Backs the first-sign-in ProfileCaptureModal and the personalized
    /projects/ view (components/ProjectsDashboard.tsx) -- `onboarded: false`
    with no row yet is the normal, expected state for a brand-new user, not
    an error.

    Also stamps last_login_at (migration 041) -- called once per sign-in by
    AuthSync, not on every request, so this is one write per session, not
    per API call. Best-effort: a logging failure here must never break the
    actual profile response."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT company, territory_states, categories, onboarded_at, "
                "full_name, phone, role_title, subscription_tier "
                "FROM user_profiles WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            row = cur.fetchone()
            try:
                cur.execute(
                    "UPDATE user_profiles SET last_login_at = now() WHERE firebase_uid = %s",
                    (firebase_uid,),
                )
                conn.commit()
            except Exception:  # noqa: BLE001 -- last_login_at is telemetry, never worth failing this request over
                conn.rollback()
    if row is None:
        return {
            "onboarded": False, "company": None, "territory_states": [], "categories": [],
            "full_name": None, "phone": None, "role_title": None, "subscription_tier": "free",
        }
    return {
        "onboarded": row["onboarded_at"] is not None,
        "company": row["company"],
        "territory_states": row["territory_states"],
        "categories": row["categories"],
        "full_name": row["full_name"],
        "phone": row["phone"],
        "role_title": row["role_title"],
        "subscription_tier": row["subscription_tier"],
    }


# docs/architecture-2026/04-productization.md P1: enforces the Free-tier
# "1 brand check per week" limit stated on app/pricing/page.tsx (Pro/Team
# say "Unlimited brand checks"). Free is the DEFAULT subscription_tier
# (migration 027), so a user with no row at all is treated as free, not
# unlimited -- fail toward the paid promise being real, not toward giving
# away Pro behavior to an unrecognized state.
FREE_BRAND_CHECKS_PER_WEEK = 1


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday of the current ISO week


@app.post("/v1/me/brand-check")
def record_brand_check(firebase_uid: str = Depends(require_firebase_user)):
    """Call once per /visibility data pull (components/VisibilityPanel.tsx),
    BEFORE fetching the sample -- 200 means proceed, 429 means show the
    upgrade prompt instead of fetching data. Atomic increment via
    INSERT ... ON CONFLICT DO UPDATE, not a read-then-write, so two rapid
    requests from the same user can't both read "0 used" and both
    proceed."""
    today = _week_start(datetime.now(timezone.utc).date())
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT subscription_tier FROM user_profiles WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            row = cur.fetchone()
            tier = row["subscription_tier"] if row else "free"

            if tier != "free":
                return {"allowed": True, "tier": tier, "remaining": None}

            cur.execute(
                """
                INSERT INTO brand_check_usage (firebase_uid, week_start, check_count)
                VALUES (%s, %s, 1)
                ON CONFLICT (firebase_uid, week_start) DO UPDATE SET
                    check_count = brand_check_usage.check_count
                        + CASE WHEN brand_check_usage.check_count < %s THEN 1 ELSE 0 END
                RETURNING check_count
                """,
                (firebase_uid, today, FREE_BRAND_CHECKS_PER_WEEK),
            )
            count = cur.fetchone()["check_count"]
        conn.commit()

    if count > FREE_BRAND_CHECKS_PER_WEEK:
        raise HTTPException(
            status_code=429,
            detail=f"Free tier is limited to {FREE_BRAND_CHECKS_PER_WEEK} brand check/week. Upgrade to Pro for unlimited.",
        )
    return {"allowed": True, "tier": "free", "remaining": FREE_BRAND_CHECKS_PER_WEEK - count}


@app.post("/v1/me/profile")
def upsert_my_profile(
    body: UserProfileUpdate,
    user: tuple[str, str] = Depends(require_firebase_user_with_email),
):
    """Upsert covers both the first-sign-in capture write and any later
    'edit your territory' action -- no third endpoint needed. email is
    re-read from the verified JWT on every call (never trusted from a prior
    write), so it can't go stale if the user changes it with their sign-in
    provider later."""
    firebase_uid, email = user
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles
                    (firebase_uid, email, company, territory_states, categories,
                     full_name, phone, role_title, lead_source, onboarded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (firebase_uid) DO UPDATE SET
                    email = EXCLUDED.email,
                    company = EXCLUDED.company,
                    territory_states = EXCLUDED.territory_states,
                    categories = EXCLUDED.categories,
                    phone = EXCLUDED.phone,
                    role_title = EXCLUDED.role_title,
                    -- full_name/lead_source are captured once, client-side,
                    -- from the signed-in user's own auth state/current page
                    -- (not asked as a form field a person can leave blank on
                    -- a later edit) -- COALESCE so a future call that omits
                    -- them (e.g. an "edit territory" flow reusing this same
                    -- endpoint) doesn't null out what first-sign-in already
                    -- captured.
                    full_name = COALESCE(EXCLUDED.full_name, user_profiles.full_name),
                    lead_source = COALESCE(EXCLUDED.lead_source, user_profiles.lead_source),
                    onboarded_at = COALESCE(user_profiles.onboarded_at, now()),
                    updated_at = now()
                """,
                (
                    firebase_uid,
                    email,
                    body.company,
                    body.territory_states,
                    body.categories,
                    body.full_name,
                    body.phone,
                    body.role_title,
                    body.lead_source,
                ),
            )
        conn.commit()
    return {"ok": True}


TRACKED_STAGES = {"watching", "contacted", "quoted", "won", "lost"}


class TrackedProjectUpdate(BaseModel):
    stage: str = Field(default="watching")
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("stage")
    @classmethod
    def stage_is_valid(cls, v: str) -> str:
        if v not in TRACKED_STAGES:
            raise ValueError(f"stage must be one of {sorted(TRACKED_STAGES)}")
        return v


@app.get("/v1/me/tracked-projects")
def list_my_tracked_projects(firebase_uid: str = Depends(require_firebase_user)):
    """Backs the signed-in home's 'Tracked' pipeline view. Joins against
    `projects` for display fields rather than the full row_to_project() +
    enrichment fetch used by /v1/projects/{id} -- this list doesn't need
    CSI scope, executive briefs, or contacts, just enough to render a
    pipeline table."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    p.project_id, p.project_sk, p.name, p.city, p.county, p.state,
                    p.status, p.estimated_value_usd,
                    t.stage, t.note, t.updated_at
                FROM user_tracked_projects t
                JOIN projects p ON p.project_sk = t.project_sk
                WHERE t.firebase_uid = %s
                ORDER BY t.updated_at DESC
                """,
                (firebase_uid,),
            )
            rows = cur.fetchall()
    return {
        "tracked": [
            {
                "project_id": r["project_id"],
                "spx_id": spx_id(r["project_sk"]),
                "name": r["name"],
                "city": r["city"] or "",
                "county": r["county"] or "",
                "state": r["state"],
                "status": r["status"],
                "estimated_value_usd": r["estimated_value_usd"],
                "stage": r["stage"],
                "note": r["note"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]
    }


@app.put("/v1/me/tracked-projects/{project_id}")
def upsert_tracked_project(
    project_id: str,
    body: TrackedProjectUpdate,
    firebase_uid: str = Depends(require_firebase_user),
):
    """Full-replace upsert (same convention as upsert_my_profile) -- the
    caller always sends the complete stage+note, not a partial patch. The
    frontend already holds the current tracked-project state from the
    list endpoint before it ever calls this, so this never needs to guess
    at what to preserve."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT project_sk FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project not found")
            project_sk = row[0]
            cur.execute(
                """
                INSERT INTO user_tracked_projects (firebase_uid, project_sk, stage, note)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (firebase_uid, project_sk) DO UPDATE SET
                    stage = EXCLUDED.stage,
                    note = EXCLUDED.note,
                    updated_at = now()
                """,
                (firebase_uid, project_sk, body.stage, body.note),
            )
        conn.commit()
    return {"ok": True}


@app.delete("/v1/me/tracked-projects/{project_id}")
def untrack_project(project_id: str, firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_tracked_projects
                WHERE firebase_uid = %s
                  AND project_sk = (SELECT project_sk FROM projects WHERE project_id = %s)
                """,
                (firebase_uid, project_id),
            )
        conn.commit()
    return {"ok": True}


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    territory_states: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)

    @field_validator("territory_states")
    @classmethod
    def states_are_two_letter(cls, v: list[str]) -> list[str]:
        for s in v:
            if len(s) != 2:
                raise ValueError(f"not a valid state code: {s!r}")
        return [s.upper() for s in v]


@app.get("/v1/me/saved-views")
def list_my_saved_views(firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, territory_states, categories, created_at "
                "FROM user_saved_views WHERE firebase_uid = %s ORDER BY created_at",
                (firebase_uid,),
            )
            rows = cur.fetchall()
    return {
        "views": [
            {
                "id": r["id"],
                "name": r["name"],
                "territory_states": r["territory_states"],
                "categories": r["categories"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@app.post("/v1/me/saved-views")
def create_my_saved_view(body: SavedViewCreate, firebase_uid: str = Depends(require_firebase_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_saved_views (firebase_uid, name, territory_states, categories)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (firebase_uid, body.name, body.territory_states, body.categories),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return {"ok": True, "id": new_id}


@app.delete("/v1/me/saved-views/{view_id}")
def delete_my_saved_view(view_id: int, firebase_uid: str = Depends(require_firebase_user)):
    """firebase_uid in the WHERE clause, not just view_id, so a user can
    never delete another user's saved view by guessing an id -- the
    delete silently no-ops if the id doesn't belong to the caller rather
    than leaking whether it exists via a 404 vs 200 distinction."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_saved_views WHERE id = %s AND firebase_uid = %s",
                (view_id, firebase_uid),
            )
        conn.commit()
    return {"ok": True}
