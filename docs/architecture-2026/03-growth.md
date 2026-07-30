# 03 — Growth: Marketing, SEO, Lead Capture, Sales Prioritization

Status: Gemini-reviewed 2026-07-30 (the review that actually ran, not just labeled — see findings below). Companion to the ingestion/scoring and admin-portal
architecture docs in this same directory. Ground truth as of 2026-07-30:

**Build status 2026-07-30: P0-P3 shipped, P4's sitemap item deliberately deferred — see `00-MASTER-ROADMAP.md` for the authoritative per-item breakdown.** In brief: FAQ/Org JSON-LD, first-party UTM capture, PostHog, `ask_log`, and `lead_scores` + `GET /v1/ops/leads` (mirroring `compute-project-scores.py`'s decomposed-score pattern, live-tested against real production leads) are all live. The sitemap-index rework stays unbuilt — its own stated precondition ("once organic project-page traffic is validated") hasn't happened yet.

## Gemini Review Findings (incorporated 2026-07-30)

1. **Territory/category breadth (+10) rewards tire-kickers, not account size.** Selecting many states/categories at onboarding is more often a casual browser or researcher than a high-value account — real high-converting reps are tightly focused on 1-3 states and 1 category. **Fix applied:** reconsider this signal as *density of engagement within a declared territory* rather than raw breadth (e.g., tracked-project count relative to territory size), not simply "more states = more score." Flagged for revision in `scripts/compute-lead-scores.py` when built — not fully redesigned here, since it needs real usage data to calibrate against.
2. **Recency should decay the total score, not just add up to 10 points.** As designed, a 6-month-old abandoned demo request keeps its full 35 intent points forever, while an engaged user active yesterday is capped lower. **Fix applied:** recency becomes a multiplicative decay factor against the *total* score (same exponential-decay shape `project_scores.recency_score` already uses, 125-day half-life) rather than a small additive component.
3. **Intent scoring is binary and undervalues organic product engagement.** A highly-engaged signed-in user (tracking 40 projects, asking Gemini a dozen questions) who never clicked "Request Demo" scores lower than someone who submitted the form and never returned. **Fix applied:** add an "implicit intent" threshold — a user exceeding a usage bar (e.g. >5 tracked projects + >3 ask-endpoint calls) earns intent points comparable to an explicit demo request, since sustained product usage is itself a real buying signal.
4. **PostHog alone undercounts attribution — ad-blockers silently drop 20-35% of client-side tracking.** Relying on `posthog-js` as the sole attribution source loses exactly the tech-savvy corporate-browser users this ICP skews toward. **Fix applied:** add a small first-party (non-blockable) script capturing `utm_source`/`utm_medium`/`utm_campaign`/`referrer` to `localStorage` on first landing, passed directly in the `/v1/contact` POST body — this becomes the primary attribution source; PostHog stays for session replay/funnels, not attribution truth.
5. **Missing, higher-leverage SEO fix: programmatic directory/hub pages, not just individual project metadata.** Individual project pages rarely rank for real B2B search intent (nobody searches an exact unknown project name) — the real opportunity is aggregation pages like `/projects/texas/healthcare` matching how buyers actually search ("commercial HVAC construction projects in Texas"). This also solves the sitemap 2,000-ID cap problem by giving crawlers indexable hub pages that internally link down to the deep project pages. **Added as a new P1 item** — higher priority than the previously-listed sitemap-index fix, which this substantially supersedes.

- Marketing site: Next.js `output: "export"`, static, Firebase Hosting.
- Lead capture: one shared "Request Demo" modal (`components/marketing/DemoModal.tsx`)
  POSTing to `/v1/contact` (`api/main.py:submit_contact`), storing to
  `contact_submissions` (`db/migrations/015_contact_submissions.sql`).
- Signed-in product usage already exists and is unused for sales: `user_profiles`
  (021, extended by 026 with `full_name/phone/role_title/lead_source/lifecycle_stage/notes`),
  `user_tracked_projects` (022), `user_saved_views` (024), and two Gemini-grounded
  "ask" endpoints (`/v1/projects/{id}/ask`, `/v1/me/ask`) that are a real, already-built
  engagement signal.
- `crm_contacts` (026) is a read-only SQL view joining `user_profiles` FULL OUTER JOIN
  latest `contact_submissions` per normalized email, served read-only via
  `GET /v1/ops/crm` behind `require_admin_user`. No scoring, no sort/filter beyond
  `ORDER BY COALESCE(onboarded_at, demo_requested_at) DESC`.
- `project_scores` (013) already establishes the "transparent, weighted, decomposed"
  scoring philosophy this doc mirrors: `score = value_score(0-40) + recency_score(0-35)
  + news_score(0-25)`, each stored as its own column so a rep can see *why* a project
  ranks where it does (`scripts/compute-project-scores.py`).
- SEO: only 4 of 7 marketing pages have `generateMetadata`/`metadata` exports
  (`product`, `pricing`, `how-it-works`, `about` — confirmed via grep). Homepage
  (`app/page.tsx`) and `visibility`/`reporting` have none. Zero marketing pages carry
  JSON-LD; only `app/projects/[id]/page.tsx` does (a `Project` schema.org type, not
  even one of the marketing-relevant types). `components/marketing/FAQ.tsx` renders
  a visual accordion only — no `FAQPage` schema despite the homepage already having
  the exact Q&A content that schema type wants. `app/sitemap.ts` caps at 2,000
  featured project IDs (full corpus is ~175K rows, times out the build) and excludes
  `pricing`'s pricing detail state, but that cap is a known, documented, deliberate
  tradeoff, not a gap discovered here. `app/robots.ts` allows everything, points at
  the sitemap — nothing wrong there.

---

## 1. Requirements

1. Every marketing page must be attributable to pipeline outcome: which page a lead
   first touched, and which page they converted on, must be visible next to the lead
   in whatever the sales-facing view becomes.
2. Search engines must be able to index and correctly rich-render the pages that
   exist today, not a hypothetical future site — no dependency on unbuilt pages.
3. The CTA must scale from "one form" to "form varies by page/persona" without a
   rewrite, because the founder already anticipates persona-specific asks (manufacturer
   vs. rep-agency vs. enterprise).
4. Signed-in product usage (territory, tracked projects, saved views, Gemini-ask
   activity) must feed the same lead view inbound demo requests feed — today these
   are two disconnected signals (`contact_submissions` vs. `user_profiles`) merged
   only by email match in a read-only view.
5. Lead prioritization must be transparent and inspectable by a human (mirrors the
   `project_scores` philosophy) — not a black-box model, this early, with this little
   labeled outcome data (no won/lost history yet to train on).
6. The solution must fit a team of effectively one founder operating both product
   and sales — no infra or subscription that requires dedicated ops headcount to run.

---

## 2. Architecture Decisions

### 2a. Analytics stack: PostHog Cloud (free tier), not GA4, not self-hosted

**Decision:** Add PostHog Cloud (hosted, not self-hosted) to the marketing site and
the authenticated app, on the free tier (1M events/mo — this site is nowhere near
that volume pre-revenue).

**Why, with tradeoffs:**
- **GA4** is free and ubiquitous, but its event model is a poor fit for what's actually
  needed here: joining an anonymous pre-signup pageview to a specific `contact_submissions`
  row to a specific `user_profiles.firebase_uid` requires either GA4's BigQuery export
  (a second system, a second bill, a pipeline to build) or living inside GA4's UI,
  which cannot join against Postgres. GA4 is the right call if the only need were
  "how much organic traffic," it is the wrong call for "which page converts which
  persona into which lead score."
- **Self-hosted PostHog / self-hosted anything (Plausible, Umami, Matomo)** adds a
  server SpecIndex now has to patch, back up, and keep alive, for a team of one. Not
  justified at this traffic volume. Revisit only if event volume or cost genuinely
  outgrows the Cloud free tier — an infra decision driven by a real number, not
  speculation.
- **PostHog Cloud** wins because (1) it's a hosted SaaS, zero ops burden, (2) it has
  a Postgres-queryable path — session/event data can be pulled via its API into the
  same lead-scoring job that already reads `crm_contacts`, rather than living in a
  silo, (3) it does session replay and funnels out of the box, useful for "why isn't
  the demo modal converting on `/pricing`" without instrumenting anything custom,
  and (4) autocapture means the 7 marketing pages need only the PostHog snippet, not
  per-element instrumentation, to get page-level conversion funnels immediately.

**Concrete wiring:**
- Add `posthog-js` to `app/layout.tsx`, autocapture on, respecting DNT.
- Add UTM + referrer capture at the point of first landing (PostHog does this
  automatically via `$initial_referrer`/`$initial_utm_*` person properties) — no
  custom code needed for this part.
- Extend `ContactSubmission` (api/main.py) and `contact_submissions`
  (015 migration) with `utm_source`, `utm_medium`, `utm_campaign`, `referrer` — today
  only `source_path` (the page path, not the traffic source) is captured. This is
  the single most important schema gap: SpecIndex currently cannot tell whether a
  demo request came from organic search, a LinkedIn post, or a cold email link.
- Client sends PostHog's `distinct_id` alongside the `/v1/contact` POST body so the
  anonymous pre-signup session can be joined to the submission row, and later to the
  `firebase_uid` once PostHog's `identify()` call fires on sign-in — giving a real,
  joinable path from first pageview through signup through demo request, not just
  the current same-email heuristic in `crm_contacts`.

### 2b. SEO fixes, ranked by leverage

1. **P0 — JSON-LD `Organization` + `SoftwareApplication` on the homepage, `FAQPage`
   on the FAQ component.** This is the single highest-leverage fix. Today zero
   marketing pages carry structured data, so SpecIndex is invisible to rich-result
   surfaces (AI Overviews, People-Also-Ask, sitelinks) that a construction-intelligence
   buyer's queries increasingly resolve through. The FAQ content already exists
   verbatim in `components/marketing/FAQ.tsx` as `{q, a}` pairs — wrapping it in a
   `FAQPage`/`Question`/`Answer` JSON-LD block is a ~20-line change with no new
   content to write, using the exact pattern `app/projects/[id]/page.tsx` already
   proves out (`dangerouslySetInnerHTML` script tag) for a second schema.org type.
2. **P1 — `generateMetadata` on `app/page.tsx`, `app/visibility/page.tsx`,
   `app/reporting/page.tsx`.** Homepage having no explicit metadata export means it's
   silently inheriting the root layout's generic title/description for the single
   highest-traffic page on the site — the one page where a hand-written, keyword-
   considered description matters most.
3. **P2 — sitemap completeness via a sitemap index.** The 2,000-ID cap is a
   deliberate, documented tradeoff (build timeout at full corpus scale), not a bug,
   but it does mean ~173K project pages are permanently unreachable to crawlers. The
   documented fix already exists in the code comment: a sitemap index with numbered
   sub-sitemaps fed by a lightweight ids-only endpoint. Worth doing once organic
   project-page traffic is validated as a channel worth the build-engineering cost —
   not urgent today since the featured 2,000 are the higher-scored, higher-intent
   pages anyway.
4. **P3 — Core Web Vitals: the 1.7MB `/map/` chunk is not a marketing SEO problem.**
   `/map/` is confirmed to be the internal admin Mapbox GL page (gated by
   `require_admin_user`/token check in `api/main.py`), not a public marketing route —
   it is not in `sitemap.ts`'s `staticRoutes`, isn't linked from any marketing page,
   and Google doesn't crawl or rank pages that aren't discoverable. It costs nothing
   in marketing-site Core Web Vitals or crawl budget. No action needed here; flagging
   only so it isn't mistaken for a real SEO issue later.

### 2c. CTA architecture: keep the shared modal, add a `persona` variant prop — don't fork it

**Decision:** Do not build separate forms per page yet. Add a `persona` prop to
`useDemoModal()`/`DemoRequestModal` (defaulted from the page it's opened on, e.g.
`product` vs. `pricing` vs. `about`), which changes only the modal's copy/subhead and
adds a hidden `persona` field to the POST body — not a different field set, not a
different endpoint.

**Why:** The founder's own build-log comment in `DemoModal.tsx` already documents the
cost of the *previous* approach (five duplicated full-width form sections, one per
page) and the fix (one shared modal). Forking again into true per-persona forms
before there's evidence a persona needs materially different fields would repeat
that exact mistake. `source_path` already gives per-page attribution; the gap is
copy/context, not data capture — a `persona` string is enough to close it without a
second form to maintain. Revisit a true fork only if a specific persona (e.g.
enterprise/Team-tier) needs to capture a field the others don't (seat count, existing
CRM, etc.) — at that point add the field conditionally within the same modal, not a
new component.

### 2d. Lead → SQL path today, and the real gap

**Traced path:** `contact_submissions` row (from `/v1/contact`) — optionally carrying
a `firebase_uid` if the visitor happened to be signed in at submit time — gets
`FULL OUTER JOIN`-merged by normalized email with `user_profiles` into the
`crm_contacts` view, read-only via `GET /v1/ops/crm`, sorted only by
`COALESCE(onboarded_at, demo_requested_at) DESC`. That's it. There is no score, no
stage-transition logic beyond the manually-set `lifecycle_stage` text field, and no
signal from `user_tracked_projects`/`user_saved_views`/the ask endpoints reaches this
view at all — a signed-in user who has tracked 40 projects across three states and
asked Gemini a dozen questions ranks identically to one who signed up and did
nothing, as long as both submitted a demo request on the same day.

**The real gap:** engagement depth (tracked-project count/stage mix, saved-view
count, ask-endpoint usage, recency of activity) is fully captured in the database
already but never read by anything sales-facing. This is not a data-collection gap —
it's a scoring gap. Section 3 closes it.

---

## 3. Sales Lead Prioritization

### 3a. Signals, mirroring the `project_scores` decomposition philosophy

Same rule `project_scores` follows: every component scored separately, stored
separately, visible separately — a founder doing sales by hand must be able to see
*why* a lead ranks where it does, same as a rep needs to see why a project ranks
where it does.

| Signal | Source | Rationale |
|---|---|---|
| **Intent score (0–35)** | `contact_submissions` exists at all (demo requested) | Directly-expressed buying intent is the strongest single signal; a demo request outweighs passive usage. |
| **Pipeline depth score (0–25)** | `user_tracked_projects` count + stage mix | More tracked projects, and projects further along (`quoted`/`won` stages weighted higher than `watching`), signal a rep actively working territory through the tool, not just browsing. |
| **Engagement score (0–20)** | `/v1/projects/{id}/ask` + `/v1/me/ask` call count (needs a new lightweight `ask_log` table — these endpoints currently answer and return, nothing is persisted) | Asking Gemini questions about specific projects is a materially deeper engagement signal than a pageview; it's a proxy for "actually evaluating a deal," the same reasoning that made the ask endpoints worth building. |
| **Territory/category breadth score (0–10)** | `user_profiles.territory_states` / `categories` array length | A rep configured for 5 states and 3 categories represents a bigger potential account than one state/one category — a proxy for account size absent real firmographic data. |
| **Recency score (0–10, decaying)** | `MAX(user_tracked_projects.updated_at, ask activity, contact_submissions.created_at)` | Same exponential-decay shape as `project_scores.recency_score` (125-day half-life) — a lead that was active last week outranks one that went quiet two months ago, all else equal. |

**Formula:** `lead_score = intent + pipeline_depth + engagement + territory_breadth + recency` (0–100), each component stored in its own column on a new `lead_scores` table (mirrors `project_scores` exactly: one row per `contact_key`, recomputed by a scheduled job, not hand-edited).

```sql
-- db/migrations/0XX_lead_scores.sql (illustrative — not yet applied)
CREATE TABLE IF NOT EXISTS lead_scores (
  contact_key           TEXT PRIMARY KEY,  -- matches crm_contacts.contact_key
  score                 INTEGER NOT NULL,
  intent_score          INTEGER NOT NULL,
  pipeline_depth_score  INTEGER NOT NULL,
  engagement_score      INTEGER NOT NULL,
  territory_score       INTEGER NOT NULL,
  recency_score         INTEGER NOT NULL,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Recomputed by `scripts/compute-lead-scores.py` (same shape as
`compute-project-scores.py`: pure functions per component, one script, run on a
schedule — daily is more than sufficient at current lead volume), reading
`crm_contacts`, `user_tracked_projects`, and the new `ask_log` table.

**Why a simple weighted sum, not an ML model:** there is no won/lost outcome history
yet to train or validate a model against — SpecIndex is pre-revenue. A learned model
here would be unfalsifiable (no ground truth to check it against) and opaque (fails
requirement 5). The transparent formula is not a placeholder for "not having gotten
to ML yet" — it's the correct choice until there's a labeled dataset of actual closed
deals to fit against, at which point revisiting with real logistic regression on the
same feature set is a natural, additive next step, not a rewrite.

### 3b. CRM: Postgres + `/v1/admin/leads`, not HubSpot/Salesforce/Pipedrive — yet

**Decision:** Extend the existing read-only `/v1/ops/crm` pattern with a
`/v1/admin/leads` endpoint that joins `lead_scores` onto `crm_contacts` and supports
`ORDER BY score DESC` plus basic stage-filter query params. No external CRM.

**Why:** the same reasoning migration 026 already gave for choosing a view over a
third table — a real external CRM buys pipeline-stage automation, email sequencing,
and multi-user permission handling that a team of one founder doing manual outreach
does not yet need, and a full HubSpot/Salesforce integration is meaningful ongoing
maintenance surface for zero current benefit. Pipedrive is the cheapest credible
option if this changes, but the trigger for revisiting should be concrete: a second
person joining sales, or lead volume high enough that manually reading a sorted table
stops being tractable (rough threshold: sustained >50 new leads/month). Below that
threshold, a sorted, scored Postgres view read through the admin portal (this
endpoint slots directly into the `/ops` admin-portal work being designed in the
parallel admin-portal doc in this same architecture set — no new auth model needed,
it reuses `require_admin_user`) is strictly less operational overhead for the same
practical outcome: a founder opening a page and seeing the hottest lead at the top.

---

## 4. Phased Build Plan

**Phase 1 (SEO + attribution, ~1 day):**
- JSON-LD `Organization`/`SoftwareApplication` on homepage, `FAQPage` on `FAQ.tsx`.
- `generateMetadata` on `app/page.tsx`, `app/visibility/page.tsx`, `app/reporting/page.tsx`.
- UTM/referrer columns on `contact_submissions`; PostHog Cloud snippet added site-wide.

**Phase 2 (CTA + engagement logging, ~1–2 days):**
- `persona` prop on `DemoModal`; PostHog `distinct_id` threaded into `/v1/contact`.
- New `ask_log` table + insert-on-call in both ask endpoints (currently unlogged).

**Phase 3 (scoring + admin surfacing, ~2–3 days):**
- `lead_scores` table + `scripts/compute-lead-scores.py`, scheduled daily.
- `/v1/admin/leads` endpoint (score-sorted `crm_contacts` + `lead_scores` join).
- Wire into the admin portal's `/ops` surface (parallel doc) as a sortable table.

**Phase 4 (revisit trigger, not scheduled):**
- Re-evaluate external CRM only at >50 new leads/month sustained, or a second sales
  seat. Re-evaluate ML-based scoring only once real won/lost outcomes exist to
  validate against.

---

## 5. Action Items

- ✅ SHIPPED 2026-07-30: Add `FAQPage` JSON-LD to `components/marketing/FAQ.tsx` and `Organization`/`SoftwareApplication` JSON-LD to `app/page.tsx`.
- ✅ SHIPPED 2026-07-30 as migration 030: Add `utm_source`/`utm_medium`/`utm_campaign`/`referrer` columns to `contact_submissions` and the `ContactSubmission` model.
- ✅ SHIPPED 2026-07-30 (`lib/attribution.ts`): Add a first-party (non-blockable) `localStorage` UTM/referrer capture script as the primary attribution source — don't rely on PostHog alone (Gemini: ad-blockers drop 20-35% of client-side tracking).
- P1: Add `generateMetadata` to `app/page.tsx`, `app/visibility/page.tsx`, `app/reporting/page.tsx`.
- P1: Add PostHog Cloud snippet to `app/layout.tsx` and thread `distinct_id` into the `/v1/contact` POST body (session replay/funnels, not primary attribution).
- P1: Build programmatic directory/hub pages (`/projects/[state]/[category]`) — Gemini-flagged as the single highest-leverage SEO fix, supersedes the sitemap-index-only approach.
- P2: Add `persona` prop to `DemoModal`/`useDemoModal()`, defaulted per page.
- P2: Add an `ask_log` table and insert rows from `/v1/projects/{id}/ask` and `/v1/me/ask`.
- P3: Create `lead_scores` migration + `scripts/compute-lead-scores.py` mirroring `compute-project-scores.py`'s decomposed-score pattern.
- P3: Add `/v1/admin/leads` endpoint joining `lead_scores` onto `crm_contacts`, sortable by score.
- P4: Build a sitemap index with numbered sub-sitemaps once organic project-page traffic is validated as a channel.
- P5: Revisit external CRM (Pipedrive) only past ~50 new leads/month sustained or a second sales hire.
