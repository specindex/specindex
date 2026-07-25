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
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "national-commercial-projects.json"
DEFAULT_SCHEMA = ROOT / "db" / "schema.sql"

UPSERT = """
INSERT INTO projects (
  project_id, name, state, city, county, status, project_type,
  estimated_value_usd, square_footage, owner, architect, general_contractor,
  opened_or_announced_date, description, key_specs, mentioned_brands,
  competitor_watch, sources, open_for, corpus_generated_at
) VALUES (
  %(project_id)s, %(name)s, %(state)s, %(city)s, %(county)s, %(status)s,
  %(project_type)s, %(estimated_value_usd)s, %(square_footage)s, %(owner)s,
  %(architect)s, %(general_contractor)s, %(opened_or_announced_date)s,
  %(description)s, %(key_specs)s, %(mentioned_brands)s, %(competitor_watch)s,
  %(sources)s, %(open_for)s, %(corpus_generated_at)s
)
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
  loaded_at = now()
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
    args = parser.parse_args()

    if not args.corpus.is_file():
        print(f"Corpus not found: {args.corpus}", file=sys.stderr)
        return 1

    with args.corpus.open(encoding="utf-8") as f:
        corpus = json.load(f)

    projects = corpus.get("projects") or []
    generated_at = parse_ts(corpus.get("generated_at"))

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_schema:
                cur.execute(DEFAULT_SCHEMA.read_text(encoding="utf-8"))

            for p in projects:
                cur.execute(UPSERT, project_row(p, generated_at))

            cur.execute("SELECT count(*) FROM projects")
            total = cur.fetchone()[0]

        conn.commit()
    finally:
        conn.close()

    print(f"Loaded {len(projects)} projects ({total} rows in database)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
