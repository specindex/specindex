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
| 13 | Run extract-spec-book.py end-to-end against a real spec book PDF + live Anthropic API | Open | `ANTHROPIC_API_KEY` added and validated in `.env` 2026-07-25 (confirmed via `models.list()`); only blocker now is having an actual spec book PDF (not a permit form — none of the sample PDFs in `data/documents/` qualify). Deprioritized below #18 per 2026-07-25 decision: solidify the Georgia dataset first, since the extraction pipeline is only as valuable as the project corpus it attaches citations to |
| 14 | Wire api/main.py to expose schema v2 columns (project_sk / external_ids / csi_division_codes / status_code) | Done | Deployed 2026-07-25 (`specindex-api-00003-hrl`) — `project_sk`/`external_ids`/`record_type` now in `/v1/projects` response |
| 15 | Fix Chicago-style bundled-permit rows (60+ permits collapsed into one row's owner/architect/description) | Open | Data quality issue independent of schema — see `docs/DATA_SOURCES.md` |
| 16 | Pull SAM.gov GA construction data (federal solicitations + spec/drawing attachments) | Open | `scripts/pull-sam-gov-ga.py` built and tested live; blocked on SAM.gov's daily API quota (throttled after ~10 calls, resets 2026-07-26 00:00 UTC) — consider applying for a SAM.gov System Account for a real quota. Main value is real spec/drawing attachments feeding item 13, not project volume (GA federal construction volume looked thin, ~10 hits) |
| 17 | GCS bucket (`specindex-ai-raw-documents`) + BigQuery `warehouse` dataset (`spec_extractions`/`citations`/`entity_resolution`) provisioned | Done | Smoke tested 2026-07-25 (`scripts/test-gcp-storage-bq.py`): GCS upload/download byte-for-byte round trip, BQ insert/query round trip. `entity_resolution` intentionally left unwired — no manufacturer-name canonicalization logic exists yet, so nothing should write raw (unresolved) mentions into a table meant for resolved ones. Note: BQ streaming inserts can't be `DELETE`d for up to ~90 min (streaming buffer), so ad hoc test rows may take a while to clean up |
| 18 | Solidify Georgia corpus (window + new sources + Accela) | In Progress | Georgia grew 489 → **1,377** projects (24mo window, up from 12mo), national corpus now 1,540 across 50 states. Added: Fulton County ArcGIS (299), Savannah/SAGIS ArcGIS (103), USAspending.gov federal awards (414, no key/quota needed) — see `docs/states/ga.md` 2026-07-25 update for full detail, source rejections (Columbus/Atlanta-CSV stale, Cobb/Gwinnett "ArcGIS" claims didn't hold up), and the Gwinnett Accela root-cause/fix. **Not done:** Atlanta/Cobb/Gwinnett Accela 24mo pulls failed — `aca-prod.accela.com` and GPR's `ssl.doas.state.ga.us` both started timing out simultaneously late in the session (likely self-inflicted rate-limiting from heavy automated traffic), which also wiped the working 318-record Gwinnett test via the shared-output-file race. Retry once backoff time has passed |
| 19 | Georgia Procurement Registry (GPR) — automate USG/state bid search | Open | Confirmed real, live, structured bid data (agency, category, NIGP codes, description, buyer contact, and a Documents tab likely holding real spec/bid attachments — directly relevant to item 13's extraction pipeline). Search UI (`govEntity`/`catType` dropdowns) loads inconsistently via Playwright `select_option`; next attempt should intercept the frontend's actual network requests to find the backend JSON endpoint rather than keep driving the UI blind. Also currently blocked by the same network timeout as item 18 |
| 20 | Fix `pull-ga-accela-commercial.py` output collision | Open | All three agencies (Atlanta/Gwinnett/Cobb) write to the same `data/raw/ga-accela-commercial.json` with no per-agency `--out` override — running any two concurrently or in sequence-with-failure silently clobbers prior results. Caused real data loss 2026-07-25 (lost a working 318-record Gwinnett pull). Add `--out` support or agency-specific default filenames before the next Accela run |
| 21 | Add Georgia Tech's ~8 named current capital projects to corpus (manual research) | Open | Found via `facilities.gatech.edu` "Current Major Projects": Tech Square Phase 3, Fanning Student-Athlete Performance Center, Curran Street Residence Hall, D.M. Smith Building renovation, East Campus Streetscape, Ferst Drive projects (x2), Chilled Water Distribution resiliency. Hand-curated list, not a bulk API — same tier as existing "prior research" entries. UGA's equivalent page not yet checked |

---

**Why this file exists instead of only a Google Sheet:** the Drive MCP tools (and the
`.gsheet` stub files Google Drive Desktop syncs locally) have no in-place update
capability for Google-native Sheets/Docs — only create-new and read. Every prior
"update" to the Drive roadmap created a new file instead of editing the existing one,
producing duplicates. This file is the fix: a real file, edited in place, no duplication.
