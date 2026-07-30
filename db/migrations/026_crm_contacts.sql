-- CRM Phase 1 (docs/PRD_SIGNUP_CRM.md): extend user_profiles with real
-- contact/lifecycle fields, link contact_submissions to a signed-in user
-- when one exists, and merge both into a single crm_contacts view for the
-- /ops/crm admin page to read from.
--
-- Deliberately not a third "crm_contacts" table -- two existing tables plus
-- a view is enough at pre-revenue traffic volume; a real table would mean
-- reconciling dual writes for no benefit yet (see the PRD's Section 2).
--
-- ADD COLUMN IF NOT EXISTS / CREATE OR REPLACE VIEW throughout -- idempotent,
-- safe to re-run.

BEGIN;

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS full_name       TEXT,
  ADD COLUMN IF NOT EXISTS phone           TEXT,
  ADD COLUMN IF NOT EXISTS role_title      TEXT,
  ADD COLUMN IF NOT EXISTS lead_source     TEXT,
  ADD COLUMN IF NOT EXISTS lifecycle_stage TEXT NOT NULL DEFAULT 'signed_up',
  ADD COLUMN IF NOT EXISTS notes           TEXT;

-- lifecycle_stage values (soft-enforced in the API layer, not a DB enum, so
-- adding a stage later doesn't require a migration):
--   signed_up -> onboarded -> demo_requested -> in_conversation
--   -> trialing -> paying -> churned

ALTER TABLE contact_submissions
  ADD COLUMN IF NOT EXISTS firebase_uid TEXT;

-- Merged view: dedupes contact_submissions to its latest row per
-- case/whitespace-normalized email before joining, so a repeat demo-form
-- submission doesn't fan out into duplicate crm_contacts rows and an email
-- typed with different casing still matches. contact_key falls back to a
-- stable hash of the normalized email (not a raw row id) for a contact who
-- only ever submitted the contact form, so it doesn't shift if
-- latest_submission re-picks a different row later.
CREATE OR REPLACE VIEW crm_contacts AS
WITH latest_submission AS (
  SELECT DISTINCT ON (LOWER(TRIM(email)))
    email, first_name, last_name, company, categories, source_path, created_at
  FROM contact_submissions
  ORDER BY LOWER(TRIM(email)), created_at DESC
)
SELECT
  COALESCE(up.firebase_uid, 'anon-' || md5(LOWER(TRIM(cs.email)))) AS contact_key,
  COALESCE(up.full_name, cs.first_name || ' ' || cs.last_name)     AS name,
  COALESCE(up.email, cs.email)                                     AS email,
  COALESCE(up.company, cs.company)                                 AS company,
  up.phone,
  up.role_title,
  up.territory_states,
  COALESCE(up.categories, string_to_array(cs.categories, ','))     AS categories,
  COALESCE(up.lifecycle_stage, 'demo_requested')                   AS lifecycle_stage,
  up.lead_source,
  cs.source_path                                                   AS demo_request_source,
  cs.created_at                                                    AS demo_requested_at,
  up.onboarded_at,
  up.notes
FROM user_profiles up
FULL OUTER JOIN latest_submission cs
  ON LOWER(TRIM(up.email)) = LOWER(TRIM(cs.email));

COMMIT;
