# SpecIndex Agent Strategy (2026-07-26, updated 2026-07-31)

**Standing data pull window (2026-07-31): since 2025-01-01, a fixed anchor
date, not a rolling lookback.** When widening any structured source past
its narrow incremental window (30-90 days) for bulk historical depth,
pull back to January 1, 2025 and no further. `main.py`'s `--lookback-days`
is relative to "today," not absolute, so recompute it fresh each session
as `(today - date(2025,1,1)).days` -- never reuse a hardcoded day-count
from an earlier session, it drifts. Real remaining scope: add proper
absolute `--since-date` support to the pipeline.

**Looking for the current discovery/acquisition pipeline?** Skip to
[Gemini-Assisted County/State Source Discovery](#gemini-assisted-countystate-source-discovery-implemented-2026-07-28)
below — the 3-phase, 10-step loop is the live, actively-used process.
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
Colorado Springs CO, Cleveland OH). It's now a 10-step loop, **reordered
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
