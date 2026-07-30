# SpecIndex Architecture 2026 — Productization: Custom LLM, MCP, Pricing

> STATUS: Gemini-reviewed 2026-07-30. Real findings below, incorporated into sections 1-3.

**Build status 2026-07-30: API-key auth (P0) and the Team invite/roster flow (P3, built jointly with identity doc's P4) shipped; MCP, Stripe metering, and the Vertex classifier stay unbuilt — see `00-MASTER-ROADMAP.md` for the authoritative per-item breakdown.** MCP was attempted and blocked on real tooling (the `mcp` SDK needs Python 3.10+, unavailable in this environment) rather than shipped unverified. The Vertex classifier stays unbuilt for the same reason `compute-project-scores.py`/`compute-lead-scores.py` use transparent formulas instead of ML elsewhere in this package: no labeled won/lost outcome history exists yet to train or validate against.

## Gemini Review Findings (incorporated 2026-07-30)

1. **Training a classifier to "explain" `project_scores` is counterproductive, not just unnecessary.** `project_scores` is a deterministic arithmetic formula — replacing/explaining it with a probabilistic fine-tuned model introduces hallucination risk over SpecIndex's own primary IP. If an enterprise buyer asks "why did this score 82," they want the deterministic component breakdown, not an LLM's guess at reasons. **Fix applied:** drop "priority-score-explain" as a classifier target entirely. The only classifier target Section 1 should pursue is genuinely predictive metadata (spec-window status, unstated product-category requirements from messy permit text) where real ground-truth labels exist and non-determinism adds value — not explaining an already-deterministic number.
2. **Vocabulary risk: don't say "custom LLM" in front of a technical enterprise buyer.** A CTO/CISO doing security diligence who sees `gemini-2.5-flash` system prompts labeled "our custom LLM" will stall the deal on transparency grounds. **Fix applied:** internal engineering and technical RFP language should say "SpecIndex Proprietary Construction Intelligence Engine" (domain RAG + deterministic scoring) — marketing copy can still say "SpecIndex's construction-intelligence model" since that's defensible, but never "custom LLM" in a technical context.
3. **MCP transport protocol was unspecified — a real gap, not a detail.** MCP needs either `stdio` (local only) or SSE (remote/hosted) transport; a Cloud-Run-hosted MCP server must expose SSE, not stdio, which doesn't work over the public web without a local bridge. **Fix applied:** Section 2 now specifies SSE transport (e.g. via a FastMCP ASGI app mounted at `/mcp`).
4. **MCP payload size will blow out agent context windows.** `GET /v1/projects` returning 20 full raw project objects (with nested arrays, coordinates, field histories) as one MCP tool response can hit 50KB+ — expensive and wasteful for an agent that just needs to decide which project to look at next. **Fix applied:** `search_projects` must return pruned summaries (id/name/score/location/status only), reserving full detail for `get_project_detail` on a specific id.
5. **`/v1/me/*`-style endpoints don't make sense for an API-key-authenticated MCP client.** `/v1/me/ask` implicitly reads the *signed-in human's* saved territory from Postgres — an enterprise API key represents an org/service account, not one person's session. **Fix applied:** MCP's `ask_about_territory` tool must accept explicit parameters (state codes, zip codes, or a territory id) rather than relying on session-bound `/v1/me/` state.
6. **Per-call usage metering on Enterprise creates real "bill shock" friction; included quotas are the better mechanism.** Manufacturers buying internal tooling access hate unpredictable variable monthly bills. **Fix applied:** Enterprise pricing (Section 3) should lead with a generous included quota (e.g. 50,000 calls/month within the base fee) with tier-based overage, not pure per-call metering.
7. **Gating all MCP access to Enterprise-only ($25K+) blocks a real mid-market use case.** Independent rep agencies and tech-savvy Pro/Team users will want to connect Claude Desktop or their own scripts via MCP well before they're an Enterprise-scale account. **Fix applied:** offer a rate-limited MCP tier on Pro/Team (e.g. 500 calls/month/seat), reserving Enterprise for bulk export, high rate limits, and SLAs — not MCP access itself.

## Ground truth: what exists today (api/main.py, db/migrations/013_project_scores.sql)

- **Full current API surface**: `/v1/projects`, `/v1/projects/facets`, `/v1/projects/map-points`,
  `/v1/projects/{id}`, `/v1/projects/{id}/ask`, `/v1/me/ask`, `/v1/me/profile`,
  `/v1/me/tracked-projects`, `/v1/me/saved-views`, `/v1/coverage` (+`/insights`), `/v1/quality`,
  `/v1/stats`, `/v1/documents/{id}`, `/v1/contact`, `/v1/ops/*`. Auth is Firebase session only
  (`require_firebase_user` / `require_firebase_user_or_build_token`). There is no API-key
  concept, no OAuth, no rate limiting beyond Cloud Run platform defaults, and no billing
  metering anywhere in the code.
- **"AI" today** is `_ask_gemini()`: one Vertex AI call (`gemini-2.5-flash`, `vertexai=True`,
  `google-genai` SDK) with a system prompt that forces answers strictly from a text block built
  by `_project_ask_context()` / `_territory_ask_context()` — rows pulled live from Postgres
  (`projects`, enrichment tables, `project_scores`, `user_tracked_projects`). There is no
  fine-tuning, no custom weights, no distillation pipeline. This is a prompted, grounded call
  over proprietary data, not a custom-trained model, and the doc below treats it that way.
- **The one real proprietary "model" logic** in the codebase is `project_scores`
  (`db/migrations/013_project_scores.sql`): `value_score + recency_score + news_score`, a
  transparent formula in `scripts/compute-project-scores.py`, fully re-derived on every
  pipeline run. It's explicitly documented in-repo as v1/adjustable, not ML — but it is the
  closest thing SpecIndex has to defensible IP beyond raw data coverage.
- **No plan-based limits are enforced anywhere in the API today.** The Free/Pro/Team split on
  `app/pricing/page.tsx` (1 brand check/week, unlimited search, competitor compare, etc.) is
  marketing copy only — there is no seat concept, no per-plan quota, and no Clerk Organizations
  wiring despite Clerk already being live for individual auth. This is a hard gap called out
  repeatedly below: **pricing tiers cannot be sold as real SKUs until the enforcement exists.**

---

## 1. "Custom LLM" — Requirements and Architecture Decision

**Requirement (from Asif):** a custom LLM model monetizable to enterprises.

**Decision: do not build or claim a custom-trained/fine-tuned foundation model.** Training a
foundation model from scratch is not realistic for this team or stage — no ML infra team, no
GPU budget, and nowhere near the data volume a competitive foundation model needs. Even
full-parameter fine-tuning of an open model is premature before there's a concrete labeled
task to justify it.

**What "custom LLM" honestly and defensibly means for SpecIndex today:**

SpecIndex's monetizable asset is the **Intelligence Layer** = proprietary corpus (205K+
projects, enrichment fields, linked source documents) + proprietary scoring methodology
(`project_scores`) + a grounded-RAG prompt layer (today's `_ask_gemini`, hardened for
production use). **The defensibility is the DATA and the SCORING IP — both of which require
SpecIndex's ingestion pipeline and jurisdiction coverage to reproduce — not the underlying
model weights, which are commodity Gemini that any competitor could call.** Calling today's
`_ask_gemini` a "custom LLM" as-is would be dishonest and would not survive enterprise
technical diligence; calling the *system it's embedded in* proprietary is accurate and
defensible.

Two concrete upgrades earn the "custom model" claim rather than just asserting it:

1. **A narrow supervised-tuned/distilled classifier**, not a chat model — e.g. **spec-window
   classification** ("will this project still accept new product specs — yes/no + confidence")
   or **priority-score-explain** (a model that predicts/explains the `project_scores` output in
   natural language). Trained via Vertex AI supervised tuning on top of a small Gemini/Gemma
   checkpoint, using labels that only exist inside SpecIndex's own corpus (enrichment history,
   score deltas, tracked-project outcomes once there's enough tracked-project data to label
   against). This is real, narrow, and genuinely hard to replicate without SpecIndex's data.
2. **"SpecIndex Answers"** — the RAG layer stays generic Gemini underneath, but is packaged and
   sold as a named enterprise product where the differentiation sold to the customer is the
   corpus it's grounded in and the scoring context it's given, not the base model. Internal
   engineering should never describe this as "our LLM" — external marketing can describe it as
   "SpecIndex's construction-intelligence model" honestly, because the intelligence is in the
   data/scoring, and that framing is defensible under scrutiny.

**Enterprise monetization:**

- **Hosted API tier**: usage-based, metered per `/ask` call and per bulk-export row. Target
  buyer: a manufacturer's own BI/analytics team who wants to pull SpecIndex's scored,
  enriched project data into their own systems.
- **VPC/on-prem deployment**: explicitly **not recommended near-term**. Current infra (Cloud
  Run + Cloud SQL + Vertex AI) has no packaging for customer-VPC deployment, and building that
  now is premature at current scale. Treat as an Enterprise-tier "ask" to defer past ~$1M ARR
  when a specific large account requires it contractually.
- **Usage-based pricing tied to query volume** (per-1K-call tiers) is the right mechanism, but
  it should be layered onto the Enterprise plan (section 3) rather than sold as a standalone
  product — it's a pricing lever, not a separate offering.

---

## 2. MCP Plan — Requirements and Architecture Decision

**Requirement:** programmatic data access via MCP for enterprise customers' own AI agents.

**Decision: MCP server as a thin wrapper over the existing FastAPI endpoints — no new data
layer, no new business logic.** The MCP server should call the same API that the web app
calls; it must not reimplement query logic against Postgres directly, so there is exactly one
place (the API) where auth, rate limiting, and data shaping live.

**Tools exposed** (each a direct pass-through to an existing endpoint):

| MCP tool | Wraps | Notes |
|---|---|---|
| `search_projects` | `GET /v1/projects` (+ `/facets`) | state/county/status/category filters, pagination |
| `get_project_detail` | `GET /v1/projects/{id}` | full enriched project record |
| `ask_about_project` | `POST /v1/projects/{id}/ask` | grounded Gemini Q&A on one project |
| `ask_about_territory` | `POST /v1/me/ask` | grounded Gemini Q&A across a rep's tracked territory |
| `get_coverage` / `get_quality` | `GET /v1/coverage`, `/v1/quality` | lets a customer's own QA agent check data freshness/coverage before trusting a pull — useful for BI pipelines, not just chat agents |

**Auth (the real gap):** the existing Firebase session cookie does not work for a headless MCP
client. This requires a **new API-key model** — a `require_api_key` FastAPI dependency parallel
to `require_firebase_user`, keys scoped to a customer account, stored with hashed secrets and a
usage counter (new `api_keys` / `api_key_usage` tables). **This is the same identity gap the
parallel identity/authz architecture doc needs to solve — API-key issuance and MCP auth should
be designed once, as one system, not twice.** OAuth client-credentials is a reasonable v2
upgrade once third-party (not just the customer's own internal) agents need to connect, but
API keys are sufficient and simpler for v1.

**Enterprise use case:** a manufacturer's internal sales-ops tooling — an AI agent that
monitors a territory and drafts rep alerts — or a BI pipeline pulling coverage/quality metrics
into the customer's own warehouse. This is a programmatic-access product for customers who
already run their own agents, not a chat-UI replacement.

**Monetization:** MCP/API access is gated to the **Enterprise tier only**, rate-limited by plan
(calls/month quota enforced at the API-key layer), reusing the same metering infrastructure
built for the hosted "Answers" API in section 1 — one billing mechanism, two product surfaces.

---

## 3. Pricing — Requirements and Architecture Decision

**Requirement:** evolve, not replace, the existing pricing thinking in
`docs/product-strategy.md` ("Monetization (initial)": Free / Pro / Team / later API+white-label)
and `app/pricing/page.tsx` (shipped copy: Free $0, Pro "Contact us" per seat, Team "Contact us"
multi-seat — no real numbers live today).

**ICP** (from `docs/product-strategy.md`'s Target users table): mid-market and enterprise
building-product manufacturers running active A&E specification programs; the practical daily
buyer/user is the manufacturer sales/territory rep or an independent rep agency covering a
multi-brand book.

| Tier | Illustrative price | Gate | Reality check vs. today's code |
|---|---|---|---|
| **Free** | $0 forever | Full national search, 1 brand check/week | Matches shipped `app/pricing/page.tsx` copy; the weekly brand-check cap is **not enforced anywhere in `api/main.py`** — currently a promise, not a control |
| **Pro** | $149/seat/mo annual ($179 month-to-month) | Unlimited brand checks, competitor compare (5 brands), territory digest | No seat concept or per-plan limit exists in the API today — this must be built as real enforcement, not just quoted as a price |
| **Team** | $129/seat/mo at 5+ seats | Multi-brand profiles, territory seats, list export, CRM export/API (roadmap) | **Blocked on Clerk Organizations**, which were deliberately deferred — cannot sell a real multi-seat SKU without org-scoped billing and membership, so Team should not be sold as a finished product until that's built |
| **Enterprise** | $25K–$75K/yr base + usage, scaled by seats/volume | MCP access, hosted "SpecIndex Answers" API, coverage/quality API, narrow custom classifier (section 1), dedicated jurisdiction priority | New; requires the API-key infrastructure from section 2 as a hard prerequisite |

**Reasoning for the numbers:** comparable B2B construction-data-intelligence products —
Dodge Construction Network and BuildingRadar-style search+alert products price core seats in
roughly the $100–300/mo per-seat range; construction-intelligence enterprise data/API deals
(the same category ConstructConnect's own DataConnect API competes in) typically land in the
$20K–75K/yr range depending on seat count and query volume. These anchor the Pro/Team seat
price and the Enterprise base fee above — they are not round numbers picked without a
reference point, but they should be validated against actual competitor list prices (Dodge,
BuildingRadar public pricing where available) before being quoted to a real prospect.

---

## Phased Build Plan

1. **Phase 0** — API-key auth (`require_api_key` dependency + `api_keys`/`api_key_usage`
   tables) — shared prerequisite for MCP access and Enterprise billing.
2. **Phase 1** — Enforce the Free-tier brand-check limit and Pro seat/usage limits already
   promised on the pricing page but absent from `api/main.py` today.
3. **Phase 2** — Ship the MCP server as a thin wrapper over the five endpoints above, deployed
   as its own Cloud Run service, authenticated with the Phase 0 API keys.
4. **Phase 3** — Wire Clerk Organizations so Team can be sold as a real multi-seat, org-scoped
   SKU rather than marketing copy.
5. **Phase 4** — Train the narrow Vertex AI supervised-tuned classifier (spec-window or
   priority-score-explain) on `project_scores` + enrichment data — the actual technical basis
   for a "custom model" claim to enterprise buyers.
6. **Phase 5** — Add Stripe usage-based metering for Enterprise query-volume pricing once real
   MCP/API traffic exists to bill against.

---

## Action Items

- ✅ SHIPPED 2026-07-30 as migration 031 (`api_keys`/`api_key_usage` tables + `require_api_key` dependency + `/v1/me/api-keys` CRUD): Ship API-key auth as the shared prerequisite for MCP access and Enterprise billing. Not yet wired into any consuming endpoint — MCP itself (P2) still needs to be built.
- P1: Enforce the Free-tier 1-brand-check/week limit and Pro seat/usage limits already promised on the pricing page but not implemented in `api/main.py`.
- P2: Ship the MCP server as an SSE-transport (not stdio) thin wrapper over `/v1/projects` (pruned summaries only), `/v1/projects/{id}` (full detail), `/v1/projects/{id}/ask`, a parameterized `ask_about_territory` (not session-bound `/v1/me/ask`), `/v1/coverage`, and `/v1/quality`.
- P2: Offer a rate-limited MCP tier on Pro/Team (Gemini: don't gate all MCP access to Enterprise-only — blocks a real mid-market use case).
- P3: Wire the org_id/org-seat model (see Identity & Portals doc) before selling Team as a real multi-seat, org-billed SKU.
- P4: Train a narrow Vertex AI supervised-tuned classifier on spec-window status or unstated product-category requirements — NOT priority-score-explain (Gemini: explaining a deterministic formula with a probabilistic model introduces hallucination risk over SpecIndex's own primary IP).
- P5: Add Stripe usage-based metering for Enterprise, leading with a generous included quota (e.g. 50K calls/mo) rather than pure per-call billing (Gemini: per-call metering alone creates "bill shock" friction for this buyer).
