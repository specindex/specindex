# SpecIndex Agent Strategy (2026-07-26, updated 2026-07-29)

**Status update, 2026-07-29:** this doc was written as a pre-build plan on
2026-07-26 and never updated after the plan was actually executed. As of
today, **all three agents are built**, not drafts:

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
Colorado Springs CO, Cleveland OH). It's a 7-step loop, and **step 7 is a
required step for every jurisdiction, not an optional follow-up** — do not
consider a jurisdiction "done" after step 6 alone.

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
4. **Provider wiring.** Confirmed sources get an existing provider
   (`Socrata`/`ArcGIS`/`Accela`/`EnerGov`/`CKAN`/`Carto`/`CSV`/`TdlrTabs` — 8
   platform types as of 2026-07-28) or a new one if the platform is
   genuinely novel. Config goes into
   `scripts/state_agent_pipeline/core/state_configs.py`, dry-run first, then
   `--merge-state`.
5. **Data-quality gate.** `scripts/check-corpus-integrity.py` (+ CI on
   push/PR) checks for duplicate IDs across the whole corpus. Clean
   structured sources route through `generic_mapping.py`'s no-LLM path
   instead of paying for Flash/Sonnet.
6. **Institutional memory.** Every batch — wins *and* dead ends — gets a
   `docs/ROADMAP.md` entry and a status line in
   `data/jurisdiction_health_matrix.json`, so the next investigation doesn't
   re-walk dead paths.
7. **Project-document pull (REQUIRED, not optional).** For every project
   captured in step 4, find and pull its real source documents (RFPs, board
   minutes, EIS reports, site plans) the same way — via Gemini
   (`gemini_discovery_chat.py`), live-verified before download, uploaded to
   `gs://specindex-ai-raw-documents/{state}/` (not git — large binaries).
   **GCS-only, no local intermediate copy** — Asif explicitly said
   (2026-07-28) documents should never be saved to a local folder, only to
   GCS; any future document-pull script should stream/upload directly, not
   stage through `data/documents/{state}/` first (the existing NJ script,
   `scripts/fetch-nj-documents.py`, downloads locally then needs a separate
   manual `gcloud storage rsync` — that's the *old* pattern, not the target
   one). Before assuming a source's documents are pullable (e.g. trusting an
   "Accela Attachments Tab" claim from a Gemini discovery response), verify
   live whether attachments are actually public without login — **confirmed
   live for Cleveland (COC) that they are not**: the Attachments tab UI
   loads for anonymous users, but it's an upload form, and the real backend
   call that would list existing documents
   (`.../Dpr/Handlers/Api.ashx/ab/records/{id}/planroom`) returns 403
   Forbidden anonymously. Do not skip straight to building a downloader on
   an unverified claim, even one as specific-sounding as Gemini's was here.
   **First real win, same day:** SAM.gov's public opportunity API
   (`sam.gov/api/prod/opps/v3/opportunities/{noticeId}/resources`, then
   `.../resources/files/{resourceId}/download`) genuinely exposes real
   downloadable attachments (structural drawings, specs, bid abstracts)
   with zero auth — verified by actually downloading and file-type-checking
   a real PDF. Built `scripts/fetch-sam-gov-documents.py` (GCS-only, per
   Asif's instruction above), ran for all 44 GA SAM.gov projects: 30/44 had
   real documents, 411 files, 752MB uploaded to
   `gs://specindex-ai-raw-documents/georgia/`. Document access genuinely
   varies by source type (federal solicitations are public by law;
   municipal permit attachments often aren't) — verify per source, never
   assume uniformly good or bad. **Remaining scope:** everything besides
   GA-SAM and the earlier NJ web-research work.

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
