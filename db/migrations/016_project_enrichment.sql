-- Per-fact enrichment data (executive brief, CSI scope, construction team,
-- permits, contacts) populated by scripts/enrich-project-details.py via a
-- Gemini search-grounded pass plus an independent cross-check pass on the
-- highest-stakes fields (team/contacts/permits) -- the same two-pass
-- methodology used manually to build the ProjectDetailLight page design
-- (2026-07-29): a fact both passes agree on is 'confirmed', a fact the
-- passes disagree on is 'reported' (shown to the user, never silently
-- resolved), and a fact neither pass could find is 'unconfirmed'.
--
-- One row per fact rather than a JSONB blob per project, matching the
-- existing project_sources/project_news pattern -- so "how confident are
-- we in this specific claim" stays a queryable, individually-updatable
-- fact instead of buried inside an opaque document.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_enrichment (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk    BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  section       TEXT NOT NULL,   -- 'executive_brief' | 'csi_scope' | 'team' | 'permit' | 'contact'
  field_key     TEXT NOT NULL,   -- stable slug within a section, e.g. 'div_03', 'general_contractor'
  field_label   TEXT NOT NULL,   -- human display label, e.g. 'Div 03 — Concrete', 'General Contractor'
  field_value   TEXT NOT NULL,
  confidence    TEXT NOT NULL CHECK (confidence IN ('confirmed', 'reported', 'unconfirmed')),
  sources       TEXT,            -- human-readable citation string, e.g. "Blackridge Research, Apr 15 2026"
  enriched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_sk, section, field_key)
);

CREATE INDEX IF NOT EXISTS project_enrichment_project_sk ON project_enrichment (project_sk);

-- Tracks the last enrichment *attempt* per project, independent of whether
-- it produced any facts -- same cooldown pattern as project_news_checks,
-- so a project that genuinely has nothing findable doesn't get re-queried
-- (and re-billed) every run.
CREATE TABLE IF NOT EXISTS project_enrichment_checks (
  project_sk  BIGINT PRIMARY KEY REFERENCES projects(project_sk) ON DELETE CASCADE,
  checked_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
