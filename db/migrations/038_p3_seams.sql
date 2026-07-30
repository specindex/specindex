-- docs/architecture-2026/00-MASTER-ROADMAP.md P3, three independent
-- additive schema changes bundled into one migration:
--
-- 1. entity_aliases: docs/architecture-2026/01-data-platform.md's own
--    P2 action item, a real prerequisite for the P3 fuzzy-matching batch
--    (scripts/find-entity-duplicates.py) -- without it, the NEXT day's
--    ingestion run would re-create a duplicate under the old name every
--    time two entities are merged (Gemini-flagged gap). deprecated_id ->
--    canonical_id, scoped per entity_type since manufacturers/GCs/people
--    are separate tables with separately-sequenced ids.
--
-- 2. user_profiles.stripe_customer_id: nullable forward seam only --
--    schema, not billing. Building an actual billing PAGE (real Stripe
--    Checkout/webhook integration, real payment processing) is a
--    materially different, consequential decision than an idempotent
--    migration and was not built here -- see ROADMAP.md's note on why.
--
-- 3. lead_scores: mirrors project_scores exactly (013_project_scores.sql)
--    -- one row per crm_contacts.contact_key, each formula component in
--    its own column so the breakdown is visible, not just the total,
--    recomputed by scripts/compute-lead-scores.py on a schedule.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS entity_aliases (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_type    TEXT NOT NULL CHECK (entity_type IN ('manufacturer', 'general_contractor', 'person')),
  deprecated_id  BIGINT NOT NULL,
  canonical_id   BIGINT NOT NULL,
  merged_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (entity_type, deprecated_id)
);

CREATE INDEX IF NOT EXISTS entity_aliases_canonical ON entity_aliases (entity_type, canonical_id);

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

CREATE TABLE IF NOT EXISTS lead_scores (
  contact_key           TEXT PRIMARY KEY,
  score                 INTEGER NOT NULL,
  intent_score          INTEGER NOT NULL,
  pipeline_depth_score  INTEGER NOT NULL,
  engagement_score      INTEGER NOT NULL,
  territory_score       INTEGER NOT NULL,
  recency_score         INTEGER NOT NULL,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
