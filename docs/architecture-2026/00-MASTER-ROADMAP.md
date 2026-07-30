# SpecIndex — Master Roadmap (2026-07-30)

Consolidated from the five docs in this package. Each line traces back to
one doc's detailed reasoning — read that doc before implementing, this is
a priority-ordered index, not the spec itself. P0 = build before anything
else in this package; P5 = someday/evaluate-later.

**Update 2026-07-30, later same day:** `gcloud` re-authenticated. All four
architecture docs have now had their real Gemini/Vertex critical review,
with substantive findings folded into each doc and reflected in the P-tags
below. The 327,561-project merged corpus has been loaded into production
Postgres (up from 205,161 — real, live now). Both items that were P0
"blocked on gcloud" are done and removed from the list below; new P0/P1/P2
items surfaced BY the review are added in their place.

**One correction applied here that isn't in the source docs yet:** doc 04's
"P3: Wire Clerk Organizations" is superseded by doc 02's `org_id` column
approach, since the repo has since migrated off Clerk to Firebase Auth.
Listed below under its corrected form.

---

## P0 — Build before anything else in this package

- Add `026_user_staff_roles.sql` (staff-only) + `subscription_tier`/`is_active` columns on `user_profiles` — revised per Gemini review, two structures not one mixed table — *identity*
- Build `require_role()` FastAPI dependency factory; re-point `/v1/ops/crm` at it instead of `require_admin_user` — *identity*
- Backfill current `ADMIN_EMAILS` allowlist into `user_staff_roles` as `super_admin` rows — *identity*
- Check `is_active` inside `require_firebase_user` itself, not just `require_role` — closes the ~1hr JWT-revocation gap Gemini flagged — *identity*
- Add `source_fingerprint`, `enrichment_version`, `status`, `last_enriched_at` columns to `project_enrichment_checks` (migration 027), with a 180-day max-staleness fallback so a fingerprint that never changes doesn't freeze a project out of re-enrichment forever (Gemini: "grounding paradox") — *data platform*
- Compute/store `source_fingerprint` in `enrich-project-details.py`; gate re-enrichment on fingerprint/version change, not just the 30-day timer — *data platform*
- Create `llm_call_log` table with a `grounding_requests_count` column priced separately from tokens (Gemini: Vertex Search Grounding is a fixed per-search fee that can dwarf token cost 10-50x, not captured by a token-only cost model); instrument `enrich-project-details.py` (both passes) and `model_a_flash.py`/`model_b_sonnet.py` to write a row per call — *data platform*
- Add `FAQPage` JSON-LD to `components/marketing/FAQ.tsx` and `Organization`/`SoftwareApplication` JSON-LD to `app/page.tsx` — *growth*
- Add `utm_source`/`utm_medium`/`utm_campaign`/`referrer` columns to `contact_submissions` and the `ContactSubmission` model — *growth*
- Add a first-party (non-blockable) `localStorage` UTM/referrer capture script as the PRIMARY attribution source, not PostHog alone (Gemini: ad-blockers silently drop 20-35% of client-side tracking for this ICP) — *growth*
- Ship API-key auth (`require_api_key` dependency + `api_keys` table) as the shared prerequisite for MCP access and Enterprise billing — *productization*

## P1 — Next, once P0 is done

- Add `v_llm_daily_spend`, `v_enrichment_coverage`, `v_pipeline_health` Postgres views — *data platform*
- Add a Tier-1 cheap-model triage call in `enrich-project-details.py` before Pass 1 — *data platform*
- Gate Pass 2 (cross-check) behind a `project_scores` value/priority threshold instead of running it unconditionally — *data platform*
- Create `manufacturers`, `general_contractors`, `people` tables + join tables; Phase-1 heuristic normalization batch over existing `mentioned_brands`/`competitor_watch`/`owner`/`architect`/`general_contractor` fields — *data platform*
- Execute `docs/PRD_SIGNUP_CRM.md` Phase 1 migration (full_name, phone, lifecycle_stage, etc. on `user_profiles`) — *identity*
- Build admin portal customer-list page, gated on `support_admin`/`super_admin` — *identity*
- Build read-only "view as customer" admin query path (never mint a real customer session) — *identity*
- Keep `/coverage`, `/ops`, `/map` on their current unauthenticated-but-noindex pattern; link them into the admin shell nav rather than rebuilding — *identity*
- Add `generateMetadata` to `app/page.tsx`, `app/visibility/page.tsx`, `app/reporting/page.tsx` — *growth*
- Add PostHog Cloud snippet to `app/layout.tsx`; thread `distinct_id` into the `/v1/contact` POST body — *growth*
- Enforce the Free-tier 1-brand-check/week limit and Pro seat/usage limits already promised on the pricing page but not implemented — *productization*
- A Cloud SQL read replica for agent/analytics query traffic, isolated from the production API — *data platform* (do this before an agent gets standing query access in a workflow that matters, not before)

## P2 — After P1

- Add a hard daily/monthly LLM budget cap with a circuit breaker in `enrich-project-details.py` and any automated discovery-chat runner — *data platform*
- Stand up the read replica (if not already done in P1); create an `agent_readonly` Postgres role scoped to `v_*` views only — *data platform*
- Add query-result caching (hash of normalized query text, TTL) for `gemini_discovery_chat.py` — *data platform*
- Enforce Free-tier "1 brand check/week" quota server-side with a usage-counter table — *identity* (note: overlaps productization's P1 above — one implementation, not two)
- Add nullable `org_id` column to `user_profiles` as the forward seam for Team-tier seats — *identity*
- Add account/settings page to the user portal for post-onboarding profile edits — *identity*
- Add a `persona` prop to `DemoModal`/`useDemoModal()`, defaulted per page — *growth*
- Add an `ask_log` table; insert rows from `/v1/projects/{id}/ask` and `/v1/me/ask` — *growth* (this is also a P0-adjacent dependency for productization's MCP usage metering — build once)
- Ship the MCP server as a thin wrapper over `/v1/projects`, `/v1/projects/{id}`, `/v1/projects/{id}/ask`, `/v1/me/ask`, `/v1/coverage`, `/v1/quality` — *productization*

## P3 — Real, but not urgent

- Enable `pg_trgm`; build the fuzzy-matching merge-proposal batch job for entity directories — *data platform*
- Batch multiple projects per Gemini enrichment call instead of one-per-call — *data platform*
- Add Stripe customer id to `user_profiles`; build billing page — *identity*
- Design short-lived `createCustomToken`-based true impersonation only if the read-only admin view proves insufficient — *identity*
- Create `lead_scores` migration + `scripts/compute-lead-scores.py`, mirroring `compute-project-scores.py`'s decomposed-score pattern — *growth*
- Add `/v1/admin/leads` endpoint joining `lead_scores` onto `crm_contacts`, sortable by score — *growth*
- Add `org_id`-based Team-tier multi-seat invite-and-roster flow (**corrected**: not Clerk Organizations — the repo is on Firebase Auth now, use the `org_id` seam from identity P2) — *productization*

## P4 — Later

- LLM-assisted entity resolution pass for the fuzzy-matching residual (manufacturers/GCs/people) — *data platform*
- Team-tier org/seat invite-and-roster flow using the `org_id` seam (identity-side implementation of productization's P3 above — one build) — *identity*
- Call `revokeRefreshTokens(uid)` from an admin "deactivate user" action — *identity*
- Build a sitemap index with numbered sub-sitemaps once organic project-page traffic is validated as a real channel — *growth*
- Train a narrow Vertex AI supervised-tuned classifier (spec-window or priority-score-explain) on `project_scores` + enrichment data as the actual "custom model" sold to Enterprise — *productization*

## P5 — Someday / evaluate later, don't build speculatively

- Evaluate a dbt-style semantic layer if/when multiple teams or data marts exist — *data platform*
- Get a real Identity Platform SSO cost quote before promising enterprise SSO to any prospect — *identity*
- Replace `SPECINDEX_BUILD_TOKEN` static shared secret with short-lived GCP service-account identity tokens once a second internal service needs to call `api/main.py` — *identity*
- Revisit an external CRM (Pipedrive/HubSpot) only past ~50 new leads/month sustained, or a second sales hire — *growth*
- Add Stripe usage-based metering for Enterprise query-volume pricing once MCP/API traffic actually exists to bill against — *productization*

---

## Org-structure sequencing (from doc 05, not a P-tag list — hiring order)

1. Platform & Core API + Data Platform engineering teams first — they own the P0/P1 backlog above, which is already real and large.
2. Growth hiring should trail the lead-scoring/CRM work actually shipping (P2/P3 above), not precede it.
3. Customer Success shouldn't exist before there's a paid Team/Enterprise customer to retain (P3/P4 pricing work above).

See `05-org-structure.md` for team sizes and full reasoning.
