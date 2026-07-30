-- Adds user_profiles.last_login_at (updated by GET /v1/me/profile, called
-- once per sign-in by AuthSync -- not on every request, which would be a
-- write on every single API call for no real benefit). Also exposes
-- is_active and last_login_at through crm_contacts so the admin CRM table
-- can show account status and last-seen date, per a live request while
-- testing the ops UI.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

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
  up.notes,
  up.is_active,
  up.last_login_at
FROM user_profiles up
FULL OUTER JOIN latest_submission cs
  ON LOWER(TRIM(up.email)) = LOWER(TRIM(cs.email));

COMMIT;
