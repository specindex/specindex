# Data pull window policy

- **Standing pull window: since 2025-01-01, fixed anchor date (not a rolling lookback).** Per Asif (2026-07-31): all bulk/historical-depth structured-source pulls (Socrata/ArcGIS/etc, widening past narrow 30-90 day incremental windows) should go back to January 1, 2025, not further, and not a shorter "last N days" window.
- The pipeline (`scripts/state_agent_pipeline/main.py`) only supports relative `--lookback-days`, not an absolute start date, so this anchor must be recomputed each session as `(today - date(2025,1,1)).days` before running -- do not reuse a hardcoded day-count from a prior session without recomputing, since it drifts.
- Real remaining scope: add proper absolute `--since-date` support to the pipeline so this doesn't need recomputing by hand every time.

# Cost-optimization guardrails

- **Targeted file scoping**: only inspect/edit files explicitly named in the prompt or their direct dependencies. No repo-wide `find`/`grep` sweeps unless asked.
- **Concise output**: no full-file reprints — output diffs or the modified function only. Keep reasoning brief on standard edits/bug fixes.
- **Proactive compacting**: when context reaches ~70% or a sub-task completes, summarize progress, drop intermediate debug logs, and compact rather than carrying it forward. At 15 user messages in a session, flag that `/compact` or `/clear` is worth running.
