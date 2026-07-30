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

**Update 2026-07-30, end of day: all P0 items shipped and live.** Actual
migration numbers ended up 027-031 (026 was already taken by
`crm_contacts.sql` from concurrent work). All 5 migrations applied
directly to production Postgres, backend redeployed and verified live
(caught and fixed one real deploy bug along the way — two new endpoints
were defined before `app = FastAPI(...)` existed, which crashed the
container on boot; fixed by moving them after, verified with a local
import before redeploying). Frontend build passes clean.

Manual verification: both items closed 2026-07-30. ✅ `/ops/crm`
confirmed rendering correctly under the new `require_role` gate with a
real signed-in admin session. ✅ UTM-tagged demo submission confirmed
end to end — `contact_submissions.id=7` (16:39:41 UTC) shows
`utm_source='test'`, `utm_medium='manual_check'`,
`utm_campaign='verification'` captured exactly from the URL, vs. NULL on
every row before this feature shipped. **All P0 work is now fully
verified, not just deployed.**

**Update 2026-07-30, later same day: P1 and P2 shipped and merged** (PR
#81), then **P3 and most of P4 built** on top on branch
`master-roadmap-p3-p4-items` — see those sections below for the full
per-item breakdown, including two items deliberately skipped (Stripe
billing integration, true impersonation), one deferred on a real
unmet precondition found live (LLM entity resolution, blocked on
`normalize-entity-directories.py`'s in-flight run), and P5 left
untouched per its own "don't build speculatively" instruction.

---

## P0 — Build before anything else in this package — ✅ ALL SHIPPED 2026-07-30

- ✅ `027_user_staff_roles.sql` (staff-only) + `subscription_tier`/`is_active` columns on `user_profiles` — revised per Gemini review, two structures not one mixed table — *identity*
- ✅ `require_role()` FastAPI dependency factory; `/v1/ops/crm` re-pointed at it instead of `require_admin_user` — *identity*
- ✅ Backfilled `ADMIN_EMAILS` allowlist into `user_staff_roles` as `super_admin` rows (live) — *identity*
- ✅ `is_active` checked inside `require_firebase_user` itself, not just `require_role` — closes the ~1hr JWT-revocation gap Gemini flagged — *identity*
- ✅ `source_fingerprint`, `enrichment_version`, `status`, `last_enriched_at` columns on `project_enrichment_checks` (migration 028), with a 180-day max-staleness fallback so a fingerprint that never changes doesn't freeze a project out of re-enrichment forever (Gemini: "grounding paradox") — *data platform*
- ✅ `source_fingerprint` computed/stored in `enrich-project-details.py`; re-enrichment gated on fingerprint/version change, not just a timer — *data platform*
- ✅ `llm_call_log` table (migration 029) with a `grounding_requests_count` column priced separately from tokens (Gemini: Vertex Search Grounding is a fixed per-search fee that can dwarf token cost 10-50x); `enrich-project-details.py` (both passes) instrumented to write a row per call — *data platform*
- ✅ `FAQPage` JSON-LD on `components/marketing/FAQ.tsx` and `Organization`/`SoftwareApplication` JSON-LD on `app/page.tsx` — *growth*
- ✅ `utm_source`/`utm_medium`/`utm_campaign`/`referrer` columns on `contact_submissions` (migration 030) and the `ContactSubmission` model — *growth*
- ✅ First-party (non-blockable) `localStorage` UTM/referrer capture (`lib/attribution.ts`) as the PRIMARY attribution source, not PostHog alone (Gemini: ad-blockers silently drop 20-35% of client-side tracking for this ICP) — *growth*
- ✅ API-key auth shipped (migration 031, `require_api_key` dependency + `/v1/me/api-keys` CRUD) as the shared prerequisite for MCP access and Enterprise billing — not yet wired into any consuming endpoint (MCP itself is still P2) — *productization*

## P1 — ✅ MOSTLY SHIPPED 2026-07-30 (2 items blocked on real decisions, not code)

- ✅ Added `v_llm_daily_spend`, `v_enrichment_coverage`, `v_pipeline_health` Postgres views (migration 032) — *data platform*
- ✅ Added a Tier-1 cheap-model triage call in `enrich-project-details.py` before Pass 1 (ungrounded, fails open to a full pass on error) — *data platform*
- ✅ Gated Pass 2 (cross-check) behind `project_scores.score >= 50` instead of running it unconditionally — *data platform*
- ✅ Created `manufacturers`, `general_contractors`, `people` tables + join tables (migration 033); `scripts/normalize-entity-directories.py` Phase-1 heuristic batch. **Deviation from the original plan, verified against live data first**: dropped `competitor_watch` as a manufacturer source entirely — every value in it is CSI-division category taxonomy ("elevators", "ff&e"), never a company name, confirmed by a real 500-project test run before scaling up. Also fixed a quote-stripping bug in `general_contractor` display names found the same way — *data platform*
- ✅ `docs/PRD_SIGNUP_CRM.md` Phase 1 migration — **already shipped 2026-07-30 as migration 026 (PR #73), before this pass started.** This bullet was stale; verified against the live schema before doing anything — *identity*
- ✅ Admin portal customer-list page — **already satisfied by `/ops/crm`** (migration 026/PR #73), gated on `support_admin`/`super_admin` via `require_role`, verified live (PR #79). This bullet was also stale — *identity*
- ✅ Built read-only "view as customer" admin query path: `GET /v1/ops/customer/{firebase_uid}` (never mints a session, `support_admin`+ gated) + `app/ops/customer/page.tsx`, linked from each real signed-in row in the CRM table — *identity*
- ✅ `/coverage`, `/ops`, `/map` kept on their unauthenticated-but-noindex pattern, consolidated into one nav via a new `app/ops/layout.tsx` admin shell — *identity*
- ✅ Added `metadata` to `app/page.tsx` (was missing). **`app/visibility/page.tsx` and `app/reporting/page.tsx` already had it** — this bullet was stale on 2 of its 3 targets, verified before building — *growth*
- ✅ Added `posthog-js` + a graceful-degrade `PostHogProvider` (`app/layout.tsx`); threaded `posthog_distinct_id` into `/v1/contact`'s POST body and `contact_submissions` (migration 034) — *growth*
- ✅ Enforced the Free-tier 1-brand-check/week limit: `POST /v1/me/brand-check` (migration 035, atomic increment, fails toward free/limited for an unrecognized tier), called from `VisibilityPanel.tsx` before every data pull, 429 shows an upgrade prompt instead of fetching — *productization*
- ⛔ **Pro seat/usage limits — nothing to enforce yet, not skipped.** "Seat" isn't a real concept in the schema at all today (confirmed against `user_profiles` and this doc's own P3: `org_id` doesn't exist until the identity doc's P3, the seat/roster flow is P4). Enforcing seat limits requires that model to exist first — this half of the original bullet was premature, not deferred — *productization*
- ⛔ **A Cloud SQL read replica — blocked on a real infra decision, not code.** Standing one up is a real, billed, standing piece of infrastructure (a second Cloud SQL instance) — not something to provision unprompted the way an idempotent migration is. Needs Asif's go-ahead on the added monthly cost before building — *data platform*

## P2 — ✅ MOSTLY SHIPPED 2026-07-30 (2 items blocked, not skipped)

- ✅ Added a hard daily/monthly LLM budget cap circuit breaker (`scripts/llm_budget.py`, `LLM_DAILY_BUDGET_USD`/`LLM_MONTHLY_BUDGET_USD` env vars, default $50/day, $1,000/month) — checked BEFORE each call, not after; wired into `enrich-project-details.py`'s batch loop (stops the whole batch, not just the current project) and single-project path. `gemini_discovery_chat.py` deliberately NOT wired to it — that script has no DB connection at all today and is explicitly documented elsewhere in this repo as "a manual tool, not a pipeline stage," run by a person watching output live; giving it DB access just for a budget check would be new surface area for a real interactive tool, not the automated/unattended risk this item is actually about — *data platform*
- ⛔ **Read replica — still blocked on the same real infra/billing decision flagged in P1.** Nothing changed since then; re-flagging rather than silently dropping — *data platform*
- ✅ Added query-result caching to `gemini_discovery_chat.py` (`data/gemini_query_cache/`, SHA-256 of `session:normalized_message`, 7-day TTL via `GEMINI_QUERY_CACHE_TTL_DAYS`). Deliberately narrower than caching a full exchange: keyed on message text only, not full conversation history, so it catches the real common case (an identical message re-sent after a crash/retry) without pretending an identical string means the same thing at two different points in one conversation — *data platform*
- ✅ Free-tier brand-check quota — **already shipped in P1** (productization's bullet), this P2 line was the identity-side duplicate the doc itself flagged as an overlap — *identity*
- ✅ Added nullable `user_profiles.org_id` (migration 036) — *identity*
- ✅ Built `/account` — `components/AccountSettings.tsx`, reuses the existing `POST /v1/me/profile` upsert (no new write path), linked from the signed-in home's nav — *identity*
- ✅ Added a `persona` prop to `DemoModal`/`useDemoModal()` (`DemoPersona` type: `product`/`pricing`/`about`/`general`, defaulted from the page it's opened on) — changes only copy/subhead, rides along as a hidden `persona` field on the same `/v1/contact` POST (migration 037), no new endpoint or field set, exactly per the doc's explicit "don't fork the modal" call — *growth*
- ✅ Added `ask_log` table (migration 036) + wired into both `/v1/projects/{id}/ask` and `/v1/me/ask` (best-effort insert, never fails the actual answer) — *growth*
- ⛔ **MCP server — attempted, blocked on tooling, not built blind.** The `mcp` Python SDK requires Python 3.10+; this environment only had 3.9 available to verify against, so `FastMCP`'s actual API surface and an SSE handshake against a real client couldn't be tested. Shipping unverified code for a new deployed service (its own Cloud Run instance, a protocol this session couldn't exercise end-to-end) would be the same mistake as guessing at the read-replica's cost — needs a Python 3.10+ dev environment to build against for real, not a confident-sounding untested file — *productization*

## P3 — ✅ MOSTLY SHIPPED 2026-07-30 (2 items deliberately skipped, 1 blocked on live data)

- ✅ Enabled `pg_trgm` (migration 039); built `scripts/find-entity-duplicates.py`, the fuzzy-matching merge-proposal batch job for entity directories (`--apply` actually merges via `entity_aliases`, proposal-only by default). **Fixed a real psycopg2 bug along the way**: pg_trgm's literal `%` similarity operator collided with psycopg2's own `%s` parameter syntax (`IndexError: tuple index out of range`), fixed by escaping to `%%`. **Also found and partially fixed a real data-durability bug this surfaced**: `normalize-entity-directories.py`'s 328K-row batch only committed once at the very end, so entity tables were still empty at 43% progress with nothing queryable — added a commit every 5,000 rows for future runs; the run in flight when this was found kept its original (less safe) behavior rather than being killed and losing progress — *data platform*
- ✅ Added opt-in `--projects-per-call` batching to `enrich-project-details.py` (default 1, unchanged): `run_discovery_batch()` sends N projects in one grounded Gemini call; Tier-1 triage and Pass-2 cross-check deliberately stay per-project even in batch mode. Syntax-verified, **not live-tested against a real Gemini call** — flagging honestly rather than claiming more than was verified — *data platform*
- ⛔ **Stripe customer id + billing page — schema seam only, no integration.** Added `user_profiles.stripe_customer_id` (nullable, migration 038) so a future integration has somewhere to write to; did not build actual Stripe API calls or a billing UI — that's a real payment-processing integration decision, not something to build unprompted — *identity*
- ⛔ **True `createCustomToken` impersonation — condition not met.** The read-only admin view (P1) hasn't been reported as insufficient by anyone yet — *identity*
- ✅ Created `lead_scores` table (migration 038) + `scripts/compute-lead-scores.py`, mirroring `compute-project-scores.py`'s decomposed-score pattern (intent/pipeline-depth/engagement/territory/recency, each stored separately). **Live-tested against real production `crm_contacts`/`user_tracked_projects`/`ask_log` data — wrote 5 real lead scores successfully** — *growth*
- ✅ Added `GET /v1/ops/leads`, joining `lead_scores` onto `crm_contacts`, `ORDER BY score DESC`, same `require_role("support_admin", "super_admin")` gate as `/v1/ops/crm` — *growth*
- ✅ Added `org_id`-based Team-tier multi-seat invite-and-roster flow: `org_members` table (migration 039), `GET/POST /v1/org/members`, `/invite`, `/accept`, `DELETE /v1/org/members/{id}`, and `components/TeamRoster.tsx` mounted on `/account` for `subscription_tier === "team"`. **Simplification not in the original spec, applied deliberately**: no separate `orgs` table exists yet, so `org_id` is just the owner's own `firebase_uid` — avoids inventing a second identity concept for a single-tier feature; revisit only if orgs need to outlive their original owner — *productization*

## P4 — ✅ 2 of 5 shipped, 3 explicitly deferred (unmet preconditions)

- ⛔ **LLM-assisted entity resolution pass — blocked on the P3 fuzzy-match batch's own data not being ready yet**, not skipped. `normalize-entity-directories.py`'s original run (started earlier, running with its pre-fix code) was still uncommitted and in flight when this pass was done — the entity tables it populates aren't durably queryable yet, so there's no real fuzzy-match residual to resolve against. Build once that run completes and `find-entity-duplicates.py` has been run against real data — *data platform*
- ✅ **Superseded/folded into P3 above** — the org/seat invite-and-roster flow was built as one unit with productization's P3 bullet, per that bullet's own "one build" note — *identity*
- ✅ Wired `revokeRefreshTokens(uid)` into a real admin "deactivate user" action: `POST /v1/ops/customer/{uid}/deactivate` (and `/reactivate`) set `user_profiles.is_active` AND revoke the user's Firebase refresh tokens via `firebase_admin.auth` (added `firebase-admin==6.6.0` to `api/requirements.txt`, lazily initialized via Application Default Credentials — no new credential provisioned). Surfaced as a Deactivate/Reactivate button on `components/CustomerDetail.tsx`. `is_active` was already enforced on every request via `require_firebase_user`; this closes the remaining gap where a still-valid Firebase session could otherwise be silently refreshed — *identity*
- ⛔ **Sitemap index with numbered sub-sitemaps — condition not met.** Organic project-page traffic hasn't been validated as a real channel yet — *growth*
- ⛔ **Vertex AI supervised-tuned classifier — no labeled ground-truth pipeline exists.** Same reasoning `compute-project-scores.py`/`compute-lead-scores.py` already give for using transparent decomposed formulas instead of ML: there's no won/lost outcome history to train or validate a classifier against yet — *productization*

## P5 — Someday / evaluate later, don't build speculatively — ⛔ not attempted, per this doc's own instruction

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
