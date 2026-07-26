# Project detail page redesign (draft — working plan, 2026-07-26)

**Status: DRAFT.** Working document to align on structure and the open
questions below before building. See [[project-specindex-page-redesign]] in
memory for the standing product-direction note this stems from.

## Why

The project detail page (`/projects/[id]/`) today is a flat facts grid. The
goal is an Amazon-listing-style page — dense, scannable, and anchored on a
**project score** (value + recency + news coverage) that's the actual
monetizable differentiator: it's what tells a manufacturer's sales rep which
open projects to prioritize outreach on, not just that a project exists.

## What already exists to build on

Two tables built earlier this session directly power sections of this
redesign — no new pipeline needed for them:

- **`project_events`** (migration 009) — Announced / Permit_Issued /
  Bid_Opened / Awarded per project, derived at load time. Powers the
  **timeline** section.
- **`project_sources`** (migration 008) — structured per-source provenance
  (source name, url, raw data). Powers the **sources/provenance** section.
- **`latitude`/`longitude`** — populated for ~718 projects so far (ArcGIS
  sources only). Powers the **location map**, with a graceful "not yet
  geocoded" fallback for the rest.
- **`spx_id`** (shipped 2026-07-26) — the one identifier this page shows;
  never `project_id`/`project_sk` as a second labeled field.

## Draft page structure (Amazon-listing pattern)

1. **Header** — status pill + type, project name (large), `spx_id` (quiet,
   under the title), location line. **Project Score badge**, prominent —
   this is the "4.5 stars, 230 reviews" equivalent, needs to be the visual
   anchor of the page since it's the paid value prop.
2. **Key facts grid** (exists today, extend) — value, sqft, dates, owner,
   GC, architect, plus a **score breakdown** mini-panel (value component /
   recency component / news component) so the score isn't a black box —
   transparency here builds trust the same way Amazon shows the rating
   distribution, not just the average.
3. **Timeline** (new) — `project_events` rendered as a dated sequence,
   each entry showing its source. This is the single feature that
   differentiates "we have this project" from "we've tracked this project."
4. **Location map** (new) — single-point map, shown only when lat/lon
   exists. **Leaflet + OpenStreetMap**, not Mapbox — this page is
   user-facing, and Mapbox is reserved for the internal `/map/` admin tool
   per Asif's explicit split (avoids Mapbox account/cost exposure on a
   customer-facing surface).
5. **Description / key specs** (exists today, keep).
6. **External enrichment** (new, open questions below) — news mentions,
   possibly owner/company info, if found.
7. **Sources & provenance** (new) — `project_sources`-backed list, each
   entry linking to the original record. A trust section, not just a
   citation dump — "here's exactly where every fact on this page came from."
8. **Brand/manufacturer visibility panel** (exists today, keep) —
   `mentioned_brands`/`competitor_watch`.
9. **CTA** (new, monetization-facing) — track/alert on status change,
   teaser for gated detail. Exact gating strategy is a separate business
   decision, not scoped here.

## Open questions — need Asif's input before building

1. **News-enrichment source.** Options, roughly cheapest-to-most-capable:
   - **Google News RSS** — free, no API key, but unstructured (title/link/date
     only, no full text, no reliable dedup).
   - **NewsAPI.org** or similar — real structured API, freemium tier, a new
     paid dependency at scale (7,000+ projects).
   - Something narrower — e.g. only search when a project's name/owner is
     distinctive enough to avoid false positives (a generic name like
     "Building B" would return garbage either way).
   No source has been picked or verified yet — whichever is chosen needs the
   same verify-before-build pass as every data source this session (check
   it's actually live, actually returns relevant results, before wiring it
   into every project page).

2. **Scoring formula — the actual IP.** "Value + recency + news" is the
   direction, not a formula. Needs: how value is normalized (raw dollars vs.
   percentile within state/category), what recency decay curve (linear?
   exponential? a hard cutoff?), how a handful of news mentions convert to
   a numeric component, and the overall scale (0–100? letter grade? 5-star?).
   This should be iterated on directly with Asif, not invented unilaterally
   — it's explicitly the core paid differentiator.

3. **Enrichment scope and cadence.** Running news lookups for all 7,255+
   projects on every pipeline run is likely wasteful and possibly costly
   depending on the source chosen. Options: enrich only new/changed
   projects each run, enrich only above some value threshold, or enrich on
   a slower separate cadence than the main coverage/quality pipeline.

## Next step

Resolve the three open questions above (at minimum #1 and #2), then this
becomes a normal build: extend `row_to_project()`/the API, add a new
enrichment/scoring script following the same pattern as
`compute-state-quality.py` (a scheduled job writing to a new table), and
rebuild the page template.
