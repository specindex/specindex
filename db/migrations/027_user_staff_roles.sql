-- Authorization foundation (docs/architecture-2026/02-identity-portals.md).
-- Two separate structures, not one mixed table -- a Gemini review of the
-- original single-user_roles-table design flagged that internal staff
-- grants (rare, manually granted) and customer subscription tier
-- (frequent, will be Stripe-webhook-driven) are different lifecycles, and
-- mixing them means every tier-check query wades through staff rows too.
--
-- user_staff_roles: internal team only (support_admin/super_admin/
-- pipeline_ops). subscription_tier/is_active: columns directly on
-- user_profiles, since every signed-in user has exactly one tier at a
-- time (no multi-tier case the way multi-staff-role is a real case).
--
-- is_active exists to close a real security gap: Firebase ID tokens
-- self-expire in ~1hr and the client SDK silently refreshes them, so a
-- Postgres-only role check (require_role) does nothing for a deactivated
-- user's still-valid token on endpoints that only call
-- require_firebase_user. Checking is_active inside require_firebase_user
-- itself (see api/main.py) makes deactivation take effect on the very
-- next request instead of up to an hour later.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS user_staff_roles (
  id            BIGSERIAL PRIMARY KEY,
  firebase_uid  TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('support_admin', 'super_admin', 'pipeline_ops')),
  granted_by    TEXT NOT NULL,
  granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (firebase_uid, role)
);

CREATE INDEX IF NOT EXISTS user_staff_roles_firebase_uid ON user_staff_roles (firebase_uid);

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS subscription_tier TEXT NOT NULL DEFAULT 'free'
    CHECK (subscription_tier IN ('free', 'trial', 'pro', 'team')),
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;

COMMIT;
