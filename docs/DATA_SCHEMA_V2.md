# SpecIndex Data Schema V2

**Status: proposed and executed 2026-07-25 (additive migration `db/migrations/002_schema_v2.sql`), against live `specindex-db`.**

Goal: make the `projects` table mergeable by an external data science team (Snowflake/Databricks/API consumer joining SpecIndex data against their own CRM/ERP/permit data), not just servable to the SpecIndex site.

This is additive-only. Nothing in `schema.sql` v1 is dropped or renamed; the live API (`api/main.py`) continues to work unmodified against the existing columns.

## What changed

### 1. Numeric surrogate key + descriptive natural key

| Column | Type | Notes |
|---|---|---|
| `project_sk` | `BIGINT GENERATED ALWAYS AS IDENTITY`, **new PRIMARY KEY** | Stable numeric key for warehouse joins and FK references. Cheaper to index/join than a text slug; also plays better with LLM/chatbot function-calling (numeric IDs tokenize cleanly). |
| `project_id` | `TEXT`, demoted from PK to `UNIQUE NOT NULL` | Unchanged as a column — still the human-readable slug the API filters on (`WHERE project_id = ...` continues to work identically). |

Same numeric+descriptive pairing applied to two more fields, since both matter for numeric filtering/sorting in a warehouse or funnel dashboard:

| Column | Type | Mapping |
|---|---|---|
| `status_code` | `SMALLINT` | `planning`=1, `design`=2, `permitting`=3, `bidding`=4, `under_construction`=5, `completed`=6, `permitting` variants land at 3. Backfilled from existing `status` text — deterministic, no data invented. |
| `project_type_code` | `SMALLINT` | Ordinal code per distinct `project_type` value seen in the corpus (commercial, industrial, data_center, healthcare, etc.), assigned alphabetically. Backfilled from existing `project_type` text. |

### 2. External interoperability

| Column | Type | Backfilled? | Notes |
|---|---|---|---|
| `external_ids` | `JSONB DEFAULT '{}'` | **Yes** | Parsed from the existing `project_id` slug pattern where deterministic — e.g. `ga-alpharetta-bc250259` → `{"county_permit": "BC250259"}`, `ga-dri-4802-...` → `{"ga_dri_number": "4802"}`. This is derived from data already in the table, not invented. |
| `record_type` | `TEXT` | **Yes** | `'dri_filing'` for `dri-` slugs, `'permit_or_press'` otherwise. Deterministic from existing `project_id`. |
| `value_currency` | `CHAR(3) DEFAULT 'USD'` | Yes (constant) | Every `estimated_value_usd` in the corpus is USD today; makes the unit explicit for external consumers instead of implied by column name. |
| `state_fips` | `CHAR(2)` | **Yes**, via new `dim_state` table | Standard Census state FIPS code, joined from a static 51-row state→FIPS reference table (all 50 states + DC — verifiable, unambiguous public reference data, not fabricated). |
| `county_fips` | `CHAR(5)` | **No — left NULL** | Would require a full Census county FIPS crosswalk (3,000+ entries) and fuzzy-matching against free-text `county` values in this table (e.g. "Fulton" vs "Fulton County"). Column added as a schema slot; backfilling it against an unverified guess would put wrong government codes into a production dataset. Needs a proper Census Gazetteer join as follow-up work. |
| `cbsa_code` | `CHAR(5)` | **No — left NULL** | Same reasoning — needs verified Census CBSA delineation file, not fabricated. |
| `latitude`, `longitude` | `NUMERIC(9,6)` | **No — left NULL** | Needs a real geocoding call (Census Geocoder or Google Maps) per address. Not fabricated. Follow-up: batch-geocode via `scripts/geocode-projects.py` (not built yet). |

### 3. CSI MasterFormat division codes (the product-critical field)

**Revised 2026-07-25 (`db/migrations/003_csi_divisions_table.sql`):** a project can hit a dozen+ CSI divisions, each with its own citation — that's a one-to-many fact, not a nested attribute on the project row, and it's also the single field customers are most likely to filter/join on. A JSONB array of citations is friction for Snowflake/Databricks/BI tools compared to a normalized table. So this is now a separate table, not a JSONB column:

| Table/Column | Type | Notes |
|---|---|---|
| `projects.csi_division_codes` | `SMALLINT[] DEFAULT '{}'` | Kept on the project row — cheap denormalized array (e.g. `{07,23}`) for "does this project touch division X at all" without a join. Auto-maintained by `scripts/extract-spec-book.py` from the table below. |
| `project_csi_divisions` (new table) | one row per division per project | `id, project_sk (FK → projects.project_sk, ON DELETE CASCADE), division, division_name, basis_of_design_product, approved_manufacturers TEXT[], substitution_language, model_numbers TEXT[], source_document, page, confidence, created_at`. `UNIQUE (project_sk, division, source_document, page)` so re-processing the same PDF upserts cleanly instead of duplicating. |

Both are **empty for all 652 existing rows.** Nothing in the current corpus comes from an actual spec book — see `docs/DATA_SOURCES.md`. This table exists so the spec-book extraction pipeline (`scripts/extract-spec-book.py`, see roadmap item #10) has a place to write verified, cited output per project. This is the intended long-term path to real division codes discussed in `docs/CONTEXT.md`.

### 4. Warehouse/versioning fields

| Column | Type | Notes |
|---|---|---|
| `first_seen_at` | `TIMESTAMPTZ` | Backfilled from existing `loaded_at` for current rows (best available proxy — this is the first load, so first-seen and loaded coincide today). Going forward, the loader should preserve this on `ON CONFLICT` upserts instead of overwriting it. |
| `last_updated_at` | `TIMESTAMPTZ` | Same backfill as above; going forward this should update on every upsert while `first_seen_at` stays fixed. **`scripts/load-corpus-to-postgres.py` needs a follow-up edit** to stop overwriting `first_seen_at` on conflict — not done in this pass. |
| `data_confidence` | `TEXT DEFAULT 'unverified'` | Placeholder for a transparency signal on AI-assisted-capture rows. Not scored yet — default only. |

### 5. Known data-modeling gap, flagged but not auto-fixed

`parent_project_id TEXT` (nullable, self-referencing `project_id`) was added as a column to support rolling up permit-level rows into one project (e.g. the ~20 separate `ga-alpharetta-bc25031x` "Brookside Reserve Lot D—" permits are one physical development). **Left NULL for all rows** — auto-grouping by fuzzy name/location match risks incorrectly merging distinct projects that happen to share a generic name. This needs a human-reviewed pass, not a heuristic run against production data.

## Migration files

- `db/migrations/002_schema_v2.sql` — the additive changes described above.
- `db/migrations/003_csi_divisions_table.sql` — splits `csi_divisions` out into the `project_csi_divisions` table (section 3 revision).

Both idempotent (`IF NOT EXISTS` throughout), safe to re-run.

## Follow-up work (not done in this pass)

1. `api/main.py` — expose `project_sk`, `external_ids`, `csi_division_codes`, `status_code` in API responses.
2. `scripts/load-corpus-to-postgres.py` — preserve `first_seen_at` across upserts; populate `status_code`/`project_type_code`/`external_ids`/`record_type` on every future load instead of only in the one-time backfill.
3. County FIPS / CBSA / lat-long backfill — needs a verified Census crosswalk + geocoder, scoped separately.
4. `parent_project_id` dedup pass — needs human review of candidate duplicate clusters, not automated.
5. `scripts/extract-spec-book.py` — populates `csi_division_codes` / `csi_divisions` per project once spec book PDFs are sourced (see that script for status).
