#!/usr/bin/env python3
"""Fetch related news articles per project from Google News RSS (no API
key, no official quota, but no SLA either -- verified live 2026-07-26:
works well for high-profile projects, e.g. "OpenAI Project Camellia"
returned real, dated, relevant articles. Raw name-only search is noisy
for generic permit-derived names, though -- searching "Linden Village"
returned two unrelated obituaries alongside one real construction
article. Filtered here by requiring the project's city/county/state to
also appear in the result, plus a denylist for common junk (obituaries).

Scoped to the highest-value, not-recently-enriched projects per run
(--limit, default 50) rather than all 7,000+ projects every run --
Google News RSS isn't a resource to hammer at that volume, and most
lower-value permit-derived projects are unlikely to have real news
coverage anyway.

Usage:
    python3 scripts/enrich-news.py --database-url postgresql://... --limit 50
"""

from __future__ import annotations

import argparse
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

JUNK_TITLE_HINTS = re.compile(
    r"(?i)obituary|obituaries|funeral|crematory|service information|celebration of life"
)

RSS_ITEM = re.compile(r"<item>(.*?)</item>", re.DOTALL)
RSS_TITLE = re.compile(r"<title>(.*?)</title>")
RSS_LINK = re.compile(r"<link>(.*?)</link>")
RSS_PUBDATE = re.compile(r"<pubDate>(.*?)</pubDate>")
RSS_SOURCE = re.compile(r"<source[^>]*>(.*?)</source>")


def fetch_news(query: str, timeout: float = 15.0) -> list[dict]:
    url = f"https://news.google.com/rss/search?{urllib.parse.urlencode({'q': query, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})}"
    req = urllib.request.Request(url, headers={"User-Agent": "specindex-pull/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    out = []
    for item in RSS_ITEM.findall(body):
        title_m = RSS_TITLE.search(item)
        link_m = RSS_LINK.search(item)
        if not title_m or not link_m:
            continue
        pubdate_m = RSS_PUBDATE.search(item)
        source_m = RSS_SOURCE.search(item)
        out.append(
            {
                "title": title_m.group(1),
                "url": link_m.group(1),
                "source_name": source_m.group(1) if source_m else None,
                "published_at": parse_pubdate(pubdate_m.group(1)) if pubdate_m else None,
            }
        )
    return out


def parse_pubdate(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_relevant(article: dict, project: dict) -> bool:
    title = article["title"] or ""
    if JUNK_TITLE_HINTS.search(title):
        return False
    locality_hints = [project.get("city"), project.get("county"), project.get("state")]
    return any(hint and hint.lower() in title.lower() for hint in locality_hints if hint)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument("--apply-migration", action="store_true")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_migration:
                from pathlib import Path

                migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "012_project_news.sql"
                cur.execute(migration.read_text(encoding="utf-8"))
                conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.project_sk, p.name, p.city, p.county, p.state
                FROM projects p
                LEFT JOIN project_news_checks c ON c.project_sk = p.project_sk
                WHERE c.checked_at IS NULL OR c.checked_at < now() - interval '30 days'
                ORDER BY p.estimated_value_usd DESC NULLS LAST
                LIMIT %s
                """,
                (args.limit,),
            )
            candidates = cur.fetchall()

        total_found = 0
        for project in candidates:
            try:
                articles = fetch_news(f'"{project["name"]}"')
            except Exception as e:  # noqa: BLE001
                print(f"  {project['name']!r}: fetch failed ({e})")
                time.sleep(args.delay)
                continue

            relevant = [a for a in articles if is_relevant(a, project)]
            with conn.cursor() as cur:
                for a in relevant:
                    cur.execute(
                        """
                        INSERT INTO project_news (project_sk, title, url, source_name, published_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (project_sk, url) DO NOTHING
                        """,
                        (project["project_sk"], a["title"], a["url"], a["source_name"], a["published_at"]),
                    )
                cur.execute(
                    """
                    INSERT INTO project_news_checks (project_sk, checked_at) VALUES (%s, now())
                    ON CONFLICT (project_sk) DO UPDATE SET checked_at = now()
                    """,
                    (project["project_sk"],),
                )
            conn.commit()
            if relevant:
                total_found += len(relevant)
            print(f"  {project['name']!r}: {len(relevant)} relevant of {len(articles)} found")

            time.sleep(args.delay)

        print(f"Checked {len(candidates)} projects, found {total_found} relevant articles")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
