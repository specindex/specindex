#!/usr/bin/env python3
"""Load national-commercial-projects.json into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "national-commercial-projects.json"
DEFAULT_SCHEMA = ROOT / "db" / "schema.sql"
MIGRATIONS_DIR = ROOT / "db" / "migrations"

sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import classify_source, derive_event_type  # noqa: E402

# Batched via psycopg2.extras.execute_values (see main()) instead of one
# execute() per row -- 7,000+ individual round trips through the Cloud SQL
# Auth Proxy took 30+ minutes and eventually hit a server-side connection
# reset (idle/max-lifetime timeout) before finishing. Batches of 500 finish
# in seconds and are far less likely to outlive any connection limit.
UPSERT_ROW_TEMPLATE = (
    "(%(project_id)s, %(name)s, %(state)s, %(city)s, %(county)s, %(status)s, "
    "%(project_type)s, %(estimated_value_usd)s, %(square_footage)s, %(owner)s, "
    "%(architect)s, %(general_contractor)s, %(opened_or_announced_date)s, "
    "%(description)s, %(key_specs)s, %(mentioned_brands)s, %(competitor_watch)s, "
    "%(sources)s, %(open_for)s, %(corpus_generated_at)s, %(latitude)s, %(longitude)s, %(zip)s)"
)

UPSERT = """
INSERT INTO projects (
  project_id, name, state, city, county, status, project_type,
  estimated_value_usd, square_footage, owner, architect, general_contractor,
  opened_or_announced_date, description, key_specs, mentioned_brands,
  competitor_watch, sources, open_for, corpus_generated_at, latitude, longitude, zip
) VALUES %s
ON CONFLICT (project_id) DO UPDATE SET
  name = EXCLUDED.name,
  state = EXCLUDED.state,
  city = EXCLUDED.city,
  county = EXCLUDED.county,
  status = EXCLUDED.status,
  project_type = EXCLUDED.project_type,
  estimated_value_usd = EXCLUDED.estimated_value_usd,
  square_footage = EXCLUDED.square_footage,
  owner = EXCLUDED.owner,
  architect = EXCLUDED.architect,
  general_contractor = EXCLUDED.general_contractor,
  opened_or_announced_date = EXCLUDED.opened_or_announced_date,
  description = EXCLUDED.description,
  key_specs = EXCLUDED.key_specs,
  mentioned_brands = EXCLUDED.mentioned_brands,
  competitor_watch = EXCLUDED.competitor_watch,
  sources = EXCLUDED.sources,
  open_for = EXCLUDED.open_for,
  corpus_generated_at = EXCLUDED.corpus_generated_at,
  latitude = EXCLUDED.latitude,
  longitude = EXCLUDED.longitude,
  zip = EXCLUDED.zip,
  loaded_at = now()
RETURNING project_id, project_sk, record_type
"""


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def project_row(p: dict, corpus_generated_at: datetime | None) -> dict:
    state = p.get("state")
    return {
        "project_id": p["id"],
        "name": p["name"],
        "state": state.upper() if state else None,
        "city": p.get("city") or "",
        "county": p.get("county") or "",
        "status": p.get("status") or "planning",
        "project_type": p.get("project_type") or "other",
        "estimated_value_usd": p.get("estimated_value_usd"),
        "square_footage": p.get("square_footage"),
        "owner": p.get("owner") or "",
        "architect": p.get("architect") or "",
        "general_contractor": p.get("general_contractor") or "",
        "opened_or_announced_date": parse_date(p.get("opened_or_announced_date")),
        "description": p.get("description") or "",
        "key_specs": Json(p.get("key_specs") or []),
        "mentioned_brands": Json(p.get("mentioned_brands") or []),
        "competitor_watch": Json(p.get("competitor_watch") or []),
        "sources": Json(p.get("sources") or []),
        "open_for": p.get("open_for") or "",
        "corpus_generated_at": corpus_generated_at,
        "latitude": p.get("latitude"),
        "longitude": p.get("longitude"),
        "zip": p.get("zip"),
    }


def project_sources_rows(project_id: str, project_sk: int, sources: list[dict]) -> list[dict]:
    """One row per entry in a project's sources array (see
    project_identity.merge_projects() for how that array gets built) --
    source_name/is_local derived the same way compute-county-coverage.py
    classifies a project's dominant source, since it's the same
    project_id-prefix signal either way."""
    label, is_local = classify_source(project_id)
    rows = []
    seen_urls: set[str | None] = set()
    for src in sources:
        if not isinstance(src, dict):
            continue
        url = (src.get("url") or "").strip() or None
        # A project's sources array can (and does, e.g. some GA SAM.gov
        # merges) contain the exact same url more than once -- the unique
        # constraint is (project_sk, source_name, url), so duplicates
        # within one project would otherwise collide within the same
        # INSERT batch (Postgres: "ON CONFLICT DO UPDATE cannot affect row
        # a second time").
        if url in seen_urls:
            continue
        seen_urls.add(url)
        rows.append(
            {
                "project_sk": project_sk,
                "source_name": label,
                "source_record_id": None,
                "source_url": url,
                "raw_data": Json(src),
                "is_primary": is_local,
            }
        )
    return rows


def project_event_row(project_id: str, project_sk: int, record_type: str | None, event_date, source_label: str) -> dict | None:
    if event_date is None:
        return None
    return {
        "project_sk": project_sk,
        "event_type": derive_event_type(project_id, record_type),
        "event_date": event_date,
        "source_name": source_label,
        "source_url": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help="Path to national-commercial-projects.json",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://specindex:specindex@localhost:5432/specindex",
        ),
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Run db/schema.sql before loading",
    )
    parser.add_argument(
        "--apply-migrations",
        action="store_true",
        help="Run db/migrations/008_project_sources.sql and 009_project_events.sql first",
    )
    args = parser.parse_args()

    if not args.corpus.is_file():
        print(f"Corpus not found: {args.corpus}", file=sys.stderr)
        return 1

    with args.corpus.open(encoding="utf-8") as f:
        corpus = json.load(f)

    projects = corpus.get("projects") or []
    generated_at = parse_ts(corpus.get("generated_at"))
    projects_by_id = {p["id"]: p for p in projects}

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_schema:
                cur.execute(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
            if args.apply_migrations:
                for name in ("008_project_sources.sql", "009_project_events.sql"):
                    cur.execute((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))

            rows = [project_row(p, generated_at) for p in projects]
            returned = execute_values(
                cur, UPSERT, rows, template=UPSERT_ROW_TEMPLATE, page_size=500, fetch=True
            )

            source_rows: list[dict] = []
            event_rows: list[dict] = []
            for project_id, project_sk, record_type in returned:
                p = projects_by_id.get(project_id)
                if not p:
                    continue
                label, _ = classify_source(project_id)
                source_rows.extend(
                    project_sources_rows(project_id, project_sk, p.get("sources") or [])
                )
                event = project_event_row(
                    project_id,
                    project_sk,
                    record_type,
                    parse_date(p.get("opened_or_announced_date")),
                    label,
                )
                if event:
                    event_rows.append(event)

            if source_rows:
                execute_values(
                    cur,
                    """
                    INSERT INTO project_sources
                        (project_sk, source_name, source_record_id, source_url, raw_data, is_primary)
                    VALUES %s
                    ON CONFLICT (project_sk, source_name, COALESCE(source_url, ''))
                    DO UPDATE SET raw_data = EXCLUDED.raw_data, ingested_at = now()
                    """,
                    source_rows,
                    template="(%(project_sk)s, %(source_name)s, %(source_record_id)s, %(source_url)s, %(raw_data)s, %(is_primary)s)",
                    page_size=500,
                )
            if event_rows:
                execute_values(
                    cur,
                    """
                    INSERT INTO project_events (project_sk, event_type, event_date, source_name, source_url)
                    VALUES %s
                    ON CONFLICT (project_sk, event_type, event_date, source_name) DO NOTHING
                    """,
                    event_rows,
                    template="(%(project_sk)s, %(event_type)s, %(event_date)s, %(source_name)s, %(source_url)s)",
                    page_size=500,
                )

            cur.execute("SELECT count(*) FROM projects")
            total = cur.fetchone()[0]

        conn.commit()
    finally:
        conn.close()

    print(
        f"Loaded {len(projects)} projects ({total} rows in database), "
        f"{len(source_rows)} project_sources rows, {len(event_rows)} project_events rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
