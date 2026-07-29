#!/usr/bin/env python3
"""Populate project_enrichment for one project via a two-pass Gemini
search-grounded process -- the same methodology used by hand to build the
ProjectDetailLight page design (2026-07-29, session
"project_rainier_detail_page" + "project_rainier_audit_crosscheck"):

  Pass 1 (discovery): one grounded query per project asking for an
  executive brief, CSI-division scope, construction team, permits, and
  news, returned as free text ending in a fenced ```json block.

  Pass 2 (cross-check): a SEPARATE, fresh Gemini session re-verifies just
  the team/contact/permit claims from pass 1 -- the highest-stakes facts,
  the ones someone might actually act on. Independent by construction:
  it gets none of pass 1's conversation history, only the bare claims to
  check, so it can't just agree with itself.

  Confidence is assigned by diffing the two passes, never by trusting
  either one alone: agreement -> confirmed, disagreement -> reported
  (both figures shown, not silently resolved -- see the generator-count
  case in docs/... er, in this session's actual output: 234 vs 878 vs 911
  all appeared across different queries), pass-1 "not publicly confirmed"
  -> unconfirmed regardless of what pass 2 says about it.

  News URLs get an independent HTTP check (like the curl checks run by
  hand in this session, which caught a 404'd citation) -- an article
  whose link doesn't resolve is dropped, not stored with a dead link.

This is deliberately NOT wired into the ingestion pipeline as an
auto-trigger. Per Asif's call (2026-07-29): run manually per project until
the methodology is validated at scale, the same way gemini_discovery_chat.py
is a manual tool, not a pipeline stage.

Usage:
    python3 scripts/enrich-project-details.py SPX-104822
    python3 scripts/enrich-project-details.py SPX-104822 --database-url postgresql://... --apply-migration
    python3 scripts/enrich-project-details.py SPX-104822 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from state_agent_pipeline.config import Settings  # noqa: E402

JSON_FENCE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


# spx_id isn't a stored column -- api/main.py computes it on the fly from
# project_sk (f"SPX-{project_sk:06d}"). Mirrored here so this script can
# take/print the same customer-facing ID without querying a column that
# doesn't exist.
def _spx_id(project_sk: int) -> str:
    return f"SPX-{project_sk:06d}"


def _parse_spx_id(value: str) -> int:
    digits = re.sub(r"\D", "", value)
    if not digits:
        raise ValueError(f"not a valid spx_id: {value!r}")
    return int(digits)


# ---------------------------------------------------------------------------
# Gemini calls
# ---------------------------------------------------------------------------

def _client(settings: Settings):
    from google import genai

    return genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)


def _grounded_call(client, model: str, prompt: str, max_retries: int = 3) -> str:
    """One-shot search-grounded generation, no chat history -- each call is
    independent, which is what makes pass 2 a real cross-check rather than
    the model just re-reading its own pass-1 answer."""
    from google.genai import types
    from google.auth.exceptions import RefreshError

    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            return resp.text
        except RefreshError:
            raise
        except Exception as e:  # noqa: BLE001 -- network/timeout errors vary by transport
            if attempt == max_retries:
                raise
            wait = 2**attempt
            print(f"  [retry {attempt}/{max_retries}] {e} -- waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _extract_json(text: str) -> dict:
    m = JSON_FENCE.search(text)
    if not m:
        raise ValueError("no ```json fence found in model response")
    return json.loads(m.group(1))


# ---------------------------------------------------------------------------
# Pass 1: discovery
# ---------------------------------------------------------------------------

DISCOVERY_PROMPT = """You are researching a commercial construction project for a project-intelligence \
database. Project: "{name}" in {city}, {county} County, {state}.

Search for current, verifiable facts. For anything you cannot verify via search, write \
"not publicly confirmed" rather than guessing -- an invented fact here is worse than a missing one.

Give me:
1. A 3-5 sentence executive brief (owner, scope, scale, why it matters)
2. CSI MasterFormat scope, division by division, for whatever divisions you can find real \
   information on (concrete, electrical, HVAC, sitework, etc) -- skip divisions with nothing findable
3. Construction team: general contractor(s), architect/engineer, electrical contractor, \
   concrete supplier, utility partner -- named companies only
4. Permits and regulatory filings, with permit numbers where findable
5. Press/media contacts (corporate press, relevant government economic development office)
6. Recent news coverage (last 90 days), with real article URLs

After your written answer, output a fenced ```json block with this exact shape (omit any \
array entirely if you found nothing for it -- do not fabricate placeholder rows):

```json
{{
  "executive_brief": "string",
  "csi_scope": [{{"division": "Div 03", "label": "Concrete", "scope": "string", "sources": "string"}}],
  "team": [{{"role": "General Contractor", "party": "string", "sources": "string"}}],
  "permits": [{{"label": "string", "detail": "string"}}],
  "contacts": [{{"org": "string", "detail": "string", "sources": "string"}}],
  "news": [{{"title": "string", "source": "string", "date": "string", "url": "string"}}]
}}
```
"""


def run_discovery(client, model: str, project: dict) -> dict:
    prompt = DISCOVERY_PROMPT.format(
        name=project["name"],
        city=project.get("city") or "unknown city",
        county=project.get("county") or "unknown county",
        state=project.get("state") or "unknown state",
    )
    text = _grounded_call(client, model, prompt)
    return _extract_json(text)


# ---------------------------------------------------------------------------
# Pass 2: independent cross-check of the highest-stakes claims
# ---------------------------------------------------------------------------

CROSSCHECK_PROMPT = """Independently verify these specific claims about "{name}" ({city}, {state}). \
Don't assume any of them are true -- search fresh. For each, give a verdict of "solid", "shaky", \
or "cant_confirm", and if shaky, what the correct value actually is.

Claims to check:
{claims}

Output ONLY a fenced ```json block, a list in the same order as the claims, no commentary:

```json
[{{"claim_index": 0, "verdict": "solid", "correction": null}}]
```
"""


def run_crosscheck(client, model: str, project: dict, claims: list[str]) -> list[dict]:
    if not claims:
        return []
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    prompt = CROSSCHECK_PROMPT.format(
        name=project["name"], city=project.get("city") or "unknown city", state=project.get("state") or "unknown state", claims=numbered
    )
    text = _grounded_call(client, model, prompt)
    return _extract_json(text)


def _team_claims(discovery: dict) -> list[str]:
    claims = []
    for row in discovery.get("team", []):
        claims.append(f"{row.get('role', 'Role')}: {row.get('party', '')}")
    for row in discovery.get("permits", []):
        claims.append(f"Permit — {row.get('label', '')}: {row.get('detail', '')}")
    for row in discovery.get("contacts", []):
        claims.append(f"Contact — {row.get('org', '')}: {row.get('detail', '')}")
    return claims


def _confidence_for(verdict: str | None) -> str:
    if verdict == "solid":
        return "confirmed"
    if verdict == "shaky":
        return "reported"
    return "unconfirmed"


# ---------------------------------------------------------------------------
# URL live-check (same idea as the curl checks run by hand this session)
# ---------------------------------------------------------------------------

def url_resolves(url: str, timeout: float = 8.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (specindex-enrichment/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:  # noqa: BLE001 -- any failure means "don't trust this link"
        return False


# ---------------------------------------------------------------------------
# Merge + persist
# ---------------------------------------------------------------------------

def build_rows(discovery: dict, crosscheck: list[dict]) -> list[dict]:
    verdicts = {row["claim_index"]: row for row in crosscheck}
    rows = []
    claim_i = 0

    if discovery.get("executive_brief"):
        rows.append(
            dict(section="executive_brief", field_key="summary", field_label="Executive Brief",
                 field_value=discovery["executive_brief"], confidence="reported", sources="Gemini search grounding")
        )

    for row in discovery.get("csi_scope", []):
        rows.append(
            dict(section="csi_scope", field_key=re.sub(r"\W+", "_", row.get("division", "")).strip("_").lower(),
                 field_label=f"{row.get('division', '')} — {row.get('label', '')}", field_value=row.get("scope", ""),
                 confidence="reported", sources=row.get("sources", ""))
        )

    for row in discovery.get("team", []):
        v = verdicts.get(claim_i)
        confidence = _confidence_for(v["verdict"]) if v else "reported"
        value = v.get("correction") if v and v.get("verdict") == "shaky" and v.get("correction") else row.get("party", "")
        rows.append(
            dict(section="team", field_key=re.sub(r"\W+", "_", row.get("role", "")).strip("_").lower(),
                 field_label=row.get("role", ""), field_value=value, confidence=confidence, sources=row.get("sources", ""))
        )
        claim_i += 1

    for i, row in enumerate(discovery.get("permits", [])):
        v = verdicts.get(claim_i)
        confidence = _confidence_for(v["verdict"]) if v else "reported"
        rows.append(
            dict(section="permit", field_key=f"permit_{i}", field_label=row.get("label", ""),
                 field_value=row.get("detail", ""), confidence=confidence, sources="")
        )
        claim_i += 1

    for i, row in enumerate(discovery.get("contacts", [])):
        v = verdicts.get(claim_i)
        confidence = _confidence_for(v["verdict"]) if v else "reported"
        value = v.get("correction") if v and v.get("verdict") == "shaky" and v.get("correction") else row.get("detail", "")
        rows.append(
            dict(section="contact", field_key=f"contact_{i}", field_label=row.get("org", ""),
                 field_value=value, confidence=confidence, sources=row.get("sources", ""))
        )
        claim_i += 1

    return rows


def persist(conn, project_sk: int, rows: list[dict], news: list[dict]) -> None:
    import psycopg2.extras  # noqa: F401

    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO project_enrichment (project_sk, section, field_key, field_label, field_value, confidence, sources)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_sk, section, field_key) DO UPDATE SET
                    field_label = EXCLUDED.field_label,
                    field_value = EXCLUDED.field_value,
                    confidence = EXCLUDED.confidence,
                    sources = EXCLUDED.sources,
                    enriched_at = now()
                """,
                (project_sk, r["section"], r["field_key"], r["field_label"], r["field_value"], r["confidence"], r["sources"]),
            )
        for n in news:
            cur.execute(
                """
                INSERT INTO project_news (project_sk, title, url, source_name, published_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (project_sk, url) DO NOTHING
                """,
                (project_sk, n["title"], n["url"], n.get("source"), None),
            )
        cur.execute(
            """
            INSERT INTO project_enrichment_checks (project_sk, checked_at) VALUES (%s, now())
            ON CONFLICT (project_sk) DO UPDATE SET checked_at = now()
            """,
            (project_sk,),
        )
    conn.commit()


def enrich_one(client, settings: Settings, conn, project: dict, dry_run: bool) -> int:
    """Run both passes for one project and persist (unless dry_run). Returns
    the number of facts written, for the batch-mode summary."""
    print(f"Pass 1 (discovery): {project['name']!r}")
    discovery = run_discovery(client, settings.flash_model, project)

    claims = _team_claims(discovery)
    print(f"Pass 2 (cross-check): {len(claims)} claims")
    crosscheck = run_crosscheck(client, settings.flash_model, project, claims)

    rows = build_rows(discovery, crosscheck)

    verified_news = []
    for n in discovery.get("news", []):
        url = n.get("url")
        if url and url_resolves(url):
            verified_news.append(n)
        else:
            print(f"  dropping unverified news URL: {n.get('title', '')!r} -> {url!r}")

    print(f"  {len(rows)} facts, {len(verified_news)}/{len(discovery.get('news', []))} news URLs verified live")
    for r in rows:
        print(f"    [{r['confidence']:11s}] {r['section']}.{r['field_key']}: {r['field_value'][:80]}")

    if dry_run:
        print("  --dry-run: not writing to the database")
        return len(rows)

    persist(conn, project["project_sk"], rows, verified_news)
    print(f"  wrote {len(rows)} facts + {len(verified_news)} news rows for {project['spx_id']}")
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spx_id", nargs="?", help="Project's customer-facing ID, e.g. SPX-104822. Omit with --batch.")
    ap.add_argument(
        "--batch",
        action="store_true",
        help="process the highest-value not-yet-enriched projects instead of one spx_id (same cooldown "
        "pattern as enrich-news.py: --limit projects per run, 30-day recheck via project_enrichment_checks)",
    )
    ap.add_argument("--limit", type=int, default=25, help="--batch only: max projects to enrich this run")
    ap.add_argument("--delay", type=float, default=2.0, help="--batch only: seconds between projects")
    ap.add_argument("--state", help="--batch only: restrict to one state code, e.g. GA")
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--apply-migration", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written, don't touch the DB")
    args = ap.parse_args()

    if not args.batch and not args.spx_id:
        ap.error("spx_id is required unless --batch is given")

    import psycopg2
    import psycopg2.extras

    settings = Settings.from_env()
    client = _client(settings)

    conn = psycopg2.connect(args.database_url)
    try:
        if args.apply_migration:
            with conn.cursor() as cur:
                migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "016_project_enrichment.sql"
                cur.execute(migration.read_text(encoding="utf-8"))
            conn.commit()

        if args.batch:
            state_clause = "AND p.state = %s" if args.state else ""
            params: tuple = (args.state.upper(), args.limit) if args.state else (args.limit,)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT p.project_sk, p.name, p.city, p.county, p.state
                    FROM projects p
                    LEFT JOIN project_enrichment_checks c ON c.project_sk = p.project_sk
                    WHERE (c.checked_at IS NULL OR c.checked_at < now() - interval '30 days')
                    {state_clause}
                    ORDER BY p.estimated_value_usd DESC NULLS LAST
                    LIMIT %s
                    """,
                    params,
                )
                candidates = cur.fetchall()
            for c in candidates:
                c["spx_id"] = _spx_id(c["project_sk"])

            print(f"Batch: {len(candidates)} candidate project(s)\n")
            total_facts = 0
            for project in candidates:
                try:
                    total_facts += enrich_one(client, settings, conn, project, args.dry_run)
                except Exception as e:  # noqa: BLE001 -- one bad project shouldn't kill the whole batch run
                    print(f"  FAILED ({project['spx_id']}): {e}", file=sys.stderr)
                    if not args.dry_run:
                        with conn.cursor() as cur:
                            cur.execute(
                                "INSERT INTO project_enrichment_checks (project_sk, checked_at) VALUES (%s, now()) "
                                "ON CONFLICT (project_sk) DO UPDATE SET checked_at = now()",
                                (project["project_sk"],),
                            )
                        conn.commit()
                print()
                time.sleep(args.delay)

            print(f"Batch complete: {len(candidates)} projects, {total_facts} total facts")
            return 0

        project_sk = _parse_spx_id(args.spx_id)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT project_sk, name, city, county, state FROM projects WHERE project_sk = %s",
                (project_sk,),
            )
            project = cur.fetchone()
        if project:
            project["spx_id"] = _spx_id(project["project_sk"])
        if not project:
            print(f"No project found with spx_id={args.spx_id!r} (project_sk={project_sk})", file=sys.stderr)
            return 1

        enrich_one(client, settings, conn, project, args.dry_run)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
