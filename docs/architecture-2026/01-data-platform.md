# Data Platform Architecture — Cost Control, Enrichment Tracking, Agent Query Access, Entity Directories

Status: draft for architecture package, pre-100-engineer scale-up.
Grounded in the real running system as of 2026-07-29/30: `docs/ROADMAP.md`, `scripts/state_agent_pipeline/` (Flash → Sonnet ingestion), `scripts/enrich-project-details.py` (two-pass Gemini enrichment), `db/migrations/016_project_enrichment.sql` (already-built enrichment tables), `db/schema.sql` (free-text `owner`/`architect`/`general_contractor`, unnormalized `mentioned_brands`/`competitor_watch` JSONB arrays).

**Review status: Gemini-reviewed 2026-07-30.** Real, substantive findings below — incorporated into the schemas and action items throughout this doc.

## Gemini Review Findings (incorporated 2026-07-30)

1. **Grounding paradox in the fingerprint gate (Section 3).** `source_fingerprint` only changes when *local* data changes, but enrichment is supposed to discover *external* web content. A sparse project's fingerprint never changes, so it would be permanently frozen and never re-checked for newly published external info. **Fix applied:** add a max-staleness fallback — re-evaluate if fingerprint changed OR `last_enriched_at < now() - interval '180 days'`, whichever comes first.
2. **Over-merging risk in `general_contractors` (Section 5).** A global `UNIQUE (normalized_name)` will collide unrelated regional companies with the same common name across states (e.g. "Apex Construction" exists in dozens of states as distinct entities). **Fix applied:** scope uniqueness to `UNIQUE (normalized_name, state)`.
3. **Postgres NULL behavior bug in `people` (Section 5).** `UNIQUE (normalized_name, firm_name)` allows unlimited duplicate rows when `firm_name` is NULL (common in permit data) — `NULL != NULL` in standard SQL. **Fix applied:** use `UNIQUE NULLS NOT DISTINCT (normalized_name, firm_name)` (Postgres 15+).
4. **Hidden cost dominator: Vertex Search Grounding fees are NOT token-based.** Google charges a fixed per-search-request fee (~$35/1,000 queries) independent of token count, which can dwarf token cost by 10-50x on sparse prompts. `llm_call_log`'s token-only cost model would under-calculate real spend by orders of magnitude. **Fix applied:** add `grounding_requests_count` to `llm_call_log` and price it separately in the cost calculator.
5. **Agent read-replica needs hard guardrails, not just isolation.** A broad unindexed agent query can still saturate replica CPU/IOPS and spike replication lag even when isolated from production. **Fix applied:** `ALTER ROLE agent_readonly SET statement_timeout = '15s'` and `default_transaction_read_only = on`.
6. **Missing: entity merge lineage.** When Phase 2/3 merges Contractor A into Contractor B, nothing records the old identity — the next day's pipeline run re-creates a duplicate under the old name. **Gap flagged, not yet designed:** needs an `entity_aliases` table (`deprecated_id -> canonical_id`) before Phase 2 ships, added as a new P2 item below.
7. **Missing: Vertex rate-limit/quota handling at scale.** Moving from 205K to 6.5M projects cannot rely on simple sequential script loops — Vertex has RPM/TPM quotas per GCP project. **Gap flagged:** needs an async task queue with rate-limiting and exponential backoff on 429s before Phase 3's batching work, added as a new P3 item below.

---

## 1. Requirements

1. LLM spend must scale sub-linearly with corpus size (205K projects today, "6.5M+" referenced as the addressable universe in code/docs) — a flat per-project two-pass Gemini call does not survive that scale.
2. No project should ever be re-enriched by a full LLM pass unless its underlying source data actually changed, or the enrichment prompt/schema version changed.
3. Cost must be a first-class, queryable metric in Postgres — not something reconstructed from GCP billing exports after the fact.
4. An AI agent (Claude, or a future internal tool) must be able to query the business's real state — coverage, enrichment freshness, cost, pipeline health — without tribal knowledge of 15+ raw tables, and without competing with production API traffic for connections.
5. Three new directory features (manufacturers, general contractors, "other people") need real normalized entities, not the free-text/JSONB status quo, with an honest phased plan for entity resolution.

---

## 2. Problem 1 — Token-cost controls

### Where the risk actually lives today

Two real call sites, both currently uncapped:

- `scripts/gemini_discovery_chat.py` — one grounded Gemini call per message, in a durable per-jurisdiction session (`data/gemini_sessions/{name}.json`). This is a human-in-the-loop research tool today, called manually, so volume is naturally bounded by a person typing. Risk: someone (or a future automation) scripts a loop over all uncovered counties and fires hundreds of grounded calls unattended.
- `scripts/enrich-project-details.py` — **two full Gemini passes per project** (discovery + independent cross-check), run manually, gated only by a 30-day cooldown recorded in `project_enrichment_checks`. This is the actual scaling risk: at 205K projects, a naive "enrich everything every 30 days" cron is 410K+ grounded Gemini calls/month before the corpus even grows. At the referenced 6.5M-project ceiling, that pattern is not viable at any reasonable budget.

The ingestion pipeline (`scripts/state_agent_pipeline/pipeline.py`) already solved a version of this problem correctly — generalize it rather than inventing something new:

```python
NO_LLM_PROVIDER_TYPES = {"sam_gov", "usaspending", "accela", "energov", "tdlr_tabs"}
```

Structured government feeds skip Flash/Sonnet entirely; only messy free-text sources pay the LLM cost. That's the same shape of decision needed for enrichment and discovery — the fix is to apply it one layer further out, and to make the middle tier ("cheap model") actually exist for enrichment, where today it's binary (skip vs. two full Gemini passes).

### Proposed tiered strategy (generalizing Flash → Sonnet)

| Tier | Used for | Cost |
|---|---|---|
| 0. Deterministic / no LLM | Structured feeds already routed via `NO_LLM_PROVIDER_TYPES`; for enrichment, any field already present verbatim in `project_sources`/`project_documents`/permit record text (regex/parse pass) | ~$0 |
| 1. Cheap model (Gemini Flash) | High-recall first pass: entity extraction (already exists for ingestion), and — new — a "is there anything worth enriching here at all" triage call for enrichment before spending a full search-grounded pass | Cheap |
| 2. Expensive model (Sonnet / Gemini Pro w/ grounding) | Dedup/golden-record judgment (exists), and the two-pass enrichment discovery + cross-check (exists) — but now gated behind tier 0/1 and behind the fingerprint check in Problem 2 | Expensive, last resort |

Concretely, insert a **Tier-1 triage call** into `scripts/enrich-project-details.py` before Pass 1: a single cheap Flash call (no search grounding) that looks at what's already in `project_sources`/`project_documents`/`projects` free-text fields and returns "worth a full grounded pass: yes/no + which sections." Skip Pass 2 (cross-check) entirely for low-stakes/low-value projects (e.g. below a `project_scores.score` threshold) — reserve the expensive independent cross-check for projects actually worth the cost (high score, high `estimated_value_usd`), matching the existing "team/contacts/permits are highest-stakes" reasoning already in the script's own docstring.

### Caching / dedup of identical queries

- `gemini_discovery_chat.py` sessions are keyed by jurisdiction name and persisted to disk — good for conversational continuity, but there's no dedup across sessions if two people (or two automation runs) investigate the same county twice. Add a lightweight `data/gemini_query_cache/` (or a Postgres table, see below) keyed by a hash of `(session_type, normalized_query_text)` with a TTL (e.g. 90 days for source-discovery, since county source pages don't change often) — check the cache before firing a grounded call, not just before starting a new named session.
- For enrichment, the fingerprint in Problem 2 IS the cache key — if the fingerprint hasn't changed, don't call Gemini at all, full stop, regardless of the 30-day cooldown. This is a bigger lever than time-based cooldown: most projects' source data doesn't change month to month, so fingerprint-gating should eliminate the majority of re-enrichment calls, not just delay them.

### Batching

Both scripts today make one call per project/query, serially. Gemini's batch API (or simply larger prompts covering N projects per call, N in the 5–20 range depending on prompt size limits) can amortize the fixed request overhead. This matters more as volume scales; it is explicitly NOT worth the engineering effort at 205K projects with manual, human-gated enrichment — flag as Phase 2/3, not now.

### Budget caps and circuit breakers

None exist today. Concrete proposal:
- A `llm_call_budget` config (env-driven, per environment) with a daily/monthly dollar ceiling.
- A new Postgres table (see below) that every LLM call site writes a row to, with model, tokens in/out, estimated cost, and call site name.
- A circuit breaker checked at the top of every call-site loop (`enrich-project-details.py`'s `--limit` loop, `gemini_discovery_chat.py` if ever automated): if the day's running total exceeds the cap, stop and exit non-zero rather than silently continuing — loud failure, not silent overspend. This is the same "loud, not silent" philosophy already used for confidence conflicts in the enrichment script (`reported` vs. silently resolved).

### Cost-per-project metric in Postgres

```sql
-- 027_llm_call_log.sql
-- Every LLM call from every call site (ingestion Flash/Sonnet, enrichment
-- passes, discovery chat) logs one row here -- the real, queryable
-- cost-per-project metric that doesn't exist today. GCP billing exports
-- tell you total spend; this tells you spend BY PROJECT and BY CALL SITE,
-- which is what a budget circuit breaker and a "why did this cost so
-- much" query both need.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS llm_call_log (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk      BIGINT REFERENCES projects(project_sk) ON DELETE SET NULL,  -- NULL for non-project calls (e.g. discovery chat)
  call_site       TEXT NOT NULL,   -- 'ingestion_flash' | 'ingestion_sonnet' | 'enrich_pass1' | 'enrich_pass2' | 'enrich_triage' | 'gemini_discovery_chat'
  model           TEXT NOT NULL,   -- 'gemini-2.5-flash' | 'gemini-2.5-pro' | 'claude-sonnet-...'
  input_tokens    INTEGER,
  output_tokens   INTEGER,
  estimated_cost_usd NUMERIC(10,6),
  grounded        BOOLEAN NOT NULL DEFAULT false,
  called_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS llm_call_log_project_sk ON llm_call_log (project_sk);
CREATE INDEX IF NOT EXISTS llm_call_log_called_at ON llm_call_log (called_at);
CREATE INDEX IF NOT EXISTS llm_call_log_call_site ON llm_call_log (call_site, called_at);

COMMIT;
```

A daily materialized view (`v_llm_daily_spend`) rolls this up by `call_site`/`model`/day — this is exactly the kind of view an agent (Problem 3) should be able to query directly.

### Interaction with Problem 2's enrichment table

The cost controls and the enrichment tracking table are the same mechanism viewed from two angles: `project_enrichment_checks` (extended per Problem 2) is the gate that decides whether a call happens at all; `llm_call_log` is the record of what it cost when it did. The fingerprint column is what makes the gate cheap to evaluate (a hash comparison) instead of a heuristic (a 30-day timer).

---

## 3. Problem 2 — Enrichment dedup/tracking table

**Already exists, checked directly**: `db/migrations/016_project_enrichment.sql` created both `project_enrichment` (per-fact results) and `project_enrichment_checks` (project_sk PK, `checked_at` timestamp — a bare cooldown, no fingerprint, no version, no status). `api/main.py` reads `checked_at` for display; `enrich-project-details.py` writes it after every attempt and uses a 30-day `WHERE checked_at < now() - interval '30 days'` filter to pick the next batch. So the "do we know if it's already been enriched" half is solved; the "was it *worth* re-enriching" half is not — today it blindly re-enriches every project older than 30 days even if nothing about the project changed.

### Delta: extend `project_enrichment_checks`, don't duplicate it

```sql
-- 027_project_enrichment_checks_fingerprint.sql
-- Extends the existing project_enrichment_checks table (016) with the
-- three things it's missing: a fingerprint of the source data actually
-- fed into the enrichment prompt (so "re-enrich if changed" replaces
-- "re-enrich if 30 days old"), a schema/prompt version (so a future
-- prompt change can selectively force re-enrichment instead of an
-- all-or-nothing backfill), and an explicit status (today "attempted"
-- is implied by row existence; failures are indistinguishable from
-- untried projects, which silently wastes retries).
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE project_enrichment_checks
  ADD COLUMN IF NOT EXISTS source_fingerprint TEXT,
  ADD COLUMN IF NOT EXISTS enrichment_version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'done', 'failed', 'stale')),
  ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ;

-- last_enriched_at is distinct from checked_at: checked_at fires on every
-- ATTEMPT (including "found nothing, don't retry for 30 days");
-- last_enriched_at only advances when the attempt actually wrote new/
-- changed rows into project_enrichment. A project that legitimately has
-- no public info gets checked_at bumped but last_enriched_at stays NULL
-- forever -- distinguishing "we looked and there's nothing" from
-- "we successfully enriched this."

CREATE INDEX IF NOT EXISTS project_enrichment_checks_status
  ON project_enrichment_checks (status)
  WHERE status IN ('pending', 'stale');

COMMIT;
```

`source_fingerprint` = a hash (e.g. sha256, truncated) computed in `enrich-project-details.py` over the concatenation of the fields the two Gemini passes actually condition on: `projects.name/address/owner/architect/general_contractor/description`, plus the set of `project_sources` URLs/titles and `project_documents` filenames for that project. Computed in code, stored alongside the check — the same "never trust the LLM to compute a stable ID, compute it yourself" discipline already used for `canonical_golden_id()` in `model_b_sonnet.py`.

`enrichment_version` bumps whenever the enrichment prompt or output schema changes (e.g. adding a new section). The selection query in `enrich-project-details.py` becomes:

```sql
WHERE status != 'done'
   OR source_fingerprint IS DISTINCT FROM %(new_fingerprint)s
   OR enrichment_version < %(current_version)s
```

This replaces the blind 30-day timer with "re-enrich only if something that would change the answer actually changed" — the direct fix for the token-cost problem in Problem 1, and it costs one migration plus a fingerprint function, not a new table.

---

## 4. Problem 3 — A robust, queryable database for an AI agent

### What "robust and queryable for an agent" concretely means here

Not a new database engine, and not (yet) a semantic layer. Three concrete pieces:

1. **A read replica for agent/analytics traffic.** Today there is one Cloud SQL Postgres instance serving both the production read API (`api/main.py`, Cloud Run) and anything ad hoc (an agent, a person running psql). At current scale this is fine; it stops being fine the moment an agent runs a broad, unindexed exploratory query during a traffic spike on the live site. Cloud SQL supports read replicas natively — stand one up, point agent/BI access at the replica's connection string, and the production API never contends with it. This is a P1, not a P0: do it before an agent is given standing query access in a workflow that matters, not before.

2. **A small set of well-commented SQL views, not a dbt semantic layer, at this stage.** The repo already has the right instinct — `v_project_stats` in `db/schema.sql` is exactly this pattern. Extend it: `v_llm_daily_spend` (Problem 1), `v_enrichment_coverage` (% of projects with `status = 'done'` and current fingerprint, by state), `v_county_coverage_summary` (thin wrapper matching what `county_coverage`/`state_quality` already track per ROADMAP item 26), `v_pipeline_health` (last run per state from `pipeline_runs`, success/failure). A dbt-style semantic layer is real engineering investment (a new tool, a new deploy pipeline, a team that owns metric definitions) that isn't justified at one Postgres instance and ~15 core tables — the honest call is: views now, revisit dbt if/when there are multiple data marts or multiple teams disagreeing about what "an active project" means. Each view's header comment should state its grain and its freshness (e.g. "recomputed on read" vs "materialized nightly") so an agent reading the view definition doesn't have to guess.

3. **Connection point to MCP.** `docs/ROADMAP.md` already references an MCP data-access plan (line mentioning Drive MCP tools). The views above are exactly what an MCP Postgres/SQL server would expose as tools/resources — an MCP server should be pointed at the read replica, scoped to the views (not raw tables) via a dedicated read-only role (`agent_readonly`), so "give an agent DB access" means "grant SELECT on `v_*` views to one Postgres role," not "hand over the primary's credentials." This doc doesn't design the MCP server itself — that's a separate, smaller task once the views and the replica exist.

---

## 5. Directories — manufacturers, general contractors, "other people"

### The real problem: `projects` has no normalized entities today

`db/schema.sql` stores `owner`, `architect`, `general_contractor` as free TEXT, and `mentioned_brands`/`competitor_watch` as JSONB arrays of strings. "ABC Construction" and "ABC Construction LLC" are two different strings with no relationship. This is a genuinely hard, unbounded-effort problem (entity resolution) — the plan below is deliberately phased so early phases ship real value without pretending the hard part is solved.

### Phase 1 (now): simple normalization heuristics, new tables, no ML

New normalized tables, populated by a batch script that runs simple heuristics (strip legal suffixes — LLC/Inc/Corp/Co, lowercase+trim, collapse whitespace, drop punctuation) to produce a `normalized_name` used as a natural dedup key. This alone catches the common case (suffix variants, casing, punctuation) without any fuzzy matching or LLM calls.

```sql
-- 028_entity_directories.sql
-- Manufacturers, general contractors, and "other people" (engineers,
-- architects, owners' reps) as first-class normalized entities, joined
-- back to projects. Phase 1: simple string normalization only (strip
-- legal suffixes, casing, punctuation) -- NOT fuzzy or LLM-resolved yet;
-- see docs/architecture-2026/01-data-platform.md Section 5 for the
-- phased plan. raw_name is preserved on every join row so a bad merge
-- is always recoverable by re-deriving from source text.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS manufacturers (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  canonical_name    TEXT NOT NULL,
  normalized_name   TEXT NOT NULL UNIQUE,  -- Phase-1 dedup key
  website           TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS general_contractors (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  canonical_name    TEXT NOT NULL,
  normalized_name   TEXT NOT NULL UNIQUE,
  city              TEXT,
  state             CHAR(2),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS people (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  canonical_name    TEXT NOT NULL,
  normalized_name   TEXT NOT NULL,   -- NOT unique alone: common names collide across firms
  role              TEXT,            -- 'engineer' | 'architect' | 'owners_rep' | other free text
  firm_name         TEXT,
  UNIQUE (normalized_name, firm_name),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Join tables: many-to-many, raw_name preserved for auditability/rollback.
CREATE TABLE IF NOT EXISTS project_manufacturers (
  project_sk       BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  manufacturer_id  BIGINT NOT NULL REFERENCES manufacturers(id) ON DELETE CASCADE,
  raw_name         TEXT NOT NULL,   -- exact string as it appeared in mentioned_brands/competitor_watch
  resolution_method TEXT NOT NULL DEFAULT 'heuristic',  -- 'heuristic' | 'fuzzy' | 'llm' | 'manual'
  PRIMARY KEY (project_sk, manufacturer_id)
);

CREATE TABLE IF NOT EXISTS project_general_contractors (
  project_sk       BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  gc_id            BIGINT NOT NULL REFERENCES general_contractors(id) ON DELETE CASCADE,
  raw_name         TEXT NOT NULL,
  resolution_method TEXT NOT NULL DEFAULT 'heuristic',
  PRIMARY KEY (project_sk, gc_id)
);

CREATE TABLE IF NOT EXISTS project_people (
  project_sk       BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  person_id        BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  raw_name         TEXT NOT NULL,
  role              TEXT,
  resolution_method TEXT NOT NULL DEFAULT 'heuristic',
  PRIMARY KEY (project_sk, person_id)
);

CREATE INDEX IF NOT EXISTS project_manufacturers_mfr ON project_manufacturers (manufacturer_id);
CREATE INDEX IF NOT EXISTS project_gcs_gc ON project_general_contractors (gc_id);
CREATE INDEX IF NOT EXISTS project_people_person ON project_people (person_id);

COMMIT;
```

### Phase 2: fuzzy matching for what heuristics miss

Trigram similarity (Postgres `pg_trgm`, already low-effort to enable) for near-duplicates the suffix-strip heuristic doesn't catch ("Turner Construction" vs "Turner Const. Co" vs a typo). Run as a scheduled batch job that proposes merges above a similarity threshold into a review queue — never auto-merge silently; a wrong merge corrupts a directory permanently unless raw_name is kept (it is, by design above).

### Phase 3: LLM-assisted resolution for the long tail

For ambiguous cases fuzzy matching can't resolve confidently (genuinely different companies with similar names, or company name changes/acquisitions), a cheap-model (Flash) pass that takes the candidate pair plus surrounding project context (address, project type) and returns same/different with a confidence — same tiered-cost discipline as Problem 1: only spent on the residual the cheaper methods couldn't resolve, never on the whole corpus.

Be honest about effort: full entity resolution at 6.5M-project scale is a multi-quarter, dedicated-team problem elsewhere in the industry (this is what Dun & Bradstreet-style master data management exists to solve). Phase 1 is worth doing now and ships real directory value; Phase 3 should not be scheduled until Phase 1's actual duplicate rate is measured and shown to matter at current scale.

---

## 6. Phased build plan

**Phase 1 (now, low-lift, unblocks everything else):**
- Fingerprint/version/status columns on `project_enrichment_checks`.
- `llm_call_log` table + instrumentation at the 3 existing call sites.
- `v_project_stats`-style views: `v_llm_daily_spend`, `v_enrichment_coverage`, `v_pipeline_health`.
- Entity-directory tables + Phase-1 heuristic normalization batch script.

**Phase 2 (once Phase 1 is live and cost data exists):**
- Budget cap + circuit breaker wired into `enrich-project-details.py` and any future automated `gemini_discovery_chat.py` runner.
- Read replica for agent/analytics access; `agent_readonly` role scoped to `v_*` views.
- Tier-1 triage call inserted before enrichment Pass 1; Pass 2 gated by `project_scores`.
- Fuzzy-matching (pg_trgm) pass for entity directories.

**Phase 3 (once volume actually demands it):**
- Batching multiple projects per Gemini call.
- LLM-assisted entity resolution for the fuzzy-matching residual.
- Revisit dbt-style semantic layer only if multiple teams/data marts exist.

---

## 7. Priority-tagged action items

- P0: Add `source_fingerprint`, `enrichment_version`, `status`, `last_enriched_at` columns to `project_enrichment_checks` (migration 027).
- P0: Compute and store `source_fingerprint` in `enrich-project-details.py`; gate re-enrichment on fingerprint/version change, not just the 30-day timer.
- P0: Create `llm_call_log` table (with `grounding_requests_count`, priced separately from tokens — Gemini: Vertex Search Grounding is a fixed per-search fee, not token-based, and can dwarf token cost 10-50x) and instrument `enrich-project-details.py` (both passes) and `model_a_flash.py`/`model_b_sonnet.py` to write a row per call.
- P0: Add a max-staleness fallback (180 days) to the fingerprint re-enrichment gate — a fingerprint alone can never change for a permanently-sparse project, freezing it out of re-checks forever (Gemini-flagged "grounding paradox").
- P1: Add `v_llm_daily_spend`, `v_enrichment_coverage`, `v_pipeline_health` views.
- P1: Add a Tier-1 cheap-model triage call in `enrich-project-details.py` before Pass 1.
- P1: Gate Pass 2 (cross-check) behind a `project_scores` value/priority threshold instead of running it unconditionally.
- P1: Create `manufacturers`, `general_contractors` (scoped `UNIQUE (normalized_name, state)`, not global — Gemini: regional companies share common names across states), `people` (`UNIQUE NULLS NOT DISTINCT (normalized_name, firm_name)` — plain `UNIQUE` allows unlimited NULL-firm_name duplicates) tables + join tables and a Phase-1 heuristic normalization batch script.
- P2: Add a hard daily/monthly LLM budget cap with a circuit breaker in both `enrich-project-details.py` and any automated discovery-chat runner.
- P2: Stand up a Cloud SQL read replica; create an `agent_readonly` Postgres role scoped to `v_*` views only, with `statement_timeout = '15s'` and `default_transaction_read_only = on` (Gemini: isolation from production alone doesn't stop one broad query from saturating replica CPU/IOPS).
- P2: Add query-result caching (hash of normalized query text, TTL) for `gemini_discovery_chat.py`.
- P2: Add an `entity_aliases` table (`deprecated_id -> canonical_id`) before Phase 2 fuzzy-matching ships (Gemini-flagged gap: without it, the next day's pipeline run re-creates a duplicate under the old name every time two entities are merged).
- P3: Enable `pg_trgm` and build the fuzzy-matching merge-proposal batch job for entity directories.
- P3: Batch multiple projects per Gemini enrichment call instead of one-per-call.
- P3: Add an async task queue with rate-limiting/exponential backoff for Vertex RPM/TPM quota errors before scaling past sequential per-project script loops (Gemini-flagged gap for the 205K-to-6.5M growth path).
- P4: LLM-assisted entity resolution pass for the fuzzy-matching residual.
- P5: Evaluate a dbt-style semantic layer if/when multiple teams or data marts exist.
