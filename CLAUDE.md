# Data pull window policy

- **Standing pull window: since 2025-01-01, fixed anchor date (not a rolling lookback).** Per Asif (2026-07-31): all bulk/historical-depth structured-source pulls (Socrata/ArcGIS/etc, widening past narrow 30-90 day incremental windows) should go back to January 1, 2025, not further, and not a shorter "last N days" window.
- The pipeline (`scripts/state_agent_pipeline/main.py`) only supports relative `--lookback-days`, not an absolute start date, so this anchor must be recomputed each session as `(today - date(2025,1,1)).days` before running -- do not reuse a hardcoded day-count from a prior session without recomputing, since it drifts.
- Real remaining scope: add proper absolute `--since-date` support to the pipeline so this doesn't need recomputing by hand every time.

# Known performance bottleneck: national-corpus rebuild

- **`scripts/merge-national-corpus.py` has an O(k^2) blowup and can hang for hours.** Its dedupe (`project_identity.dedupe_projects`) buckets records by `(state, county)` and does pairwise comparison within each bucket. Once a single bucket grows into the tens of thousands of rows (e.g. NJ after the 2025-01-01 backfill), the comparison count explodes and the script runs at ~100% CPU for hours with zero progress output (it only prints once at the end).
- **If a data-processing script's CPU time balloons far past a sane estimate for its input size, with no progress logging: kill it and reroute, don't wait it out.** Check `ps aux` for CPU time (not just wall clock) on any backgrounded job.
- **Stopgap in place:** `scripts/fast-merge-national-corpus.py` skips the pairwise cross-source merge entirely (relies on `load-corpus-to-postgres.py`'s `ON CONFLICT (project_id)` upsert for exact-id dedup) — rebuilds the full ~400K-row corpus in ~10 seconds instead of hours. Use it for a fast reload; `merge-national-corpus.py` remains the source of truth for real cross-source duplicate merging once the O(k^2) bug is actually fixed.
- Real remaining scope: fix `_dedupe_bucket` in `scripts/project_identity.py` to sub-bucket by a cheap prefilter (e.g. normalized address or permit-ID hash) before doing pairwise `same_project()` comparison, so large buckets don't blow up.

# Top-500-counties coverage goal

- **Standing goal (per Asif, 2026-08-02): onboard commercial-permit sources for all top-500 US counties by population**, not just an ad-hoc sample. Reference: `docs/us_counties_by_population.md` — real Census Bureau data (all 3,144 US counties, bulk CSV from `www2.census.gov`, no API key needed), with a Corpus Coverage column. Always check this file before scoping a new discovery batch; regenerate it (re-download the CSV, re-run the corpus-coverage join) periodically as the corpus grows.
- **Do not trust ad-hoc web-scraped or pasted "complete" county population lists.** One such pasted file looked authoritative but was fabricated past rank ~18 (recycled county names like "Washington County" reused across every state with invented populations, degenerating into "Washington 2 County" filler). Spot-check any ranked dataset over ~20-30 rows against a known-authoritative source before acting on it; prefer bulk downloads from the primary source (e.g. Census Bureau CSVs) over WebFetch summaries or user-pasted tables.
- **Pacing: batches of 5 counties at a time, with review between each batch** — explicitly chosen by Asif over larger batches or a continuous unattended run. After each batch: cherry-pick worktree commits, resolve LFS-pointer conflicts by keeping real current data (never trust the cherry-picked data diff), re-run the pipeline fresh per new source for real merged counts, then report before launching the next 5. This is an open-ended, multi-session effort.

# Use Playwright to verify gated/SPA portals

- **When a county/city permit portal is suspected login-gated or is an Angular/React SPA shell that WebFetch/curl can't see through, use Playwright (headless Chromium) to check it live** rather than concluding "no viable source" from static research alone. `python3 -m playwright install chromium` if not already installed. Capture network requests to see real backend API calls, and try clicking visible nav/search/"Guest" elements to see where they actually lead.
- Used live 2026-08-02 to definitively confirm Duval County FL's JaxEPICS has no guest/anonymous path (no "guest" text in rendered HTML, every nav link bounces to login or 404s) — closes a real open question, not a guess.
- Apply the same technique to future gated portals hit during county-discovery batches (SmartGov TLS blocks, OpenGov/ViewPoint SPA shells, MGO Connect, etc.) — see `docs/ROADMAP.md` item 98.

# Cost-optimization guardrails

- **Targeted file scoping**: only inspect/edit files explicitly named in the prompt or their direct dependencies. No repo-wide `find`/`grep` sweeps unless asked.
- **Concise output**: no full-file reprints — output diffs or the modified function only. Keep reasoning brief on standard edits/bug fixes.
- **Proactive compacting**: when context reaches ~70% or a sub-task completes, summarize progress, drop intermediate debug logs, and compact rather than carrying it forward. At 15 user messages in a session, flag that `/compact` or `/clear` is worth running.
