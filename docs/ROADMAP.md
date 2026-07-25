# SpecIndex Roadmap

Canonical tracker — edit this file directly (git-tracked, no duplication problem).
A Google Sheet mirror is kept in Drive for non-technical sharing, refreshed on request
rather than on every edit (Sheets can't be updated in place — see note at bottom).

| # | Milestone | Status | Notes |
|---|---|---|---|
| 1 | Product strategy + architecture doc | Done | |
| 2 | Georgia corpus v0 (Kimi-structured), expanded to 126 projects / 10 states | Done | |
| 3 | Static SpecIndex site + project search UI | Done | |
| 4 | Firebase Hosting init + first deploy | Done | Live at specindex.ai |
| 5 | Custom domain specindex.ai | Done | |
| 6 | GitHub Actions CI/CD (PR previews + live deploy on merge to main) | Done | |
| 7 | Phase 1 Postgres (Cloud SQL) + read API (Cloud Run) | Done | Live and verified; schema v2 (migrations 002/003) adds numeric surrogate keys, external ID crosswalk, project_csi_divisions fact table |
| 8 | Complete corpus capture for remaining 40 states | Open | |
| 9 | Wire the Next.js site to specindex-api instead of static JSON | Done | Live on specindex.ai as of 2026-07-25 |
| 10 | Spec book extraction pipeline (PyMuPDF -> CSI division LLM pass -> cited JSON) | In Progress | Built: `scripts/extract-spec-book.py`. Parsing/chunking verified against a synthetic PDF. `--pdf` now also accepts a `gs://bucket/path.pdf` URI (downloads and cleans up a temp file). `--write-bq` streams results into `warehouse.spec_extractions`/`citations`; verified 2026-07-25 with a synthetic payload queried back correctly. LLM classification pass itself still untested (no live Anthropic API key in this env) — see item 13 |
| 11 | Firestore or Postgres-backed authenticated manufacturer seats | Open | |
| 12 | Automated permit/press capture job + brand NER | Open | |
| 13 | Run extract-spec-book.py end-to-end against a real spec book PDF + live Anthropic API | Open | LLM classification layer built but never exercised live |
| 14 | Wire api/main.py to expose schema v2 columns (project_sk / external_ids / csi_division_codes / status_code) | Done | Deployed 2026-07-25 (`specindex-api-00003-hrl`) — `project_sk`/`external_ids`/`record_type` now in `/v1/projects` response |
| 15 | Fix Chicago-style bundled-permit rows (60+ permits collapsed into one row's owner/architect/description) | Open | Data quality issue independent of schema — see `docs/DATA_SOURCES.md` |
| 16 | Pull SAM.gov GA construction data (federal solicitations + spec/drawing attachments) | Open | `scripts/pull-sam-gov-ga.py` built and tested live; blocked on SAM.gov's daily API quota (throttled after ~10 calls, resets 2026-07-26 00:00 UTC) — consider applying for a SAM.gov System Account for a real quota. Main value is real spec/drawing attachments feeding item 13, not project volume (GA federal construction volume looked thin, ~10 hits) |
| 17 | GCS bucket (`specindex-ai-raw-documents`) + BigQuery `warehouse` dataset (`spec_extractions`/`citations`/`entity_resolution`) provisioned | Done | Smoke tested 2026-07-25 (`scripts/test-gcp-storage-bq.py`): GCS upload/download byte-for-byte round trip, BQ insert/query round trip. `entity_resolution` intentionally left unwired — no manufacturer-name canonicalization logic exists yet, so nothing should write raw (unresolved) mentions into a table meant for resolved ones. Note: BQ streaming inserts can't be `DELETE`d for up to ~90 min (streaming buffer), so ad hoc test rows may take a while to clean up |

---

**Why this file exists instead of only a Google Sheet:** the Drive MCP tools (and the
`.gsheet` stub files Google Drive Desktop syncs locally) have no in-place update
capability for Google-native Sheets/Docs — only create-new and read. Every prior
"update" to the Drive roadmap created a new file instead of editing the existing one,
producing duplicates. This file is the fix: a real file, edited in place, no duplication.
