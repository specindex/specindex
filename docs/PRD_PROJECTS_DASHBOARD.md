# PRD: Projects Dashboard — From Database Browser to Sales Intelligence

**Author:** Asif Hussain (product), captured with Claude
**Date:** 2026-07-26
**Status:** Phase A shipped; Phase B and several deferred items open

## 1. Problem

`/projects/` — the core product surface — was a filterable list over the
full corpus (20,000+ projects and growing). Multiple independent UX
reviews converged on the same critique, in slightly different words:

- **Kimi-sourced redesign doc** (earlier this session): mockup for a
  territory + priority-score-ranked dashboard, "load 50 at a time," map
  view toggle, division filter.
- **Perplexity general feedback doc** (2026-07-26): "the site is a
  discovery layer, not a workflow tool"; a rep needs "here are your 8 new
  early-stage projects in your territory this week," not a search box.
- **Perplexity `/projects/` page audit** (2026-07-26): granular bug/UX
  list, largely written against a pre-rewrite build (see Section 4 for
  what was already stale vs. still real).
- **Your own framing**, most directly: *"Don't show all 25,000+ projects.
  Show the 50 best projects for this specific manufacturer, ranked by a
  transparent score, filtered by their territory and product category...
  Database browser: 'Here are 7,963 projects. Good luck.' Sales
  intelligence: 'Here are the 12 projects in your territory that need
  your product this week, ranked by how likely they are to buy.'"*

That's the product gap this PRD addresses: the site had the right data
and the right score, but presented it as a browse-everything database
instead of a personalized, ranked shortlist.

## 2. Goals

1. Default landing on `/projects/` reads as "your top 50," not "here are
   25,000+ rows."
2. Ranking (priority score: value + recency + news, already live and
   transparent) and relevance (territory + product category) are both
   first-class, not buried filters.
3. Surface "what's new" so a rep has a reason to come back weekly, without
   requiring an account to get initial value.
4. Do this without reopening the static-export architecture decision that
   was explicitly deferred until 100,000 projects.

## 3. Non-goals (explicitly out of scope for this PRD)

- **CSI Division / product-category filtering by MasterFormat code.**
  Verified this session: `project_csi_divisions` and `csi_division_codes`
  are 100% empty in the database. Any "Division 23 (HVAC)" style filter
  in the feedback docs is describing a feature that has no underlying
  data yet — this is a data-sourcing problem, not a UI problem, and is
  tracked separately (`docs/ROADMAP.md` item 13/41).
- **User accounts, saved searches, weekly digest email.** Real, valuable,
  and the single most-requested "killer feature" across every feedback
  doc — but the app has zero existing auth infrastructure today. Treated
  as Phase B (Section 5), not bundled into the initial reframe.
- **Static→SSR/Cloud Run migration.** You deferred this explicitly
  ("come back after 100,000 projects, focus on coverage now"). This PRD's
  Phase A is deliberately designed to work entirely within the current
  static-export + client-fetched-dashboard architecture.
- **Pricing page rebuild.** Explicit decision 2026-07-26: keep it static
  for now; revisit once ready to commit to real numbers (`docs/ROADMAP.md`
  item 45).

## 4. What was already fixed vs. genuinely new

The Perplexity `/projects/` page audit is dated 2026-07-26 but reads
against an earlier build. Before treating any of its findings as
open work, they were checked against the live site:

| Audit claim | Status |
|---|---|
| Search box doesn't filter, counter stuck at "20084 of 20084" | **Stale.** Server-side search/filter/pagination shipped earlier this session; verified live (e.g. "hospital" correctly returns a filtered subset) |
| All 20,084 projects render at once, no pagination | **Stale.** Paginated at 50/page since the same rewrite |
| County dropdown not scoped to selected state | **Still real** — tracked in item 48 |
| Filters don't update the URL (unshareable/unbookmarkable) | **Still real** — tracked in item 48 |
| Inconsistent money formatting, raw permit-string titles, truncated dropdown labels | **Still real**, lower-severity — tracked in item 48 |

This matters beyond this one doc: **every piece of secondhand UX
feedback in this project has been verified against the live system
before being acted on**, not accepted at face value (the Kimi doc's
"22MB page" and "CSI division filter" claims were similarly corrected
earlier this session). Feedback quality varies; the live system is the
source of truth.

## 5. Requirements

### Phase A — Ship without accounts (shipped 2026-07-26)

| # | Requirement | Notes |
|---|---|---|
| A1 | Default view leads with "Top 50 in your territory," not a raw total | Score-sorted (already the default), page-1 framing changes copy from "N,NNN projects match" to "Top 50 ... — N,NNN total match, refine to search all" |
| A2 | Territory + product category persist across visits, no login required | `localStorage`, not server-side — a placeholder for real saved profiles until Phase B |
| A3 | First-visit nudge toward setting territory/category | Dismissible banner, not a blocking modal — avoids friction for a skeptical evaluator (per the "no self-serve evaluation path" feedback) |
| A4 | "🔔 N new this week" visible and actionable | Required fixing a real bug first: `first_seen_at` had no column default and was NULL on every project loaded since a two-days-prior schema migration — see `db/migrations/014_first_seen_default.sql` |
| A5 | Map view toggle on `/projects` itself, not just the internal `/map/` | New public `/v1/projects/map-points` endpoint, bounded to the visitor's active filters (not the full corpus); Leaflet+OSM per the existing customer-facing-map decision (Mapbox GL stays admin-only) |

### Phase B — Requires accounts (not started)

| # | Requirement | Notes |
|---|---|---|
| B1 | Firebase Auth (email/password or magic link) | Lowest-new-infra option given the app is already on Firebase Hosting |
| B2 | Server-persisted saved territory + saved searches | New Postgres table(s) + authenticated API routes |
| B3 | Weekly digest email: "N new projects in your territory" | Reuses existing Gmail SMTP credentials already used elsewhere in the pipeline; cron via GitHub Actions scheduled workflow, matching the existing `pull-national.yml` pattern |
| B4 | Personalized default landing | Do this **client-side** (fetch using the logged-in user's saved territory on load), not via SSR — avoids reopening the deferred static-export migration |

### Deferred (logged, not built)

- Demo-request friction (mailto link, no self-serve evaluation path,
  buried demo form, no real pricing numbers, weak testimonials) —
  `docs/ROADMAP.md` item 47
- Detailed `/projects/` UX polish (URL state, clear-filters button, money
  formatting, title cleanup) — item 48
- SEO/analytics/growth infrastructure (sitemap index split, GA4/GTM,
  pSEO hub pages, dynamic OG images, JSON-LD, connection pooling) — item
  49. Most of this is compatible with the current static-export
  architecture and doesn't require Phase B or the SSR migration; only
  on-demand ISR revalidation does, and is explicitly gated on that
  deferred decision.

## 6. Success signals

No formal analytics are wired up yet (see item 49 — GA4 is part of the
deferred SEO/analytics rollout). Once in place, the signals that would
validate this PRD:

- Return-visit rate to `/projects/` (does persisted territory/category
  bring reps back, vs. one-time visits)
- Click-through rate from the "new this week" badge
- Map-toggle usage as a fraction of sessions
- Demo requests originating from `/projects/` vs. other pages, once
  item 47's self-serve-evaluation and demo-form-placement fixes ship

## 7. Open questions

- Phase B sequencing: build accounts now, or continue prioritizing
  coverage (the standing goal) and revisit at a natural checkpoint?
- Should the "new this week" window (currently hardcoded to 7 days) be
  user-configurable once accounts exist?
- Advertising as a second monetization layer (raised 2026-07-26):
  recommendation is to hold off — subscription/workflow value is worth
  more per user at this audience size, and optimizing for pageviews would
  pull against the "12 projects, ranked, this week" product thesis. Worth
  revisiting once there's real traffic and multiple competing
  manufacturers per category.
