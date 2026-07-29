# Project detail page template

**Status: ADOPTED (2026-07-29).** This is the standard template for every
project detail page (`/projects/[id]/`), implemented in
`components/ProjectDetailView.tsx`. It replaces the draft plan this file
used to contain — see "History" at the bottom for that draft, kept for
context on what changed and why.

Piloted end-to-end on one real project, `SPX-000157` (Hyundai-SK Battery
Plant, `ga-hyundai-sk-battery-bartow`), the only project with a full
enrichment pass as of this writing. **Next step, not yet started:** run
`scripts/enrich-project-details.py --batch` across the rest of the
corpus so every project gets this same treatment — see "Rollout" below.

## Why this shape

Modeled on Clay/Attio/Linear-style dense B2B SaaS rather than a
marketing/blog layout — validated over several rounds of an independent
Gemini design review against the live page, not just built once and
shipped. Each round caught something concrete (see "Review process"
below); the structure below is what survived that process, not a first
draft.

## Page structure, top to bottom

1. **Sticky title + score bar** — project name (truncated) and a
   tier-colored score chip (green/amber/gray dot + `NN/100`), stays
   visible while scrolling. Uses the same `scoreTier()` color logic as
   the hero score box below — these two must never disagree on what
   color a given score means (an actual bug caught and fixed once).

2. **AI grounding pipeline bar** — shown only when the project has any
   enrichment data. Three honestly-labeled steps describing what
   `scripts/enrich-project-details.py` actually does: *Search-grounded
   discovery → Cross-verified (2nd pass) → Links live-checked*. Never
   names the underlying model (Gemini) in user-facing copy — flagged in
   review as "AI theater" that exposes the vendor instead of reading as
   a SpecIndex-owned process. Right-aligned: **"Page updated {date}"**,
   from `project_enrichment_checks.checked_at` — a real timestamp of
   when the pipeline last ran against this project, not a fabricated
   freshness claim.

3. **Hero card** — bordered card, not a full-bleed band:
   - Status pill + type, then the project name (`text-2xl`/`text-3xl`,
     not the site's marketing-page `text-hero` — this page uses a
     deliberately denser type scale throughout, `text-xs`/`text-sm` for
     most body and table content).
   - `spx_id`, plus **"Source data pulled {date}"** from
     `project.first_seen_at` — when SpecIndex's corpus last pulled this
     record from its original public source. This is a *different*
     timestamp from "Page updated" above; don't conflate them.
   - City/county/state.
   - Score box (right-aligned on desktop): total score, tier label,
     click-to-reveal breakdown popover (Value/Recency/News components).
   - **KPI grid**, inside the same card, below a divider: Project ID,
     estimated value, square footage, opened/announced date, owner, GC,
     architect, mentioned brands — `grid-cols-2` → `md:grid-cols-3` →
     `lg:grid-cols-6`. Each cell is its own bordered box (not a bare
     `dt`/`dd` pair — cells without borders let labels blend into
     neighboring columns, caught in review). Empty values ("Not
     reported") render muted/de-emphasized rather than with the same
     visual weight as real data.
   - GC/Architect fall back to the matching `enrichment.team` fact (with
     its confidence badge shown) when the base corpus row has them
     blank — a real bug: the base row and the enrichment pass can
     disagree on whether a field is known, and showing "Not reported"
     directly above a "Confirmed" answer for the same field further
     down the page destroys credibility.

4. **Two-column body, `lg:grid-cols-12` at a 7/5 split** (not an
   8/4-ish content+sidebar split — the ratio matters, caught in review
   as columns visibly ending at different heights before this fix):

   **Left (7 cols) — narrative:**
   - "Project overview" (raw `description`/`key_specs`) — **only
     rendered when there's no `executive_brief` yet.** Once enrichment
     exists, showing both the raw description and the AI executive
     brief says the same thing twice.
   - Executive brief (enrichment) — confidence-tagged.
   - CSI scope matrix (enrichment) — one card per CSI division, each
     confidence-tagged with its source.
   - Verified construction team (enrichment) — a divided list. The
     section header already says "Verified", so a Confirmed badge on
     every single row is pure repetition; **badges only render for
     rows that are the exception** (`reported`/`unconfirmed`).

   **Right (5 cols) — workspace / lookup rail:**
   - **Activity feed** (`All` / `AI Signals` / `News` filter tabs) —
     merges `project.timeline` (real dated milestones) and
     `enrichment.permit` (filings, no dates) as `AI_SIGNAL` entries, and
     `project.news` as `NEWS` entries. News links render as clickable
     blue links with an external-link arrow — this replaced two
     previously-separate, now-deleted components (`ProjectTimeline`,
     `ProjectNews`) that duplicated the same underlying data across two
     disconnected sections.
   - Contacts — confidence shown as a small dot + text
     (`ConfidenceDot`), not a filled pill. A filled pill on every row of
     a dense list reads as noise once every item has one — same
     principle as the team-list fix above, different mechanism since
     Contacts (unlike "Verified construction team") doesn't already
     imply confirmed in its header.
   - Documents, when any exist.
   - **No standalone "Permits & Filings" card** — removed after review
     caught it repeating, word for word, the same permit facts the
     Activity Feed already shows as `AI_SIGNAL` entries a few dozen
     pixels above it.
   - **No location/map card** — `ProjectLocationMap` only ever showed a
     "Regional location pending" placeholder for the large majority of
     projects that aren't geocoded yet; not worth the space on this
     page. The component itself is untouched and still used by `/map/`.

5. **Back to all projects** link. No manufacturer-outreach CTA on this
   page (a "Run a brand check" button and "Still open for
   manufacturers"/"Manufacturer watch list" sections were removed —
   sales-facing content that doesn't belong in this pass).

## Design principles (apply these to any future section, not just what's listed above)

- **Never show a freshness or confidence claim that isn't backed by a
  real column.** Every date and badge on this page traces to an actual
  DB value (`project_enrichment.confidence`, `.sources`,
  `project_enrichment_checks.checked_at`, `project.first_seen_at`) —
  none are invented for the sake of looking complete.
- **Don't duplicate the same fact in two places on the same page.**
  Caught twice (Permits, and the old Timeline/News split) — if two
  sections would show the same underlying row, pick one.
- **Confidence badges lose meaning if every row has one.** Only show a
  badge when it's telling the reader something they wouldn't already
  assume from context (a section titled "Verified" implies confirmed by
  default; only the exceptions need a badge).
- **Don't name the underlying AI vendor in user-facing copy.** Describe
  what the pipeline actually did (search-grounded, cross-verified,
  link-checked), not which model did it.
- **Match density to context.** This page's type scale (`text-xs` for
  most body/table content, `text-2xl`/`text-3xl` for the title) is
  deliberately denser than the site's marketing pages — don't reuse
  `text-hero`/`text-section` here, and don't pull this page's smaller
  scale into marketing pages either.

## Real data this template depends on

| Section | Table / field |
|---|---|
| KPI grid | `projects` base columns (`estimated_value_usd`, `square_footage`, `owner`, `general_contractor`, `architect`, ...) |
| Executive brief / CSI scope / Team / Permits / Contacts | `project_enrichment` (one row per fact, `confidence` + `sources` columns) — see `db/migrations/016_project_enrichment.sql` |
| "Page updated" date | `project_enrichment_checks.checked_at` |
| "Source data pulled" date | `projects.first_seen_at` |
| Activity feed — AI Signals | `project_events`/`project.timeline` + `project_enrichment` (`permit` section) |
| Activity feed — News | `project_news` / `project.news` |
| Documents | `project_document_files` |
| Score box | `project_scores` (`compute-project-scores.py`) |

## Rollout

As of 2026-07-29, only `SPX-000157` has a real enrichment pass. Every
other project falls back gracefully (raw `description`/`key_specs`
instead of an executive brief, no CSI scope/team/activity-feed
signals/contacts sections, no freshness dates) rather than showing empty
sections — the whole page is conditional on data actually existing, not
assuming it does.

To extend this to the rest of the corpus:

```bash
python3 scripts/enrich-project-details.py --batch --apply-migration --limit N
```

`.github/workflows/enrich-project-details-pipeline.yml` already wraps
this as a `workflow_dispatch` job (cron intentionally disabled, matching
every other pipeline workflow — see 2026-07-28 decision to disable all
crons). Running it at increasing `--limit` sizes, largest-value/highest-
score projects first, is the natural rollout path — not scoped or
started as of this doc.

## Review process (repeat this for future template changes)

Every round of this page's design went through the same loop, not just
a single pass:

1. Make the change, verify it builds (`npx tsc --noEmit`, `npm run
   build`).
2. Deploy, confirm live via direct `curl`/screenshot — never trust a
   deploy notification alone.
3. Screenshot the live page and send it to Gemini via
   `scripts/gemini_visual_review.py` for an independent critique.
4. Fix what's concrete and verifiable (data contradictions, real
   duplication, actual color/alignment inconsistencies) — not every
   subjective suggestion. Verify claims independently before acting on
   them (e.g. the "four different greens" note in one round turned out,
   on inspection, to already be two consistent design tokens at
   different opacities — not a real issue).
5. Repeat until a review round comes back clean or only with minor,
   optional suggestions.

This caught real bugs a single build-and-ship pass wouldn't have:
a genuine data contradiction (Architect/GC shown as both "Not reported"
and "Confirmed" on the same page), a color-language mismatch introduced
by an earlier fix, and duplicate content introduced by a later one.

## History

This file originally held a pre-build draft plan (2026-07-26) written
before any of the above was built, with open questions about a news
source, the scoring formula, and enrichment cadence. Those questions
were resolved during the actual build (two-pass Gemini search grounding
for enrichment; `project_scores`/`compute-project-scores.py` for the
score; the enrichment pipeline's own 30-day recheck cooldown via
`project_enrichment_checks` for cadence) — superseded by everything
above rather than kept as a separate historical section, since the
draft's specific proposals didn't survive intact.
