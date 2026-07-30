# SpecIndex — Master Technical Architecture (2026-07-30)

**Status:** Reviewed. Four of five sections were written against the real
codebase by independent research passes, grounded in actual files (cited
inline in each doc), then each given a real Gemini/Vertex critical review
(2026-07-30, after `gcloud` re-authentication) — findings folded directly
into each doc's schemas and action items, not just appended as notes. Real
issues the review caught and that are now fixed in the docs: a data-
freezing bug in the enrichment fingerprint gate, an entity-normalization
uniqueness bug that would corrupt the GC/people directories, an
undercounted LLM cost model missing Vertex's per-search grounding fee, a
1-hour JWT-revocation gap in the authorization design, an unrealistic
"explain the score with an LLM" productization idea, and an MCP transport
gap. See each doc's own "Gemini Review Findings" section for the full list.

**Also done since the first draft:** the 327,561-project merged national
corpus (see Immediate next steps, previously blocked) is now loaded into
production Postgres — 205,161 → 328,327 real projects live.

**Correction carried through from doc 02, applies to doc 04 as well:**
the repo migrated from Clerk to Firebase Auth (`db/migrations/025_clerk_to_firebase_auth.sql`)
concurrently with this work. Doc 04's productization plan mentions "wiring
Clerk Organizations" for Team-tier — that's now stale. The real seam is
doc 02's `org_id` column proposal on `user_profiles` (§3.3), which is
Firebase-Auth-compatible. Read Team-tier multi-seat plans through that
lens, not Clerk's.

This master doc is an index + synthesis. Each linked doc is the full
detailed spec — read the doc itself before implementing, this summary
intentionally compresses the "why."

## The five sections

1. **[Data Platform](01-data-platform.md)** — token-cost controls for
   scraping/enrichment, an enrichment-tracking table (extends the
   existing `project_enrichment_checks`, doesn't duplicate it), a
   read-replica + views plan for agent/AI query access, and a phased
   entity-resolution plan for manufacturer/GC/people directories.
2. **[Identity & Portals](02-identity-portals.md)** — onboarding (builds
   on the existing, unbuilt `docs/PRD_SIGNUP_CRM.md`), the real gap
   (zero authorization/role model today), a Postgres-source-of-truth
   `user_roles` design, and requirements for the user portal's growth
   and the fully-unbuilt admin portal.
3. **[Growth](03-growth.md)** — SEO/structured-data gaps on the
   marketing site, an analytics stack recommendation (PostHog Cloud),
   and a `project_scores`-style decomposed lead-scoring design that
   turns existing engagement data (tracked projects, saved views,
   Gemini-ask usage) into a sales-prioritized queue.
4. **[Productization](04-productization.md)** — an honest framing of
   what "custom LLM" can defensibly mean here (the corpus + scoring
   methodology + RAG layer, not a foundation model), an MCP server plan
   as a thin wrapper over the existing API, and a pricing tier structure
   evolved from the current (unenforced) pricing page copy.
5. **[Org Structure at 100](05-org-structure.md)** — team sizes and
   sequencing tied directly to the real backlog in docs 1-4, not a
   generic chart.

## Cross-cutting architecture decisions (appear in more than one doc)

**Auth is the seam everything else depends on.** Doc 02's `require_role()`
FastAPI dependency pattern is the enforcement point for: Free/Pro/Team/
Enterprise tier limits (doc 04 §3), the admin portal's customer-visibility
features (doc 02 §4.2), and the API-key auth MCP needs (doc 04 §2). Build
`user_roles` + `require_role()` once, correctly, before any of those three
consumers, rather than each inventing its own ad hoc check. This is why
doc 02's P0 items ("Add `026_user_roles.sql`", "Build `require_role()`")
are also effectively P0 for the other three docs even though they don't
say so themselves.

**The `project_scores` decomposed-score philosophy is SpecIndex's real
design pattern, and it recurs on purpose.** Doc 01's entity-confidence
scoring, doc 03's lead-scoring formula, and doc 04's framing of the
priority score as the actual proprietary "model" all consciously mirror
`project_scores`'s transparent, explainable, weighted-component design
(see `ProjectScoreBadge.tsx`). This is a real, load-bearing convention —
new scoring systems in this codebase should keep following it, not
introduce a different (e.g. black-box ML) pattern without a strong reason.

**Cost discipline is one architecture, not four.** Doc 01's LLM
budget-cap/circuit-breaker design, doc 01's read-replica isolation for
agent queries, and doc 04's API-key rate limiting for MCP/paid tiers are
the same underlying concern (don't let unmetered access — human, agent,
or paid customer — silently blow up cost or contend with production
traffic) applied to three different actors. Build the metering/logging
primitive (`llm_call_log`, per-request cost tracking) once, generically,
rather than bespoke per consumer.

**Every doc found a real, already-existing partial solution and extended
it rather than replacing it.** `project_enrichment_checks` already existed
(doc 01), `PRD_SIGNUP_CRM.md` already existed unbuilt (doc 02), engagement
data already exists in Postgres just not surfaced to sales (doc 03), and
the pricing page already has tier copy just no enforcement (doc 04). The
pattern across this whole package is: the data and partial infrastructure
usually already exist; the gap is almost always the connecting piece, not
a from-scratch build. Keep applying this lens to new work — check for the
partial solution before designing a new one.

## What this package deliberately does NOT decide

- The exact microservices/service-boundary split of `api/main.py` for a
  100-engineer team (flagged in the org-structure doc as a real, near-term
  decision — `api/main.py` as one file does not survive to 100 engineers —
  but not designed here; it deserves its own dedicated doc once the
  auth/role foundation in doc 02 is built, since service boundaries should
  probably split along the same lines roles do: public API / admin API /
  internal pipeline API).
- A firm SSO/enterprise-auth cost commitment (doc 02 flags this as
  unresolved rather than guessing a number).
- Whether an external CRM (HubSpot/Pipedrive) is ever needed — doc 03
  recommends deferring this decision past ~50 leads/month, not deciding
  it now.

## Immediate next steps

1. ~~Run `gcloud auth login`/`application-default login`, re-run Gemini
   review~~ — done 2026-07-30, findings folded into all four docs.
2. ~~Load the merged national corpus into production Postgres~~ — done,
   328,327 projects now live.
3. Start executing against `00-MASTER-ROADMAP.md`'s P0 list — several new
   P0 items came directly out of the Gemini review (the enrichment
   fingerprint staleness fix, the LLM cost model's missing grounding-fee
   line item, the `is_active`/JWT-revocation fix, first-party UTM capture)
   and should be treated as no less urgent than the items already in the
   original draft.
