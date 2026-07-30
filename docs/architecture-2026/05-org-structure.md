# SpecIndex at 100 People — Org Structure

Scope note: this models the org SpecIndex would need to actually execute the
four architecture docs in this package (data platform, identity/portals,
growth, productization) at scale — not a generic startup org chart. Team
sizes are sized against the real backlog those docs describe (entity
resolution, an admin portal, MCP + API productization, lead scoring), not
round numbers.

## Leadership (5)
- CEO/Founder (Asif)
- VP Engineering
- VP Product
- VP Sales & Customer Success
- VP Data & Coverage (owns the ingestion/coverage moat specifically — see
  `[[project_specindex_mls_vision]]`; this is not a generic "Head of Data,"
  it's the single owner of the thing that's actually the company's
  defensibility)

## Engineering (42)

**Platform & Core API (10)** — owns `api/main.py`'s decomposition (see
`01-data-platform.md` §4 and `02-identity-portals.md` — this is also where
the microservices/service-boundary split for a 100-eng team gets decided;
`api/main.py` as one monolithic FastAPI file stops being tenable well before
headcount reaches this size). Owns auth/authz (`user_roles`, `require_role`),
billing integration, API-key/MCP infrastructure.

**Data Platform & Pipeline (12)** — owns ingestion (`state_agent_pipeline/`),
enrichment cost controls and the `llm_call_log`/fingerprint work from
`01-data-platform.md`, entity resolution (manufacturers/GCs/people
directories), and the read-replica/agent-query infrastructure. This is the
largest single engineering team, sized to match "national → state → county"
being the core, ongoing, never-finished work — see `docs/ROADMAP.md`'s
standing goal.

**Frontend & Portals (10)** — owns the marketing site, the signed-in
user portal (`SignedInHome` and its growth per `02-identity-portals.md`
§4.1), and the net-new admin portal (§4.2). Splits into a marketing-site
sub-team (2-3) and an app/portal sub-team (7-8) once the admin portal
ships — don't split earlier, it's one codebase today.

**AI/ML (6)** — owns the Gemini-grounded ask endpoints, the "custom LLM"
work from `04-productization.md` (the narrow Vertex-tuned classifier, not a
foundation model), prompt/cost tuning across the whole pipeline in
partnership with Data Platform.

**Infrastructure/SRE (4)** — Cloud Run, Cloud SQL (including the read
replica), CI/CD, the eventual re-enabling of scheduled pipeline crons
currently disabled per `docs/ROADMAP.md`.

## Data & Research (18)

**Coverage Research (10)** — the human side of what's currently done
ad hoc in Claude Code sessions: jurisdiction discovery, source
verification, dead-end documentation. At 100 people this is a real team
with a real backlog tracker, not one person running Gemini discovery
chats — but the same discipline applies (verify every source live,
document dead ends, largest-counties-first).

**Data Quality (4)** — owns `state_quality`, the `county_coverage`
freshness problem this session found (sources pulled but never merged),
and the entity-resolution accuracy loop (Phase 2/3 in
`01-data-platform.md` §5).

**Content Enrichment (4)** — owns the manual/semi-automated enrichment
pipeline scale-up, works directly with AI/ML on cost/quality tradeoffs.

## Growth (20)

**Marketing (7)** — SEO, content, the analytics/lead-capture
architecture in `03-growth.md`.

**Sales (9)** — inbound (working the `lead_scores`-prioritized queue
from `03-growth.md` §3), outbound/enterprise (selling the Enterprise
tier + MCP access + custom model from `04-productization.md`).

**Customer Success (4)** — owns retention/expansion once Team/Enterprise
tiers exist; doesn't need to exist before that revenue does.

## G&A (15)
- Finance/Ops (5)
- People/Recruiting (4)
- Legal/Compliance (2) — data-sourcing legal review scales with coverage,
  not headcount; keep this small but real once county-by-county sourcing
  reaches jurisdictions with actual usage restrictions
- Exec/Admin support (4)

## Sequencing note

Don't hire this org chart in one motion. The real ordering, tied to the
P0/P1 items in the master roadmap: Platform & Core API and Data Platform
teams justify themselves first (they're already the largest real backlog);
Growth hiring should trail the lead-scoring/CRM work actually shipping,
not precede it; Customer Success shouldn't exist before there's a paid
Team/Enterprise customer to retain.
