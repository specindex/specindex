-- docs/architecture-2026/00-MASTER-ROADMAP.md P1 / 01-data-platform.md §7:
-- entity directory tables, seeded by a Phase-1 HEURISTIC normalization
-- batch (scripts/normalize-entity-directories.py) over projects.mentioned_brands,
-- projects.competitor_watch, projects.owner, projects.architect, and
-- projects.general_contractor. "Heuristic" is doing real work in that
-- sentence: this is lowercasing + punctuation-stripping, not fuzzy
-- matching or LLM entity resolution -- those are P3/P4 (pg_trgm
-- merge-proposal batch, then an LLM-assisted resolution pass for the
-- residual). Expect real duplicates under near-identical names until then.
--
-- UNIQUE constraints per Gemini review:
-- - manufacturers/general_contractors scoped (normalized_name, state), not
--   global -- regional companies legitimately share common names across
--   states ("ABC Construction" in GA is not "ABC Construction" in TX).
-- - people uses UNIQUE NULLS NOT DISTINCT (normalized_name, firm_name) --
--   plain UNIQUE treats every NULL firm_name as distinct, which would let
--   the same unaffiliated person get inserted unlimited times.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS manufacturers (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  normalized_name TEXT NOT NULL,
  display_name    TEXT NOT NULL,
  state           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (normalized_name, state)
);

CREATE TABLE IF NOT EXISTS general_contractors (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  normalized_name TEXT NOT NULL,
  display_name    TEXT NOT NULL,
  state           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (normalized_name, state)
);

-- role/firm_name are both nullable and heuristic -- Phase 1 tags a person
-- with whatever field it found them in (owner/architect), not a verified
-- title. firm_name is set when the source string reads as a company
-- rather than an individual (see the normalization script's is_firm_like
-- heuristic); NULL means "person, unaffiliated or firm unknown."
CREATE TABLE IF NOT EXISTS people (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  normalized_name TEXT NOT NULL,
  display_name    TEXT NOT NULL,
  firm_name       TEXT,
  role            TEXT,
  state           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (normalized_name, firm_name)
);

CREATE TABLE IF NOT EXISTS project_manufacturers (
  project_sk      BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  manufacturer_id BIGINT NOT NULL REFERENCES manufacturers(id) ON DELETE CASCADE,
  source_field    TEXT NOT NULL CHECK (source_field IN ('mentioned_brands', 'competitor_watch')),
  PRIMARY KEY (project_sk, manufacturer_id, source_field)
);

CREATE TABLE IF NOT EXISTS project_general_contractors (
  project_sk           BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  general_contractor_id BIGINT NOT NULL REFERENCES general_contractors(id) ON DELETE CASCADE,
  PRIMARY KEY (project_sk, general_contractor_id)
);

CREATE TABLE IF NOT EXISTS project_people (
  project_sk BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  person_id  BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  role       TEXT NOT NULL CHECK (role IN ('owner', 'architect')),
  PRIMARY KEY (project_sk, person_id, role)
);

CREATE INDEX IF NOT EXISTS project_manufacturers_manufacturer ON project_manufacturers (manufacturer_id);
CREATE INDEX IF NOT EXISTS project_general_contractors_gc ON project_general_contractors (general_contractor_id);
CREATE INDEX IF NOT EXISTS project_people_person ON project_people (person_id);

COMMIT;
