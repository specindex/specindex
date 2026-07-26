# SpecIndex Agent Strategy (draft — working plan, 2026-07-26)

**Status: DRAFT.** This is a working document to align on approach before building
anything. Sections marked "Open question" need a decision from Asif before the
corresponding agent gets built. Related: [[standing goal]] and sourcing-priority
order in `docs/ROADMAP.md`.

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
