# SpecIndex Database Design

How unstructured public records become a structured, queryable project lifecycle
record — and why that record is the thing worth charging for.

---

## 1. Recommendation: PostgreSQL

**Use PostgreSQL (Cloud SQL for PostgreSQL on your existing GCP billing account).**

A project lifecycle is relational. One project has many bid packages; each package
has many bidders; one bidder wins; each award produces installed products; each
product ties back to a manufacturer. Reporting queries are almost entirely joins
and aggregates across those relationships — "which GCs won concrete packages in
Georgia last year, and whose product went in."

Postgres also covers the two hard parts of this problem in one engine:

| Need | Postgres feature |
| --- | --- |
| Keep raw documents verbatim | `JSONB` columns, no schema migration to store a new source shape |
| Fuzzy company-name matching | `pg_trgm` trigram similarity indexes |
| Semantic project deduplication | `pgvector` embeddings with HNSW indexes |
| Point-in-time history | Append-only history tables with `tstzrange` |
| Reporting rollups | Materialized views, refreshed on ingest |

### Why not Firestore

Firestore is already available in your Firebase project, so it deserves an explicit
rejection rather than silence. It is a document store with no joins and no
aggregation beyond counting. Every reporting question above would require either
fanning out reads per project or maintaining hand-rolled aggregate documents that
drift from the source data. The queries that justify the paid tier are exactly the
queries Firestore is worst at. Keep Firestore for app state and auth-adjacent data
if you want; do not make it the system of record.

### Why not BigQuery as primary

BigQuery is excellent for the analytics layer and a reasonable downstream target
once volume grows. It is a poor primary store here because ingestion involves
constant row-level updates — re-resolving entities, superseding facts, correcting
extractions — and BigQuery is built for append-mostly workloads. Land in Postgres,
replicate to BigQuery if and when the reporting workload outgrows it.

### Architectural constraint to be aware of

The site is currently a **static export** (`output: "export"` in `next.config.ts`)
served by Firebase Hosting. A static page cannot query Postgres at request time. So:

- Postgres is the system of record; the Python pipeline writes to it.
- The build step exports a JSON snapshot for the free public pages. This is how the
  site works today and it keeps working.
- **Gated, per-customer reporting cannot be static.** It needs an authenticated
  runtime — Cloud Run or Firebase Functions in front of Postgres, with Firebase Auth
  for identity. Plan for that when reporting goes paid.

---

## 2. Schema

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2.1 Companies and entity resolution

Every actor — owner, architect, GC, subcontractor, manufacturer, distributor — is a
company. Roles are per-project, not per-company, because a firm can be a GC on one
job and a sub on another.

```sql
CREATE TABLE companies (
  company_id     BIGSERIAL PRIMARY KEY,
  canonical_name TEXT        NOT NULL,
  hq_city        TEXT,
  hq_state       CHAR(2),
  website        TEXT,
  duns           TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "Ryan Companies" and "Ryan Companies US, Inc." must resolve to one row.
CREATE TABLE company_aliases (
  alias_id   BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  alias      TEXT   NOT NULL UNIQUE,
  source     TEXT
);

CREATE INDEX company_aliases_trgm
  ON company_aliases USING gin (alias gin_trgm_ops);
```

### 2.2 Projects, keyed by a stable ID

The stable `project_id` is the spine of the whole system — it is what lets a permit
filed in 2026 and a closeout document filed in 2029 describe the same building.

```sql
CREATE TYPE project_stage AS ENUM (
  'announced', 'planning', 'design', 'permitting',
  'bidding', 'under_construction', 'completed', 'cancelled'
);

CREATE TABLE projects (
  project_id          TEXT PRIMARY KEY,           -- 'ga-centennial-yards'
  name                TEXT NOT NULL,
  state               CHAR(2) NOT NULL,
  county              TEXT,
  city                TEXT,
  project_type        TEXT,
  owner_id            BIGINT REFERENCES companies(company_id),
  architect_id        BIGINT REFERENCES companies(company_id),
  gc_id               BIGINT REFERENCES companies(company_id),
  estimated_value_usd BIGINT,
  square_footage      INTEGER,
  announced_date      DATE,
  current_stage       project_stage NOT NULL,
  name_embedding      vector(768),                -- dedupe across jurisdictions
  first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX projects_name_trgm ON projects USING gin (name gin_trgm_ops);
CREATE INDEX projects_embedding ON projects USING hnsw (name_embedding vector_cosine_ops);
CREATE INDEX projects_state_stage ON projects (state, current_stage);
```

### 2.3 Unstructured in: raw documents

Raw payloads are immutable. This is the single most valuable design decision in the
schema: when extraction models improve, you re-run them over documents you already
have instead of re-crawling the internet.

```sql
CREATE TYPE source_type AS ENUM (
  'permit', 'press', 'owner_release', 'spec_book', 'addendum',
  'bid_tab', 'award_notice', 'closeout', 'trade_press'
);

CREATE TABLE source_documents (
  source_id    BIGSERIAL PRIMARY KEY,
  project_id   TEXT REFERENCES projects(project_id) ON DELETE SET NULL,
  source_type  source_type NOT NULL,
  jurisdiction TEXT,
  url          TEXT,
  title        TEXT,
  published_on DATE,
  retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash TEXT NOT NULL UNIQUE,   -- skip re-processing identical fetches
  raw_payload  JSONB NOT NULL,         -- never edited
  raw_text     TEXT
);
```

### 2.4 Structured out: facts with provenance

Nothing reaches `projects` without a traceable origin. A fact knows which document
it came from, which page, the verbatim quote supporting it, and how confident the
extractor was. Corrections supersede rather than overwrite, so the audit trail
survives.

```sql
CREATE TABLE extracted_facts (
  fact_id       BIGSERIAL PRIMARY KEY,
  project_id    TEXT   NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  source_id     BIGINT NOT NULL REFERENCES source_documents(source_id),
  field_path    TEXT   NOT NULL,        -- 'award.winning_gc', 'product.basis_of_design'
  value_text    TEXT,
  value_num     NUMERIC,
  value_date    DATE,
  page_number   INTEGER,                -- the citation manufacturers will click
  char_start    INTEGER,
  char_end      INTEGER,
  quote         TEXT,
  confidence    NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
  extractor     TEXT NOT NULL,          -- model name + version
  extracted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_by BIGINT REFERENCES extracted_facts(fact_id)
);

CREATE INDEX facts_project_field ON extracted_facts (project_id, field_path)
  WHERE superseded_by IS NULL;
```

### 2.5 Stage history

Stage is not a column you overwrite; it is a timeline. This is what makes "how long
does a hospital sit in permitting in Fulton County" answerable.

```sql
CREATE TABLE project_stage_history (
  id          BIGSERIAL PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  stage       project_stage NOT NULL,
  observed_on DATE NOT NULL,
  source_id   BIGINT REFERENCES source_documents(source_id),
  UNIQUE (project_id, stage, observed_on)
);
```

### 2.6 Bid, award, and installed products

This is the reporting tier. It is entirely absent from the current corpus.

```sql
CREATE TABLE bid_packages (
  package_id            BIGSERIAL PRIMARY KEY,
  project_id            TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  csi_division          CHAR(2),        -- '03' concrete, '08' openings, '09' finishes
  scope_label           TEXT NOT NULL,
  bid_due_date          DATE,
  substitution_deadline DATE            -- the date a manufacturer's window shuts
);

CREATE TYPE bid_outcome AS ENUM ('won', 'lost', 'withdrawn', 'unknown');

CREATE TABLE bids (
  bid_id       BIGSERIAL PRIMARY KEY,
  package_id   BIGINT NOT NULL REFERENCES bid_packages(package_id) ON DELETE CASCADE,
  bidder_id    BIGINT NOT NULL REFERENCES companies(company_id),
  amount_usd   BIGINT,
  submitted_on DATE,
  outcome      bid_outcome NOT NULL DEFAULT 'unknown',
  source_id    BIGINT REFERENCES source_documents(source_id)
);

-- One winner per package, enforced rather than assumed.
CREATE UNIQUE INDEX one_winner_per_package
  ON bids (package_id) WHERE outcome = 'won';

-- Distinguishing these four roles is the entire manufacturer value proposition.
CREATE TYPE spec_role AS ENUM (
  'basis_of_design', 'approved_equal', 'substituted_in', 'as_installed'
);

CREATE TABLE installed_products (
  install_id      BIGSERIAL PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  package_id      BIGINT REFERENCES bid_packages(package_id),
  manufacturer_id BIGINT REFERENCES companies(company_id),
  product_name    TEXT,
  csi_division    CHAR(2),
  role            spec_role NOT NULL,
  source_id       BIGINT REFERENCES source_documents(source_id),
  confidence      NUMERIC(4,3)
);

CREATE INDEX installed_by_mfr ON installed_products (manufacturer_id, csi_division);
```

### 2.7 Reporting rollup

```sql
-- Share of spec: what fraction of decided packages in a division went to whom.
CREATE MATERIALIZED VIEW mv_manufacturer_share AS
SELECT
  ip.csi_division,
  p.state,
  c.canonical_name           AS manufacturer,
  count(*)                   AS placements,
  count(*) FILTER (WHERE ip.role = 'basis_of_design') AS as_basis_of_design,
  count(*) FILTER (WHERE ip.role = 'substituted_in')  AS won_by_substitution
FROM installed_products ip
JOIN projects  p ON p.project_id = ip.project_id
JOIN companies c ON c.company_id = ip.manufacturer_id
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX ON mv_manufacturer_share (csi_division, state, manufacturer);
```

---

## 3. Ingestion pipeline

```
public sources
    ↓  fetch, hash, store verbatim            → source_documents (JSONB)
    ↓  LLM extraction against a strict schema → extracted_facts (+ page, quote, confidence)
    ↓  entity resolution (pg_trgm + pgvector) → companies / company_aliases
    ↓  project matching (name + geo + owner)  → projects.project_id
    ↓  promote high-confidence facts          → projects, bids, installed_products
    ↓  refresh rollups                        → mv_manufacturer_share
    ↓  export public snapshot                 → data/national-commercial-projects.json
```

Two rules keep this trustworthy:

1. **A fact below the confidence threshold stays in `extracted_facts` and never
   reaches the promoted tables.** It is visible internally, not to customers.
2. **Any promoted value must be able to render its citation.** If it cannot link to
   a source document, it does not ship. This is what separates the product from a
   scraped list.

---

## 4. Where the money is

The free public index — search by state, county, stage, and category — stays free.
It is built from records anyone can read, so charging for it invites someone to
undercut you by rebuilding it.

The paid tier is the **lifecycle record**, because it cannot be looked up:

- **Who won.** Bid tabs and award notices are public but scattered, and essentially
  never joined back to the original permit or to each other.
- **What went in.** Installed products live in spec books, submittals, and closeout
  documents. Assembling them per project is genuinely hard work.
- **Share of spec over time.** Once the two above exist across enough projects, a
  manufacturer can finally measure what they currently guess at: whether they are
  gaining or losing ground in a division, in a region, against a named competitor.
- **Basis of design versus substitution.** Knowing you won as an approved equal on a
  job where a competitor was the basis of design is a different sales lesson than
  winning outright. Nobody reports this today.

The defensible asset is not the crawler. It is the accumulated, citation-backed
join between projects, awards, and products, which gets more valuable every month
and cannot be bought from a data vendor.

### Honest status

As of this writing the reporting tables above are **designed, not populated.** The
`/reporting/` page measures the gap directly against the live corpus rather than
illustrating it with sample figures, and it reports zero where the answer is zero.
Selling the reporting tier requires closing that gap first.
