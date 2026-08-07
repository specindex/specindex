# Data provenance schema — as built

**Revision 1. Factual record of where source-provenance data is stored today.
Prepared for legal review. No legal conclusions are drawn here.**

Companion to `docs/COMPLIANCE_BRIEF.md` §4 (Data Clean-Room Protocol) and
`docs/BUILD_COMPLIANCE_BRIEF.md`. This file states **what exists**, including
what does not.

---

## 1. Where provenance lives

Three stores, keyed to each other:

| store | holds | provenance carried |
|---|---|---|
| **PostgreSQL** (Cloud SQL, `specindex-ai:us-central1:specindex-db`) | projects, document registrations, extracted page text, classifier output | `source_url`, `fetched_at`, `content_sha256` |
| **Google Cloud Storage** (`gs://specindex-ai-raw-documents`) | retrieved documents, unmodified | object metadata: `source_url`, `portal`, `doc_type`, `fetch_date`, `portal_state` |
| **Git** (`coverage/pull-log/*.csv`) | one append-only row per source per run | state, portal, project id, document URL, file size, retrieved date, status |

**Raw is separated from processed.** Documents are stored byte-unmodified in GCS
and content-addressed by SHA-256; extractions live in Postgres and key back to
the GCS object path.

**Retrieval logs are append-only.** One file per run, header written once, rows
only appended, committed to git. A run cannot rewrite an earlier run's record.

## 2. Mandatory fields required by §4 — current status

| §4 requirement | status | stored as |
|---|---|---|
| exact public URL | **present** | `source_url` (projects, documents), `url` (document tables) |
| access date | **present** | `fetched_at`, `fetch_date` (GCS metadata) |
| retrieval method | **present** | adapter name in the pull log |
| hash / immutable identifier | **partial** | `content_sha256` on documents; **absent on project rows** |
| source owner | **ABSENT** | — |
| applicable terms or license | **ABSENT** | — |
| access authorization | **ABSENT** | — |
| whether authentication was used | **ABSENT** | adapters never authenticate, but this is not recorded as a field |
| data classification | **ABSENT** | — |
| retention restrictions | **ABSENT** | — |
| contributor certification | **ABSENT** | not collected |

**Seven required fields are not implemented.** They are listed as gaps rather
than described as satisfied.

## 3. Retrieval behaviour, as implemented

- **No adapter authenticates.** No account is created, no credential entered, no
  login submitted. Sources requiring registration are recorded as
  `registration required` and abandoned.
- **Standard browser headers** (`User-Agent`, `Referer`) are sent to public,
  unauthenticated documents; some government CDNs reject non-browser clients for
  fully public files. No faked authentication, forged cookies or sessions,
  captcha bypass, or IP rotation.
- **Rate limiting** of at least one request per second per host.
- **robots.txt** honoured.
- **Content verification, not status codes.** A retrieval counts only when the
  bytes are a valid document and differ from the host's known error response.
- **Blocked sources are logged as outcomes** — `registration required`,
  `dead link`, `needs browser`, `unreadable format`, `no active solicitations` —
  and never worked around.

## 4. Source inventory

| file | contents |
|---|---|
| `coverage/data/state-portal-sources.csv` | 100 state portals: URL, agency, access tier, terms notes |
| `coverage/data/project-discovery-sources.csv` | 47 discovery sources: URL, API access, verification status |
| `coverage/data/top-500-counties.csv` | coverage targets with feed status |
| `config/socrata/*.yaml`, `config/arcgis/*.yaml`, `config/accela/*.yaml` | per-source endpoint, filter and field mapping |
| `scripts/portal_adapters/*.py` | one adapter per portal; retrieval logic in git |

Transformation logic, extraction prompts and validation methods are in git with
their reasoning in commit messages.

## 5. Live schema

Dumped from the running database. Row counts as of the dump.


### `projects` — 597,078 rows

| column | type | null |
|---|---|---|
| `project_id` | text | NO |
| `name` | text | NO |
| `state` | character | YES |
| `city` | text | YES |
| `county` | text | YES |
| `status` | text | NO |
| `project_type` | text | YES |
| `estimated_value_usd` | bigint | YES |
| `square_footage` | integer | YES |
| `owner` | text | YES |
| `architect` | text | YES |
| `general_contractor` | text | YES |
| `opened_or_announced_date` | date | YES |
| `description` | text | YES |
| `key_specs` | jsonb | NO |
| `mentioned_brands` | jsonb | NO |
| `competitor_watch` | jsonb | NO |
| `sources` | jsonb | NO |
| `open_for` | text | YES |
| `corpus_generated_at` | timestamptz | YES |
| `loaded_at` | timestamptz | NO |
| `project_sk` | bigint | NO |
| `status_code` | smallint | YES |
| `project_type_code` | smallint | YES |
| `state_fips` | character | YES |
| `county_fips` | character | YES |
| `cbsa_code` | character | YES |
| `latitude` | numeric | YES |
| `longitude` | numeric | YES |
| `external_ids` | jsonb | NO |
| `record_type` | text | YES |
| `value_currency` | character | NO |
| `csi_division_codes` | ARRAY | NO |
| `first_seen_at` | timestamptz | YES |
| `last_updated_at` | timestamptz | YES |
| `data_confidence` | text | NO |
| `parent_project_id` | text | YES |
| `zip` | text | YES |
| `street_address` | text | YES |
| `bbl` | text | YES |

### `project_document_files` — 20,601 rows

| column | type | null |
|---|---|---|
| `id` | bigint | NO |
| `project_sk` | bigint | NO |
| `title` | text | NO |
| `url` | text | NO |
| `content_type` | text | YES |
| `computed_at` | timestamptz | NO |
| `gcs_path` | text | YES |
| `content_sha256` | text | YES |
| `fetched_at` | timestamptz | YES |
| `document_type` | text | NO |
| `etag` | text | YES |
| `last_modified` | text | YES |
| `last_seen_at` | timestamptz | YES |
| `vanished_at` | timestamptz | YES |
| `doc_type` | text | YES |
| `spec_format` | text | YES |

### `reference_documents` — 248 rows

| column | type | null |
|---|---|---|
| `id` | bigint | NO |
| `scope` | text | NO |
| `scope_value` | text | NO |
| `doc_kind` | text | NO |
| `title` | text | YES |
| `url` | text | NO |
| `gcs_path` | text | YES |
| `content_sha256` | text | YES |
| `page_count` | integer | YES |
| `byte_size` | bigint | YES |
| `text_extracted` | boolean | NO |
| `fetched_at` | timestamptz | NO |
| `doc_type` | text | YES |
| `spec_format` | text | YES |

### `legislative_documents` — 2,242 rows

| column | type | null |
|---|---|---|
| `id` | bigint | NO |
| `jurisdiction` | text | NO |
| `matter_id` | bigint | YES |
| `matter_title` | text | YES |
| `matter_date` | date | YES |
| `attachment_name` | text | YES |
| `url` | text | NO |
| `gcs_path` | text | YES |
| `content_sha256` | text | YES |
| `byte_size` | bigint | YES |
| `project_sk` | bigint | YES |
| `fetched_at` | timestamptz | NO |

### `document_pages` — 124,120 rows

| column | type | null |
|---|---|---|
| `id` | bigint | NO |
| `document_file_id` | bigint | YES |
| `page_number` | integer | NO |
| `raw_text` | text | NO |
| `ocr_engine` | text | NO |
| `avg_confidence` | numeric | YES |
| `embedding` | USER-DEFINED | YES |
| `extracted_at` | timestamptz | NO |
| `reference_document_id` | bigint | YES |
| `legislative_document_id` | bigint | YES |

### `project_csi_divisions` — 455 rows

| column | type | null |
|---|---|---|
| `id` | bigint | NO |
| `project_sk` | bigint | YES |
| `division` | character | NO |
| `division_name` | text | NO |
| `basis_of_design_product` | text | YES |
| `approved_manufacturers` | ARRAY | NO |
| `substitution_language` | text | YES |
| `model_numbers` | ARRAY | NO |
| `source_document` | text | YES |
| `page` | integer | YES |
| `confidence` | text | YES |
| `created_at` | timestamptz | NO |
| `reference_document_id` | bigint | YES |
| `legislative_document_id` | bigint | YES |
| `page_from` | integer | YES |
| `page_to` | integer | YES |
| `openness` | text | YES |

### `substitution_rulings` — 102 rows

| column | type | null |
|---|---|---|
| `id` | bigint | NO |
| `project_sk` | bigint | NO |
| `requesting_party` | text | YES |
| `proposed_manufacturer` | text | NO |
| `proposed_product` | text | YES |
| `displaced_manufacturer` | text | YES |
| `ruling` | text | NO |
| `ruling_date` | date | YES |
| `csi_section` | text | YES |
| `csi_division` | text | YES |
| `document_file_id` | bigint | YES |
| `page_number` | integer | YES |
| `source_url` | text | YES |
| `quoted_text` | text | YES |
| `agreement` | text | YES |
| `confidence` | text | NO |
| `extracted_at` | timestamptz | NO |

### `document_processing_status` — 2,310 rows

| column | type | null |
|---|---|---|
| `document_file_id` | bigint | NO |
| `text_extracted_at` | timestamptz | YES |
| `structured_extraction_at` | timestamptz | YES |
| `page_count` | integer | YES |
| `error` | text | YES |
| `divisions_written_at` | timestamptz | YES |

---

## 6. Known gaps

1. Seven §4 fields are unimplemented (§2 above).
2. `content_sha256` exists on documents but not on project rows.
3. Contributor certification is not collected.
4. Source owner, licence and terms exist as free text in the source CSVs, not as
   structured per-record fields.
5. `coverage/data/project-discovery-sources.csv` is malformed — 29 of 47 rows
   carry 10 fields against a 9-field header, shifting `url` and `notes`.

Closing 1–4 requires schema migrations. They are recorded here rather than
deferred silently.
