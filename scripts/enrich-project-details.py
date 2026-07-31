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
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from state_agent_pipeline.config import Settings  # noqa: E402
import llm_budget  # noqa: E402

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


# Rough per-1M-token list prices (USD) for cost estimation only -- not
# billing-accurate, just enough for the budget-tracking/circuit-breaker
# use case in docs/architecture-2026/01-data-platform.md. Grounding fee is
# the real cost dominator on sparse prompts (Gemini review finding): it's
# a fixed per-search charge, NOT token-based, and can be 10-50x the token
# cost -- logged as its own column rather than folded into token pricing.
_FLASH_INPUT_PER_M = 0.30
_FLASH_OUTPUT_PER_M = 2.50
_GROUNDING_FEE_PER_REQUEST = 0.035  # ~$35 / 1,000 grounded requests


def _log_llm_call(
    conn, project_sk: int | None, call_site: str, model: str,
    input_tokens: int | None, output_tokens: int | None, grounded: bool,
) -> None:
    if conn is None:
        return
    cost = _GROUNDING_FEE_PER_REQUEST if grounded else 0.0
    if input_tokens:
        cost += (input_tokens / 1_000_000) * _FLASH_INPUT_PER_M
    if output_tokens:
        cost += (output_tokens / 1_000_000) * _FLASH_OUTPUT_PER_M
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO llm_call_log
                (project_sk, call_site, model, input_tokens, output_tokens,
                 grounding_requests_count, estimated_cost_usd, grounded)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (project_sk, call_site, model, input_tokens, output_tokens,
             1 if grounded else 0, round(cost, 6), grounded),
        )
    conn.commit()


def _grounded_call(
    client, model: str, prompt: str, max_retries: int = 3,
    conn=None, project_sk: int | None = None, call_site: str = "enrich_unspecified",
) -> str:
    """One-shot search-grounded generation, no chat history -- each call is
    independent, which is what makes pass 2 a real cross-check rather than
    the model just re-reading its own pass-1 answer.

    Logs to llm_call_log when conn is given (batch/single-project runs that
    pass a real connection) -- best-effort, a logging failure must never
    fail the actual enrichment call."""
    from google.genai import types
    from google.auth.exceptions import RefreshError

    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            usage = getattr(resp, "usage_metadata", None)
            try:
                _log_llm_call(
                    conn, project_sk, call_site, model,
                    getattr(usage, "prompt_token_count", None) if usage else None,
                    getattr(usage, "candidates_token_count", None) if usage else None,
                    grounded=True,
                )
            except Exception as log_err:  # noqa: BLE001 -- logging must never break enrichment
                print(f"  [warn] llm_call_log insert failed: {log_err}", file=sys.stderr)
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
# Tier-1 triage: cheap, ungrounded pre-check before Pass 1
# ---------------------------------------------------------------------------

TRIAGE_PROMPT = """A construction-project database is deciding whether to spend a full \
search-grounded research pass on this project. Project: "{name}" in {city}, {state}. \
What we already have on file:

{existing_summary}

Based ONLY on the project name, location, and what's already on file (no search -- just \
your judgment), is this project specific/identifiable enough that a real web search pass is \
likely to find team/permit/news facts, or is it too generic/sparse to be worth it (e.g. a \
one-line permit record with no real project name)?

Output ONLY a fenced ```json block:
```json
{{"worth_full_pass": true, "reason": "short string"}}
```
"""


def _existing_summary(project: dict) -> str:
    parts = []
    if project.get("owner"):
        parts.append(f"owner: {project['owner']}")
    if project.get("general_contractor"):
        parts.append(f"GC: {project['general_contractor']}")
    if project.get("description"):
        parts.append(f"description: {project['description'][:200]}")
    return "; ".join(parts) if parts else "(nothing else on file)"


def run_triage(client, model: str, project: dict, conn=None) -> dict:
    """Single cheap, UNGROUNDED call (no google_search tool -- that's the
    whole point, grounding is the expensive part of Pass 1/2) that decides
    whether a project is worth a full grounded pass at all.
    docs/architecture-2026/01-data-platform.md P1: cuts spend on projects
    too generic/sparse for search to find anything real (a bare permit
    record with no real project name), before paying for the grounded
    call that would likely come back empty anyway."""
    from google.genai import types

    prompt = TRIAGE_PROMPT.format(
        name=project["name"],
        city=project.get("city") or "unknown city",
        state=project.get("state") or "unknown state",
        existing_summary=_existing_summary(project),
    )
    for attempt in range(1, 3):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig()
            )
            usage = getattr(resp, "usage_metadata", None)
            try:
                _log_llm_call(
                    conn, project.get("project_sk"), "enrich_triage", model,
                    getattr(usage, "prompt_token_count", None) if usage else None,
                    getattr(usage, "candidates_token_count", None) if usage else None,
                    grounded=False,
                )
            except Exception as log_err:  # noqa: BLE001
                print(f"  [warn] llm_call_log insert failed: {log_err}", file=sys.stderr)
            return _extract_json(resp.text)
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                # Triage itself failing shouldn't block enrichment -- fail
                # open (treat as worth a full pass) rather than silently
                # starving a project of enrichment because the cheap
                # pre-check had a bad day.
                print(f"  [warn] triage call failed, defaulting to full pass: {e}", file=sys.stderr)
                return {"worth_full_pass": True, "reason": "triage call failed, failing open"}
            time.sleep(1)
    return {"worth_full_pass": True, "reason": "unreachable"}


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


def run_discovery(client, model: str, project: dict, conn=None) -> dict:
    prompt = DISCOVERY_PROMPT.format(
        name=project["name"],
        city=project.get("city") or "unknown city",
        county=project.get("county") or "unknown county",
        state=project.get("state") or "unknown state",
    )
    text = _grounded_call(client, model, prompt, conn=conn, project_sk=project.get("project_sk"), call_site="enrich_pass1")
    return _extract_json(text)


# docs/architecture-2026/01-data-platform.md P3: "Batch multiple projects
# per Gemini enrichment call instead of one-per-call." Opt-in only
# (--projects-per-call > 1, default 1 = today's unchanged one-per-call
# behavior) -- this changes the discovery prompt shape, and the currently
# running/scheduled single-project pipeline shouldn't have its default
# behavior altered by a P3 addition. Pass 2 (cross-check) and Tier-1
# triage stay per-project even in batch mode -- Pass 2's whole point is
# an INDEPENDENT second look with no shared context (see its own
# docstring); batching it together with other projects' claims would
# undermine that by construction, not just be slower to parse.
BATCH_DISCOVERY_PROMPT = """You are researching {count} commercial construction projects for a \
project-intelligence database. For EACH project below, search for current, verifiable facts. \
For anything you cannot verify via search, write "not publicly confirmed" rather than guessing.

Projects:
{project_list}

For each project, give the same fields as a single-project lookup would: executive_brief, \
csi_scope, team, permits, contacts, news (see field shapes below). Skip anything you found \
nothing for -- do not fabricate placeholder rows.

Output ONLY a fenced ```json block: an array, ONE ENTRY PER PROJECT IN THE SAME ORDER LISTED \
ABOVE, each entry shaped exactly like a single-project lookup:

```json
[
  {{
    "project_index": 0,
    "executive_brief": "string",
    "csi_scope": [{{"division": "Div 03", "label": "Concrete", "scope": "string", "sources": "string"}}],
    "team": [{{"role": "General Contractor", "party": "string", "sources": "string"}}],
    "permits": [{{"label": "string", "detail": "string"}}],
    "contacts": [{{"org": "string", "detail": "string", "sources": "string"}}],
    "news": [{{"title": "string", "source": "string", "date": "string", "url": "string"}}]
  }}
]
```
"""


def run_discovery_batch(client, model: str, projects: list[dict], conn=None) -> dict[int, dict]:
    """Returns {{project_sk: discovery_dict}}. A project missing from the
    response (model skipped it, or the batch call failed entirely) is
    simply absent from the returned dict -- callers must handle a partial
    result, not assume every input project_sk comes back."""
    project_list = "\n".join(
        f"{i}. \"{p['name']}\" in {p.get('city') or 'unknown city'}, "
        f"{p.get('county') or 'unknown county'} County, {p.get('state') or 'unknown state'}"
        for i, p in enumerate(projects)
    )
    prompt = BATCH_DISCOVERY_PROMPT.format(count=len(projects), project_list=project_list)
    text = _grounded_call(
        client, model, prompt, conn=conn, project_sk=None, call_site="enrich_pass1_batch"
    )
    m = JSON_FENCE.search(text)
    if not m:
        raise ValueError("no ```json fence found in batch discovery response")
    entries = json.loads(m.group(1))
    out: dict[int, dict] = {}
    for entry in entries:
        idx = entry.get("project_index")
        if idx is None or not (0 <= idx < len(projects)):
            continue
        out[projects[idx]["project_sk"]] = entry
    return out


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


def run_crosscheck(client, model: str, project: dict, claims: list[str], conn=None) -> list[dict]:
    if not claims:
        return []
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    prompt = CROSSCHECK_PROMPT.format(
        name=project["name"], city=project.get("city") or "unknown city", state=project.get("state") or "unknown state", claims=numbered
    )
    text = _grounded_call(client, model, prompt, conn=conn, project_sk=project.get("project_sk"), call_site="enrich_pass2")
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
# Fingerprint -- computed here in code, never trusted to the LLM (same
# discipline as canonical_golden_id() in model_b_sonnet.py). Hashes the
# concatenation of every field the two Gemini passes actually condition
# on: name/city/county/state, plus this project's source titles/urls and
# document filenames -- if none of that changed, the discovery/crosscheck
# prompts would produce the same input and cost is better spent elsewhere.
# ---------------------------------------------------------------------------

CURRENT_ENRICHMENT_VERSION = 1


def compute_source_fingerprint(conn, project: dict) -> str:
    import hashlib

    parts = [
        project.get("name") or "",
        project.get("city") or "",
        project.get("county") or "",
        project.get("state") or "",
    ]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_name, source_url FROM project_sources WHERE project_sk = %s ORDER BY id",
            (project["project_sk"],),
        )
        for source_name, source_url in cur.fetchall():
            parts.append(f"{source_name}|{source_url}")
        cur.execute(
            "SELECT title FROM project_document_files WHERE project_sk = %s ORDER BY id",
            (project["project_sk"],),
        )
        for (title,) in cur.fetchall():
            parts.append(title)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:32]


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


def persist_checked_only(conn, project_sk: int, fingerprint: str | None) -> None:
    """Records a real, done attempt with zero facts written -- used when
    Tier-1 triage decides a project isn't worth a full pass. Distinct from
    not calling this at all: without it, a triaged-away sparse project
    would get re-triaged (another cheap call, still real spend) every
    single batch run forever instead of respecting the same fingerprint/
    180-day cooldown a normal enrichment gets."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO project_enrichment_checks
                (project_sk, checked_at, source_fingerprint, enrichment_version, status, last_enriched_at)
            VALUES (%s, now(), %s, %s, 'done', now())
            ON CONFLICT (project_sk) DO UPDATE SET
                checked_at = now(),
                source_fingerprint = EXCLUDED.source_fingerprint,
                enrichment_version = EXCLUDED.enrichment_version,
                status = 'done',
                last_enriched_at = now()
            """,
            (project_sk, fingerprint, CURRENT_ENRICHMENT_VERSION),
        )
    conn.commit()


def persist(conn, project_sk: int, rows: list[dict], news: list[dict], fingerprint: str | None = None) -> None:
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
            INSERT INTO project_enrichment_checks
                (project_sk, checked_at, source_fingerprint, enrichment_version, status, last_enriched_at)
            VALUES (%s, now(), %s, %s, 'done', now())
            ON CONFLICT (project_sk) DO UPDATE SET
                checked_at = now(),
                source_fingerprint = EXCLUDED.source_fingerprint,
                enrichment_version = EXCLUDED.enrichment_version,
                status = 'done',
                last_enriched_at = now()
            """,
            (project_sk, fingerprint, CURRENT_ENRICHMENT_VERSION),
        )
    conn.commit()


# docs/architecture-2026/01-data-platform.md P1: "reserve the expensive
# independent cross-check for projects actually worth the cost (high
# score, high estimated_value_usd)". project_scores.score is 0-100 (see
# api/main.py's score.total); below this, Pass 1's discovery alone still
# runs and gets written, just without the second, independent verification
# pass on team/permit claims.
PASS2_SCORE_THRESHOLD = 50


def _project_score(conn, project_sk: int) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT score FROM project_scores WHERE project_sk = %s", (project_sk,))
        row = cur.fetchone()
    return row[0] if row else None


def enrich_one(client, settings: Settings, conn, project: dict, dry_run: bool, force: bool = False) -> int:
    """Run both passes for one project and persist (unless dry_run). Returns
    the number of facts written, for the batch-mode summary.

    Fingerprint-gated (docs/architecture-2026/01-data-platform.md): if the
    project's source data hasn't changed since the last successful
    enrichment (same fingerprint) AND that enrichment was less than 180
    days ago, skip calling Gemini at all -- the 180-day fallback exists
    because the fingerprint only hashes LOCAL fields, so a permanently
    sparse project (nothing in project_sources/project_document_files)
    would otherwise never be re-checked for newly published external
    info (a real bug a Gemini review of this design caught)."""
    fingerprint = compute_source_fingerprint(conn, project)
    if not force:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_fingerprint, last_enriched_at FROM project_enrichment_checks WHERE project_sk = %s",
                (project["project_sk"],),
            )
            existing = cur.fetchone()
        if existing:
            prev_fingerprint, last_enriched_at = existing
            stale = last_enriched_at is None or (
                datetime.now(timezone.utc) - last_enriched_at
            ).days >= 180
            if prev_fingerprint == fingerprint and not stale:
                print(f"  skip: unchanged fingerprint, enriched {last_enriched_at} (< 180 days) for {project['spx_id']}")
                return 0

    triage = run_triage(client, settings.flash_model, project, conn=conn)
    if not triage.get("worth_full_pass", True):
        print(f"  triage: skipping full pass for {project['spx_id']} -- {triage.get('reason', '')!r}")
        if not dry_run:
            persist_checked_only(conn, project["project_sk"], fingerprint)
        return 0

    print(f"Pass 1 (discovery): {project['name']!r}")
    discovery = run_discovery(client, settings.flash_model, project, conn=conn)

    claims = _team_claims(discovery)
    score = _project_score(conn, project["project_sk"])
    if claims and (score is None or score >= PASS2_SCORE_THRESHOLD):
        print(f"Pass 2 (cross-check): {len(claims)} claims (score={score})")
        crosscheck = run_crosscheck(client, settings.flash_model, project, claims, conn=conn)
    else:
        print(f"  skipping Pass 2 -- score {score} below threshold {PASS2_SCORE_THRESHOLD}")
        crosscheck = []

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

    persist(conn, project["project_sk"], rows, verified_news, fingerprint=fingerprint)
    print(f"  wrote {len(rows)} facts + {len(verified_news)} news rows for {project['spx_id']}")
    return len(rows)


def _finish_from_discovery(
    client, settings: Settings, conn, project: dict, discovery: dict, fingerprint: str, dry_run: bool
) -> int:
    """Shared back half of enrich_one/enrich_group once a Pass-1 discovery
    dict exists, regardless of whether it came from a single-project or
    batched call -- Pass 2 gating, news verification, and persistence are
    identical either way."""
    claims = _team_claims(discovery)
    score = _project_score(conn, project["project_sk"])
    if claims and (score is None or score >= PASS2_SCORE_THRESHOLD):
        print(f"Pass 2 (cross-check): {len(claims)} claims (score={score})")
        crosscheck = run_crosscheck(client, settings.flash_model, project, claims, conn=conn)
    else:
        print(f"  skipping Pass 2 -- score {score} below threshold {PASS2_SCORE_THRESHOLD}")
        crosscheck = []

    rows = build_rows(discovery, crosscheck)
    verified_news = []
    for n in discovery.get("news", []):
        url = n.get("url")
        if url and url_resolves(url):
            verified_news.append(n)
        else:
            print(f"  dropping unverified news URL: {n.get('title', '')!r} -> {url!r}")

    print(f"  {len(rows)} facts, {len(verified_news)}/{len(discovery.get('news', []))} news URLs verified live")
    if dry_run:
        print("  --dry-run: not writing to the database")
        return len(rows)

    persist(conn, project["project_sk"], rows, verified_news, fingerprint=fingerprint)
    print(f"  wrote {len(rows)} facts + {len(verified_news)} news rows for {project['spx_id']}")
    return len(rows)


def enrich_group(client, settings: Settings, conn, projects: list[dict], dry_run: bool, group_size: int) -> int:
    """docs/architecture-2026/01-data-platform.md P3: batch multiple
    projects per Gemini Pass-1 call. Fingerprint check and Tier-1 triage
    still run per-project (both are cheap/local or a single ungrounded
    call each) -- only the expensive GROUNDED Pass-1 discovery call is
    actually batched. A project the batch response omits (model skipped
    it, or the whole batch call failed) is simply left unresolved rather
    than marked 'done' with nothing -- it stays eligible for the next
    batch run instead of being silently written off."""
    survivors: list[tuple[dict, str]] = []  # (project, fingerprint)
    for project in projects:
        fingerprint = compute_source_fingerprint(conn, project)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_fingerprint, last_enriched_at FROM project_enrichment_checks WHERE project_sk = %s",
                (project["project_sk"],),
            )
            existing = cur.fetchone()
        if existing:
            prev_fingerprint, last_enriched_at = existing
            stale = last_enriched_at is None or (datetime.now(timezone.utc) - last_enriched_at).days >= 180
            if prev_fingerprint == fingerprint and not stale:
                print(f"  skip: unchanged fingerprint for {project['spx_id']}")
                continue

        triage = run_triage(client, settings.flash_model, project, conn=conn)
        if not triage.get("worth_full_pass", True):
            print(f"  triage: skipping full pass for {project['spx_id']} -- {triage.get('reason', '')!r}")
            if not dry_run:
                persist_checked_only(conn, project["project_sk"], fingerprint)
            continue
        survivors.append((project, fingerprint))

    total_facts = 0
    for chunk_start in range(0, len(survivors), group_size):
        chunk = survivors[chunk_start : chunk_start + group_size]
        chunk_projects = [p for p, _ in chunk]
        print(f"Pass 1 (batch discovery): {len(chunk_projects)} project(s)")
        try:
            batch_results = run_discovery_batch(client, settings.flash_model, chunk_projects, conn=conn)
        except Exception as e:  # noqa: BLE001 -- one bad batch shouldn't kill the whole run
            print(f"  BATCH FAILED for {len(chunk_projects)} projects: {e}", file=sys.stderr)
            continue

        for project, fingerprint in chunk:
            discovery = batch_results.get(project["project_sk"])
            if discovery is None:
                print(f"  {project['spx_id']} missing from batch response -- left pending, not marked done")
                continue
            try:
                total_facts += _finish_from_discovery(client, settings, conn, project, discovery, fingerprint, dry_run)
            except Exception as e:  # noqa: BLE001
                print(f"  FAILED ({project['spx_id']}): {e}", file=sys.stderr)

    return total_facts


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
    ap.add_argument(
        "--projects-per-call",
        type=int,
        default=1,
        help="--batch only: batch this many projects into one Pass-1 Gemini call (default 1 = today's "
        "unchanged one-per-call behavior). Pass 2/triage stay per-project even when > 1.",
    )
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
                    WHERE (c.project_sk IS NULL OR c.status != 'done' OR c.last_enriched_at < now() - interval '180 days')
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

            if args.projects_per_call > 1:
                total_facts = enrich_group(client, settings, conn, candidates, args.dry_run, args.projects_per_call)
                print(f"Batch complete: {len(candidates)} projects, {total_facts} total facts")
                return 0

            total_facts = 0
            for project in candidates:
                try:
                    llm_budget.check_budget(conn)
                except llm_budget.BudgetExceeded as e:
                    # Stops the WHOLE batch, not just this project -- a
                    # circuit breaker that keeps looping past a tripped
                    # cap (just skipping the current project and moving
                    # on) isn't actually breaking anything.
                    print(f"BUDGET CAP HIT, stopping batch early: {e}", file=sys.stderr)
                    break
                try:
                    total_facts += enrich_one(client, settings, conn, project, args.dry_run)
                except Exception as e:  # noqa: BLE001 -- one bad project shouldn't kill the whole batch run
                    print(f"  FAILED ({project['spx_id']}): {e}", file=sys.stderr)
                    if not args.dry_run:
                        with conn.cursor() as cur:
                            cur.execute(
                                "INSERT INTO project_enrichment_checks (project_sk, checked_at, status) "
                                "VALUES (%s, now(), 'failed') "
                                "ON CONFLICT (project_sk) DO UPDATE SET checked_at = now(), status = 'failed'",
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

        try:
            llm_budget.check_budget(conn)
        except llm_budget.BudgetExceeded as e:
            print(f"BUDGET CAP HIT: {e}", file=sys.stderr)
            return 1
        enrich_one(client, settings, conn, project, args.dry_run)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
