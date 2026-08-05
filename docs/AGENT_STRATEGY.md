# SpecIndex Agent Strategy (2026-07-26, updated 2026-08-04)

> **Read the AMENDMENT at the end of this file before running the 11-step
> process.** Steps 1-7 are tuned for breadth, which is now solved (599,860
> permits). The moat lives in steps 8-10, which are document-type-blind and
> need six specific changes — including a new step 11 (substitution ledger)
> and a non-jurisdictional source track for SAM.gov / UFGS / VA TIL.

**Standing data pull window (2026-07-31): since 2025-01-01, a fixed anchor
date, not a rolling lookback.** When widening any structured source past
its narrow incremental window (30-90 days) for bulk historical depth,
pull back to January 1, 2025 and no further. `main.py`'s `--lookback-days`
is relative to "today," not absolute, so recompute it fresh each session
as `(today - date(2025,1,1)).days` -- never reuse a hardcoded day-count
from an earlier session, it drifts. Real remaining scope: add proper
absolute `--since-date` support to the pipeline.

**Known bottleneck (2026-08-01): `scripts/merge-national-corpus.py` can hang
for hours.** Its dedupe buckets records by `(state, county)` and does
O(k^2) pairwise comparison within each bucket; once a bucket (e.g. NJ after
the 2025-01-01 backfill) grows into the tens of thousands of rows, it runs
at ~100% CPU with zero progress output. If a data-processing script's CPU
time balloons far past a sane estimate with no progress logging, kill it
and reroute rather than waiting it out. Stopgap:
`scripts/fast-merge-national-corpus.py` skips the pairwise merge (relies on
Postgres `ON CONFLICT (project_id)` for exact-id dedup) and rebuilds the
full corpus in ~10 seconds. Real fix still open: sub-bucket
`project_identity._dedupe_bucket` by a cheap prefilter before pairwise
`same_project()` comparison.

**Standing coverage goal (2026-08-02): onboard commercial-permit sources for
all top-500 US counties by population.** Reference:
`docs/us_counties_by_population.md` -- real Census Bureau data (bulk CSV from
`www2.census.gov`, no API key needed) for all 3,144 US counties, with a
Corpus Coverage column; always check it before scoping a new batch, and
regenerate it periodically as the corpus grows. Do not trust ad-hoc
web-scraped or pasted "complete" county lists -- one such file looked
authoritative but was fabricated past rank ~18 (recycled county names reused
across every state with invented populations); spot-check any large ranked
dataset against a known-authoritative source. Pacing: batches of 5 counties
with review between each batch (cherry-pick worktree commits, resolve
LFS-pointer conflicts by keeping real current data, re-run the pipeline
fresh per source for real merged counts, report before the next 5) -- an
open-ended, multi-session effort, not a single continuous run.

**Documents are the moat, not permit-metadata breadth (2026-08-02).** A
county-discovery win now requires BOTH structured data AND a real document
path (per-record detail page or attachments/documents API), even if
currently gated -- pure ArcGIS/Socrata/CKAN bulk-feed wins (metadata only)
are no longer sufficient on their own. Weight future batches by likelihood
of a real document path, not just population rank -- Accela-based systems
have a consistent (if often login-gated) "Attachments" tab pattern
confirmed across UT-SALTLAKE/IN-INDIANAPOLIS/Cleveland OH/Duval FL, more
promising than bulk feeds even for a smaller county. See
`docs/ROADMAP.md` item 98 for specific login-gated opportunities already
identified (Duval FL/JaxEPICS is the strongest lead).

**Use Playwright to verify gated/SPA portals (2026-08-02).** When a county/city
permit portal is suspected login-gated or is an Angular/React SPA shell that
WebFetch/curl can't see through, use Playwright (headless Chromium,
`python3 -m playwright install chromium`) to check it live instead of
concluding "no viable source" from static research alone -- capture network
requests to see real backend API calls, and try clicking visible nav/search/
"Guest" elements to see where they actually lead. Used live to definitively
confirm Duval County FL's JaxEPICS has no guest/anonymous path. Apply to
future gated portals (SmartGov TLS blocks, OpenGov/ViewPoint SPA shells, MGO
Connect, etc.) -- see `docs/ROADMAP.md` item 98.

**Looking for the current discovery/acquisition pipeline?** Skip to
[Gemini-Assisted County/State Source Discovery](#gemini-assisted-countystate-source-discovery-implemented-2026-07-28)
below — the 4-phase, 11-step loop is the live, actively-used process.
Everything above it (Agents 1/2/3) is the original pre-build plan, kept
as historical record now that all three agents exist as described in the
2026-07-29 status update directly below.

**Status update, 2026-07-29:** this doc was written as a pre-build plan on
2026-07-26 and never updated after the plan was actually executed. As of
that date, **all three agents are built**, not drafts:

- **Agent 1 (Quality)** — `scripts/compute-state-quality.py`, writes to
  the `state_quality` table (migration 005). A raw metrics table, not a
  rolled-up score, matching the recommendation below.
- **Agent 2 (Depth)** — `scripts/compute-county-coverage.py`, writes to
  `county_coverage` (migration 004) with week-over-week diffing via
  `previous_project_count`/`delta` (migration 006). Surfaced on the
  Insights tab at `app/coverage`.
- **Agent 3 (Puller)** — national scope has run for a while via
  `pull-nj-dca-pipeline.yml`/`pull-ga-federal-pipeline.yml`/
  `pull-nc-pipeline.yml`. State scope had a real gap until 2026-07-29:
  `pull-state.yml` was a legacy, hardcoded GA/NC-only workflow predating
  the `state_agent_pipeline` framework, never extended to the ~30 sources
  wired since. Closed by `.github/workflows/pull-all-deterministic-
  sources.yml`, which pulls every no-LLM `state_agent_pipeline` key
  generically (reads the list from `state_configs.py` at run time, so new
  sources are picked up with no workflow edit needed).

The sections below are kept as historical record of the original plan and
its reasoning — most of the "Open questions" were implicitly resolved by
what actually got built (raw metrics table over a score; countywide
source-count via the diffing column over a separate binary deep/thin
metric; GitHub Actions cron over Cloud Scheduler; skip-and-log via
`continue-on-error: true` per step). All 4 crons remain disabled per
Asif's 2026-07-28 "disable all cron jobs, will come back to it later" —
`workflow_dispatch` works for manual runs on every workflow today.

## Why three agents

Coverage work today is manual and reactive: Asif or Claude reads secondhand
research, verifies a source by hand, writes a one-off pull script, and re-runs
`compute-county-coverage.py` to see the effect. That doesn't scale past ~3
states. The goal is to split this into three standing, periodic jobs:

| # | Agent | Question it answers | Cadence |
|---|---|---|---|
| 1 | **Quality monitor** | "Is the data we already have any good?" | per state |
| 2 | **Depth monitor** | "How much of each state/county do we actually cover?" | per state |
| 3 | **Puller** | "Go get more data — national first, then state, then county" | national + per-state |

This follows the sourcing-priority rule already in `docs/ROADMAP.md`: capture
broad national sources first, then state, then county — the Puller agent should
enforce that ordering, not just fire every script every run.

## Agent 1 — Data Quality Monitor (by state)

**New work.** Nothing like this exists yet. "Quality" needs a concrete
definition before this can be built. Proposed metrics per state (computed from
`projects` table, grouped by `state`):

- **Field completeness** — % of projects with a non-null address, estimated
  value, contractor, opened/announced date. Low completeness = source has a
  sparse schema (e.g. Forsyth GA: no address/value/contractor fields at all).
- **Freshness** — days since the newest project's `opened_or_announced_date`
  vs. today. Stale = source pull hasn't run recently or the source itself
  stopped updating.
- **Duplicate/merge rate** — how often `dedupe_projects()` is merging records
  within that state, as a proxy for source overlap/noise.
- **Schema conformance** — malformed IDs, missing `county`, invalid dates.

**Open question:** should this be a single "quality score" per state (easy to
scan on a dashboard) or a raw metrics table (more useful for debugging, less
useful at a glance)? Recommend: raw metrics table now, roll up into a score
later once we know which metrics actually predict "this source needs
attention."

**Output:** new table, e.g. `state_quality` (state, completeness_pct,
freshness_days, duplicate_rate, computed_at) — same pattern as
`county_coverage`. Surfaced as a new tab on `/coverage/` next to Insights.

## Agent 2 — Data Depth Monitor (by state)

**Mostly exists already** — this is close to a re-scope of
`scripts/compute-county-coverage.py` + the `county_coverage` table + the
Insights tab shipped this session, rather than a new agent. What's missing is
making it *periodic* instead of "run by hand after a corpus reload."

**Open question:** is "depth" for this agent the same as the existing
deep/thin county classification, or something more granular (e.g. depth =
number of independent sources contributing to a county, not just
binary deep/thin)? If it's the latter, `county_coverage.sources` (already an
array) already has the raw data to compute it — would just need a new derived
metric, not new plumbing.

**Recommendation:** don't build a second thing here — extend Agent 2 to mean
"run `compute-county-coverage.py` on a schedule and diff against the last run
so we can see week-over-week movement," and add a `previous_project_count`
column to spot counties that stalled.

## Agent 3 — Puller (national + state, periodic)

**New work — orchestration, not new pull logic.** The individual pull scripts
(`pull-sam-gov-bulk-national.py`, `pull-nc-arcgis.py`,
`pull-ga-municipal-commercial.py`, etc.) already exist and work; nothing about
them needs to change. What's missing is a scheduler that:

1. Runs national-scope pullers on one cadence (e.g. weekly — SAM.gov,
   USAspending, DRI).
2. Runs state-scope pullers on another cadence, one state at a time, in the
   order the sourcing-priority rule implies (bring a state to a solid
   baseline before spending effort on its counties).
3. Re-runs `rebuild-{state}-corpus.py` → `merge-national-corpus.py` →
   `load-corpus-to-postgres.py` → `compute-county-coverage.py` in sequence
   after any pull, respecting the deploy-timing gotcha already documented
   (reload Cloud SQL *before* the triggering Firebase build, not after).

**Open question — where does this run?** Three real options:

- **GitHub Actions cron** (`schedule:` trigger) — simplest, no new GCP infra,
  logs land where CI logs already live. Downside: 6-hour max job runtime on
  free tier is a non-issue here (pulls are minutes), but secrets management
  needs the DB URL added as a repo secret (currently only used via env var on
  Cloud Run).
- **Cloud Scheduler → Cloud Run Job** — more "proper" GCP-native, keeps
  secrets in the same place as the API's `DATABASE_URL`, but is new
  infrastructure to stand up (a second Cloud Run resource type, a scheduler
  job, IAM wiring) for something that doesn't need to scale.
- **Manual trigger, agent-assisted** — Claude Code runs the sequence when
  asked, no new infra at all, but doesn't get us "periodic" — still reactive.

**Recommendation:** GitHub Actions cron. Lowest new-infra cost, reuses
existing CI patterns, easy to read logs for. Revisit Cloud Scheduler only if
job frequency or duration outgrows Actions' limits.

**Open question — failure handling.** If a source starts 404ing or a schema
changes mid-run, does the agent skip that source and continue (log + alert),
or halt the whole run? Given the "verify before build" discipline already in
place, recommend: skip + log loudly (e.g. write to a `pull_failures` table or
post a GitHub issue comment), never silently drop data, never halt other
sources over one bad one.

## Suggested build order

Given the sourcing-priority rule, build these in the order they pay off:

1. **Agent 3 (Puller), national scope only** — wire up GitHub Actions cron to
   re-run the existing national pullers (SAM.gov, USAspending, DRI) weekly.
   Lowest risk, reuses 100% existing scripts.
2. **Agent 2 (Depth)** — schedule the existing `compute-county-coverage.py`
   to run after every corpus reload automatically (part of the same
   pipeline as #1), add week-over-week diffing.
3. **Agent 1 (Quality)** — new metrics + table + dashboard tab. Do this after
   #1/#2 are running so there's periodic data to actually measure trends on.
4. **Agent 3 (Puller), state scope** — extend the cron to state-level pullers,
   one state at a time, once national is stable and boring.

## Open questions to resolve before building

1. Quality score vs. raw metrics table (Agent 1)?
2. Is "depth" binary deep/thin or a graduated source-count metric (Agent 2)?
3. GitHub Actions cron vs. Cloud Scheduler/Cloud Run Job (Agent 3)?
4. Skip-and-log vs. halt-on-failure for a broken source mid-run (Agent 3)?
5. Cadence: is weekly right for national, and what's right for state-level
   (weekly per state would mean ~3 states/week today — fine at 3 states,
   needs rethinking past ~10)?

## Gemini-Assisted County/State Source Discovery (IMPLEMENTED, 2026-07-28)

Unlike the rest of this doc, this section describes a real, running process —
not a draft plan. This is the actual workflow used to find and wire every new
county/state source added on 2026-07-28 (Wayne MI, Cook IL, Miami-Dade FL,
King WA, Tarrant TX, Franklin/Cuyahoga OH, Mecklenburg/Wake NC, Fairfax VA,
Philadelphia PA, San Diego CA, Dallas/Bexar TX, TDLR TABS statewide TX,
Colorado Springs CO, Cleveland OH). It's now an 11-step loop, **reordered
2026-07-31 into 3 phases per an external review** (recorded in full at
`docs/PIPELINE_REVIEW_2026-07-31.md`) — the step numbers below are not the
order these steps were originally added in; see that doc for the history
and reasoning behind each move. **Steps 8 (document pull), 9 (text
extraction), and 10 (enrichment) are all required for every project pulled
via a structured source, not optional follow-ups** — do not consider a
jurisdiction "done" after step 7 alone, and do not consider an individual
project "done" without steps 8-10. **Step 6 (research fallback) is
conditional, not required for every project** — it only applies when
steps 1-4 find no structured source at all for a jurisdiction.

At a glance, the three phases answer three different questions:

- **Phase I — Source Discovery** (steps 1-4): *Does a live, pullable data
  source exist for this jurisdiction?* Ends with either a confirmed
  source or a logged dead end — never both left open.
- **Phase II — Project Acquisition** (steps 5-7): *Given Phase I's
  answer, how do we turn that into a deduplicated list of real
  candidate projects?* Forks into provider wiring (a source exists) or
  research fallback (it doesn't) — both paths converge on the same
  deduped output before Phase III starts.
- **Phase IV — The Moat** (step 11): *What was CONTESTED?* Runs on
  addenda/amendments and records approved and rejected substitutions with
  dates and citations. Steps 1-10 capture what was specified; only this
  captures who was displaced.
- **Phase III — Project Processing & Enrichment** (steps 8-10): *For
  each new project, what do we now go pull, extract, and enrich to make
  its page useful?* Runs only on what Phase II already deduplicated, so
  nothing here is spent twice on the same project.

### Phase I — Source Discovery

1. **Discovery — Gemini, with context.** Send a query through
   `scripts/gemini_discovery_chat.py --session <name> "..."`. Not stateless:
   the script replays the full prior conversation from
   `data/gemini_sessions/{name}.json` (gitignored) before each new turn, so
   Gemini keeps context across a multi-step jurisdiction investigation.
   Google Search grounding always on.
2. **Verification — always live, never trusted.** Every URL/agency-code/
   dataset-ID gets an actual probe (curl for simple reachability, Playwright
   when a real browser is needed). Freshness checked via real `MAX(date)`
   queries, never catalog metadata. When Gemini's specific guess is
   close-but-wrong, try plausible variants directly before looping back.
3. **Feedback loop.** If everything fails, write a `GEMINI_FEEDBACK_REPORT`
   (status overview, exact failure codes, what's being asked for) back into
   the *same* persistent session, so Gemini has the full trail of what's
   already ruled out. Can chain many rounds.
4. **Institutional memory — moved up from the former step 6.** Every batch
   — wins *and* dead ends — gets a `docs/ROADMAP.md` entry and a status
   line in `data/jurisdiction_health_matrix.json`, logged **immediately
   upon a lead being confirmed dead (step 2/3), not batched to the end** —
   if step 2 fails and the run is aborted, logging that only happens later
   in the sequence never executes for that failure. This is the first
   phase's actual output: a jurisdiction is either resolved to a live
   source, or logged as a dead end with evidence, before anything else
   happens.

### Phase II — Project Acquisition (the fork)

Two mutually exclusive paths out of Phase I, both producing the same thing:
a standardized list of raw project candidates to hand to Phase III.

5. **Provider wiring** *(path A — a structured source was found)*.
   Confirmed sources get an existing provider (`Socrata`/`ArcGIS`/
   `Accela`/`EnerGov`/`CKAN`/`Carto`/`CSV`/`TdlrTabs` — 8 platform types
   as of 2026-07-28) or a new one if the platform is genuinely novel.
   Config goes into `scripts/state_agent_pipeline/core/state_configs.py`,
   dry-run first, then `--merge-state`.
6. **Direct project-level research fallback** *(path B — moved up from the
   former step 9; fires only when steps 1-4 find no structured source at
   all)* **— added 2026-07-31, for any state, not just Illinois.** A real
   and common outcome for smaller counties/cities with no digitized permit
   system at all (confirmed live for ~20 IL jurisdictions in one batch:
   DuPage/Lake resolved to false positives, McHenry/Kane/Will named the
   right platform but wrong exact URL, McLean/Rock Island/St. Clair are
   real sites with no online application system, Winnebago/Madison gave
   dead URLs). No pullable source doesn't mean no real commercial
   construction activity worth capturing — this path researches specific
   named projects directly instead of a feed:

   a. **Grounded research call.** One `google_search`-grounded Gemini
      call per county (or per project, for a deeper follow-up), asking
      for named projects with a fixed field set (name, address, type,
      cost + confidence level, SF/acreage, developer, contractor,
      architect, status, tenants, completion date, source citation) and
      an explicit instruction to write "Not identified in public
      records" rather than guess at any field it can't find. See
      response_mime_type caveat in step 1/Flash's docstring above
      (`scripts/research-county-sources.py`) -- the same
      google_search-corrupts-structured-output issue applies here, so
      this call must NOT set response_mime_type either. **Also ask for a
      per-project "pullable document" check as part of this same
      call** -- added 2026-07-31, per Asif's explicit ask ("make sure
      both projects and docs are captured, especially drawings"): the
      grounded call must separately state, per project, whether it can
      find an actual document (site plan PDF, PUD plan set, permit
      application, RFP, EIS report, drawing set) with a direct URL on
      the relevant municipal/county planning department's site -- not
      just a news article about the project. If none is findable, it
      must say "No pullable document found" explicitly rather than
      omitting the question. **A "pullable document" claim from this
      call is not itself verified** -- it still needs the same
      live-URL check as everything else (confirmed live on McLean
      County, IL: a first pass returned portal-level domains like
      `normalil.gov`/`illinois.gov` rather than exact document URLs --
      those domains being real is not the same as the specific document
      being reachable at a specific link). Do not treat a document as
      pulled until it has actually been fetched, the same discipline as
      step 8 below.
   b. **Independent cross-check (REQUIRED, not optional) -- this is the
      whole point of the step.** Every specific numeric or named-entity
      claim from (a) gets re-verified via a SEPARATE search call, not a
      second read of the same grounded response -- trusting one model's
      self-reported "High confidence" is exactly the failure mode this
      whole doc exists to prevent. Verified live 2026-07-31 across 8
      claims (DuPage + Cook County test batch): 6 fully confirmed
      (Block 59 $53M redevelopment cost, Joanne B. Wagner Community
      Center's $84.95M/Dewberry/McHugh+Nacional JV/fall 2027, Meadowbrook
      Shopping Center's $9.5M TIF cost, Amazon Oak Brook's 225,000 SF/27
      acres/Oct 2028, Obama Presidential Center's June 19 2026 opening,
      111 W. Monroe's developer/architect/contractor), but 1 real
      discrepancy caught (111 W. Monroe's hotel room count: Gemini
      claimed 308 keys, independent search found the real figure is 226)
      and 1 claim left unconfirmable (111 W. Monroe's $345.7M total
      project cost -- only the $40M+$50M TIF funding pieces are publicly
      documented, no total project figure exists in public sources).
      This ~75% clean/~25% needs-a-second-look rate is exactly why the
      cross-check is mandatory, not optional, and why nothing from (a)
      gets treated as fact until (b) confirms it.
   c. **Load path -- built and run 2026-07-31.**
      `scripts/load-research-fallback-projects.py` converts a findings
      file's projects into the corpus schema
      `load-corpus-to-postgres.py` already expects, with a hard safety
      rule: only projects with `cross_checked: true` AND a `CONFIRMED`
      result are included by default (`--include-unverified` is an
      explicit opt-out, not the default) -- a claim from (a) that
      never went through (b) does not meet the bar every other source
      in this corpus meets. project_id convention:
      `{state}-{county}-research-{slug}`, e.g.
      `il-kendall-research-cyrusone-c1-yorkville-data-center-campus`,
      so these stay visibly distinct from structured-source IDs.
      First real run: 8 of 21 total projects found across
      Kendall/McLean/Sangamon, IL met the cross-checked bar and are
      now loaded, verified live in `projects`. Run
      `compute-county-coverage.py` after loading, same as any other
      corpus change, so `/coverage` reflects the new rows.
7. **Data-quality gate / dedup — moved up from the former step 5.**
   `scripts/check-corpus-integrity.py` (+ CI on push/PR) checks for
   duplicate IDs across the whole corpus. Run **right after acquisition
   (step 5 or 6), before any of Phase III's expensive per-project work** —
   not just via CI on push after documents/enrichment have already been
   paid for. Clean structured sources route through `generic_mapping.py`'s
   no-LLM path instead of paying for Flash/Sonnet.

### Phase III — Project Processing & Enrichment

Runs only on the new, deduplicated projects Phase II produced.

8. **Project-document pull (REQUIRED, not optional) — moved up from the
   former step 7.** For every new project, find and pull its real source
   documents (RFPs, board minutes, EIS reports, site plans) the same way —
   via Gemini (`gemini_discovery_chat.py`), live-verified before download,
   uploaded to `gs://specindex-ai-raw-documents/{state}/` (not git — large
   binaries). **GCS-only, no local intermediate copy** — Asif explicitly
   said (2026-07-28) documents should never be saved to a local folder,
   only to GCS; any future document-pull script should stream/upload
   directly, not stage through `data/documents/{state}/` first (the
   existing NJ script, `scripts/fetch-nj-documents.py`, downloads locally
   then needs a separate manual `gcloud storage rsync` — that's the *old*
   pattern, not the target one). Before assuming a source's documents are
   pullable (e.g. trusting an "Accela Attachments Tab" claim from a Gemini
   discovery response), verify live whether attachments are actually
   public without login — **confirmed live for Cleveland (COC) that they
   are not**: the Attachments tab UI loads for anonymous users, but it's
   an upload form, and the real backend call that would list existing
   documents (`.../Dpr/Handlers/Api.ashx/ab/records/{id}/planroom`)
   returns 403 Forbidden anonymously. Do not skip straight to building a
   downloader on an unverified claim, even one as specific-sounding as
   Gemini's was here. **First real win, same day:** SAM.gov's public
   opportunity API (`sam.gov/api/prod/opps/v3/opportunities/{noticeId}/
   resources`, then `.../resources/files/{resourceId}/download`)
   genuinely exposes real downloadable attachments (structural drawings,
   specs, bid abstracts) with zero auth — verified by actually
   downloading and file-type-checking a real PDF. Built
   `scripts/fetch-sam-gov-documents.py` (GCS-only, per Asif's instruction
   above), ran for all 44 GA SAM.gov projects: 30/44 had real documents,
   411 files, 752MB uploaded to `gs://specindex-ai-raw-documents/
   georgia/`. Document access genuinely varies by source type (federal
   solicitations are public by law; municipal permit attachments often
   aren't) — verify per source, never assume uniformly good or bad.
   **Remaining scope:** everything besides GA-SAM and the earlier NJ
   web-research work.
9. **Document text extraction — moved up from the former step 10, added
   2026-07-29.** For every document just pulled in step 8, extract real
   per-page text into `document_pages` (pgvector-ready, embedding column
   added but not yet populated) via
   `scripts/extract-document-text.py --document-file-id` (or `--batch
   --state --document-type`) — feeds step 10 below as its primary source,
   and is the foundation for the chat agent's retrieval and, later,
   structured material extraction. Native text (PyMuPDF) is tried first —
   free, instant, and most real documents in the corpus already carry an
   embedded text layer, including CAD-exported drawing sheets. Only pages
   with no meaningful native text (<20 chars) render to a one-page PDF
   and go to Google Document AI, chosen over a self-hosted OCR pool after
   a live head-to-head test (comparable accuracy, better layout-aware
   output, ~$360 total at the corpus's estimated ~240K OCR-needing pages
   vs. the engineering cost of running a CPU OCR worker pool). Automated
   via `.github/workflows/extract-document-text-pipeline.yml`, same WIF +
   Cloud SQL Auth Proxy pattern as every other pull-*.yml workflow.
10. **Project enrichment (REQUIRED, not optional) — moved down from the
    former step 8, added 2026-07-29.** Run
    `scripts/enrich-project-details.py <spx_id or slug>` (or `--batch
    --limit N` across many) to populate the AI-enriched detail-page
    sections — Executive Brief, CSI Scope Matrix, Verified Construction
    Team, Permits, Contacts — via the same two-pass search-grounded
    discovery + independent cross-check method used to build the first
    real page (`SPX-000157`, Hyundai-SK Battery Plant). **Should read step
    9's extracted document text as its primary source, using web search
    only to fill gaps or cross-check** — a project's own RFP/spec sheet is
    higher-fidelity than the open web for facts like architect or
    contractor; this reordering (previously enrichment ran before text
    extraction, forcing it to search the open web first) hasn't been
    re-implemented in `enrich-project-details.py` itself yet, only
    reflected here in step order — **real remaining scope**. Writes to
    `project_enrichment` (per-fact rows with `confidence`/`sources`) and
    `project_enrichment_checks` (a 30-day recheck cooldown, so a project
    that genuinely has nothing findable doesn't get re-queried/re-billed
    every run). This is what makes `components/ProjectDetailView.tsx` —
    **the adopted default template for every project page, see
    `docs/PROJECT_PAGE_REDESIGN.md`** — actually render its enriched
    sections instead of falling back to the raw description; a project
    without step 10 still gets a working page, just a thinner one. As of
    2026-07-29 only `SPX-000157` has been through this step; running it
    across the rest of the corpus is real remaining scope, same as
    step 8's GA-SAM/NJ-only coverage today.

### Phase IV — The Moat (step 11)

Runs on rank-1 documents (addenda / amendments) produced by step 8, after
step 9 has extracted their text.

11. **Substitution ledger (REQUIRED wherever addenda exist) — added
    2026-08-04.** Steps 1-10 capture what was *specified*; nothing captures
    what was *contested*. This step does. Pre-bid substitution requests are
    ruled on publicly and the approved or rejected manufacturers are **named,
    with dates**, in addenda posted to public bid portals and in SAM.gov
    amendments. Extract, per addendum: the requesting party, the manufacturer
    and model proposed, the manufacturer it would displace, the ruling
    (approved / approved-as-noted / rejected), the date, and a page-level
    citation. Write to a dedicated substitution table keyed to the project.

    **Why this is the moat and not just another extraction.** It is the only
    public artifact that records *competitive displacement* — who was basis of
    design, who attacked the spec, and who won. No incumbent indexes it: Dodge
    SpecShare and ConstructConnect Analyze report that you were specified, at
    MasterFormat granularity, but neither is documented as reporting your
    POSITION or who displaced you. And on state/local portals **addenda come
    down after award**, so a competitor starting later cannot backfill it.
    Two years of this data is an asset that cannot be bought.

    **Sequencing.** SAM.gov RETAINS its amendments, so prove the extraction
    on the federal corpus first — free, permanent, already wired. The
    genuinely time-sensitive build is the **state/local addenda crawler**,
    because every week it is not running is data permanently lost. A crawler
    that only ARCHIVES the PDFs is enough to start the clock; extraction can
    follow against a growing archive.

    **Status 2026-08-04:** not built. ~14 amendments held, all from SAM.gov,
    captured incidentally rather than deliberately.

**Known real limits (be honest about these, don't oversell):** discovery
still needs a human+Claude verification loop per lead every time — not
unattended. New platform types cost real debugging time regardless of county
count. All 4 scheduled crons are disabled as of 2026-07-28 (Asif's explicit
request), so nothing refreshes automatically yet. Statewide sources like
TDLR are rare (1 of 49 states fully panned out on a first broad search) but
by far the highest-leverage target when found. Real CAPTCHA gates (Colorado
Springs' PPRBD) and login/invitation-only systems (Jacksonville's JaxEPICS,
El Paso County's EDARP) are hard stops — no anti-bot-evasion tooling,
regardless of legitimate purpose. asif-test's earlier national scan found
only ~0.3% of all US counties have a clean deterministic feed at all — full
"all counties" coverage isn't realistic through this method; national +
statewide + largest ~100-300 counties by population is the realistic
scalable target.

---

## AMENDMENT 2026-08-04 — the process is document-type-blind, and the moat is a document type

Everything above optimises for **breadth**: does a jurisdiction have a pullable
source, and can we turn it into projects. That was the right objective and it
worked — the corpus is at **599,860 county permit projects across all 50
states**. Breadth is no longer the constraint.

The constraint is now **which documents**, and the ten steps above cannot
express that. Six changes, derived from the ConstructConnect teardown
(2026-08-04) reconciled against what the corpus actually holds.

**The value hierarchy the process must encode.** Ranked by how hard a
competitor could replicate it:

| rank | document | why | held 2026-08-04 |
| :- | :- | :- | :- |
| 1 | **Addenda / amendments** | The only public artifact naming *competitive displacement* — who was approved, who was rejected, on what date. Nobody indexes them, and on state/local portals they **come down after award**, so they cannot be backfilled. | ~14 |
| 2 | **Project manuals (spec books)** | Where basis-of-design lives: Div 23/26 schedules name a manufacturer + model, then an "or equal" clause. Basis of design vs listed alternate vs absent is the highest-value fact for a manufacturer, and no incumbent is documented as distinguishing them. | ~13 |
| 3 | **MEP drawing sets** | Equipment schedules carry basis-of-design too — same fact, different artifact, usually without the substitution language. A *separate* extraction problem. | ~2,121 |
| 4 | Permit cards, receipts, inspection reports, site plans | No manufacturer names. Not the moat. | bulk |

Note the inversion: **almost the entire captured corpus is rank 3**, because
steps 8-10 were written when any document counted as a win.

### The six changes

**1. Step 2 (live verification) must classify document TYPE, not just
existence.** Today it asks "are attachments public without login?". A
jurisdiction can pass that with nothing but inspection cards and still be
worthless to the moat. Record **which class** is reachable — addenda / spec
book / MEP drawings / permit card. Hillsborough passes on drawings: a partial
win, not a win.

**2. Step 8 (document pull) needs priority ordering.** The step text above
says pull "RFPs, board minutes, EIS reports, site plans" — **none of which are
the moat**. With a per-source cap, that budget currently goes to whatever
appears first in the attachment list. Rank **addenda > spec book > MEP
drawings > everything else** and let the cap fall on the tail.
`SKIP_NAME_HINTS` in `fetch-accela-documents.py` already does this crudely for
receipts; this is the same mechanism pointed at value rather than triviality.

**3. Step 9 (text extraction) must branch by document class.** Everything
currently gets generic per-page text. A spec book needs
`scripts/extract-spec-book.py` — division segmentation, then basis-of-design
and approved-manufacturer extraction per MasterFormat section. Running plain
page extraction on a project manual yields searchable text and **discards the
structure that makes it valuable**. Fork: spec books to the spec-book
extractor, everything else to the page extractor.

**4. Step 11 — the substitution ledger (NOW ADDED, see Phase IV above).** The largest gap: nothing in
steps 1-10 captured *"manufacturer X approved, manufacturer Y rejected, date
Z"*. That is the single uncopyable asset and the process has no home for it.
Runs on rank-1 documents; writes approved/rejected manufacturers with dates
and page-level citations to a dedicated table.

**5. Step 10 (enrichment) must output spec POSITION.** It currently produces
executive brief, CSI scope and team. The fact a manufacturer buys is **"am I
basis of design, a listed alternate, or absent — and who displaced me."** Add
basis-of-design position as a first-class output, sourced from step 9's
spec-book extraction rather than web search.

**6. Phase I assumes a JURISDICTION.** "Does a live, pullable source exist for
this jurisdiction?" cannot express the highest-yield moat sources, which are
national and document-class-keyed rather than county-keyed:

| source | access | what it yields |
| :- | :- | :- |
| **SAM.gov** `opportunities/{id}/resources` | free, anonymous, no API key | **Full federal project manuals AND amendments.** Verified 2026-08-04: 187 files included `SpecsAsOne.pdf` (18.9 MB) and Amendments 0001-0005. Federal amendments ARE addenda, and SAM.gov RETAINS them. |
| **UFGS** (WBDG) | free, no login | Complete Divisions 21-28, quarterly, public domain |
| **VA TIL** | free `.docx`, predictable URLs, on data.gov | Entire master spec library |
| **Public university / state agency design standards** | free, permanent URLs | MasterFormat-numbered Div 23/26. Highest breadth-to-effort ratio in the entire set; nobody harvests it systematically |
| **State/local e-procurement portals** | mostly free registration | Project manuals **plus addenda** — the only time-sensitive source, since these vanish after award |

Add a **non-jurisdictional source track** that skips Phase I's
county-discovery entirely and enters at Phase III. Without it the process
cannot express "harvest UFGS", which is among the highest-value things to do
next.

### Sequencing note that changed

The teardown treats addenda as urgent because they disappear after award.
**True for state/local portals; NOT true for SAM.gov, which retains
amendments.** So prove basis-of-design extraction on the federal corpus first
— free, permanent, already wired — and treat the state/local addenda crawler
as the genuinely time-sensitive build.

Cost is not a constraint here: **98.4% of document pages carry a native text
layer** (measured over 24,167 pages, 2026-08-04), so OCR spend does not scale
with corpus size the way earlier planning assumed.

### What is already built and merely disconnected

Three components exist and were never wired together — this is the shortest
path to the wedge, not a new build:

1. **50 `sam_gov` configs** — wired, but pull award METADATA only
2. **`scripts/fetch-sam-gov-documents.py`** — live-verified, returns spec books and amendments
3. **`scripts/extract-spec-book.py`** — already extracts basis-of-design product and approved manufacturers by MasterFormat section, and has never had a spec book to run on

---

## AMENDMENT II — 2026-08-05: three defects in the volume→value shift

Recorded after passing the strategy doc and this file to Gemini for critique.
All three are corrections to the four-part plan as originally specified, and
all three are the same shape: **a step that looks complete but silently drops
the highest-value data.**

### D1. Never classify by filename alone before applying a download cap

SAM.gov and municipal portals routinely name files `Attachment_A.pdf`,
`Doc_001.pdf`, `Amd_1.pdf`. A cap applied on filename regex drops real
Addenda (rank 1) while keeping a cover sheet named `Specification_Notice.pdf`
(rank 4). The loss is **silent and permanent** — the file is never fetched, so
nothing downstream can recover it.

**Required: two-phase fetch.** Use the SAM.gov API `description`/`name` fields
alongside the filename; for anything still unclassified, pull the first page
(HTTP byte-range where the server honours it) and test for `ADDENDUM NO.`,
`SECTION \d{2} \d{2} \d{2}`, `BASIS OF DESIGN`, `SUBSTITUTION`. **Apply the cap
only after header inspection.** This is the same discipline as the soft-404
baseline: never let a cheap signal stand in for the real one.

### D2. Spec-book extraction is ADDITIVE, not an exclusive fork

Routing spec books *exclusively* to `extract-spec-book.py` breaks two things:

1. **Retrieval.** Step 9 populates `document_pages` for pgvector + FTS. An
   exclusive fork means the highest-value documents in the corpus are absent
   from search and from the chat agent.
2. **Addenda carry spec text.** Addenda routinely rewrite whole MasterFormat
   sections — *"Delete Section 23 05 00 and replace with the attached."*
   Restricting spec extraction to files tagged "Spec Book" therefore misses
   basis-of-design changes that live inside rank-1 documents.

**Required:** page-text extraction on **everything**; spec-book extraction
additionally on **any** document whose pages match MasterFormat structure,
regardless of its file-level classification.

### D3. Spec Position is COMPUTED, not read

Sourcing position strictly from `extract-spec-book.py` produces false
negatives: a manufacturer absent from the baseline manual but approved by
Addendum 02 is reported **Absent**. That is exactly the "too many false
positives / outdated leads" failure that sinks the incumbents, and it is worse
here because we sell the citation.

    position = baseline (spec book) + substitution overrides (substitution_rulings)

    basis of design  : named as BOD in the manual AND not removed by addendum
    listed alternate : listed in the manual OR approved via a substitution ruling
    absent           : neither listed nor approved (or explicitly rejected)

Every state change carries its own page-level citation.

**Consequence for sequencing: step 10 must JOIN step 11.** They are coupled;
the ledger cannot be bolted on after position ships. Migration 043
(`substitution_rulings`, with a CHECK refusing any ruling lacking
`document_file_id` AND `page_number > 0`) is the table that join targets.

### D4. Capture and processing were never connected

Found 2026-08-05 while acting on the above. `fetch-sam-gov-documents.py` and
`fetch-accela-documents.py` contain **zero** database references — verified by
grep: no `psycopg2`, no `DATABASE_URL`, no `INSERT`. They upload to GCS. Step 9
selects its work **from `project_document_files`**. So ~78% of the captured
corpus (10,033 objects in GCS vs 2,240 rows) was invisible to text extraction,
spec extraction and enrichment.

Capture was never the bottleneck; the **seam** was, and it presented as
"extraction is slow" rather than as an error. `scripts/register-gcs-documents.py`
closes it and must run after every capture batch.

**Generalised rule: after any pipeline step, assert that the NEXT step can see
its output.** A step that succeeds into a place nothing reads from is
indistinguishable from a step that ran.
