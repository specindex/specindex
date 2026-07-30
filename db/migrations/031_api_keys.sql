-- API-key auth foundation (docs/architecture-2026/04-productization.md
-- Section 2/Phase 0) -- the shared prerequisite for both MCP access and
-- Enterprise billing. Not yet wired into any endpoint; this migration
-- and require_api_key() in api/main.py are the primitive other work
-- builds on, not a finished feature.
--
-- Keys are stored hashed (sha256), never in plaintext -- the raw key is
-- shown to the customer exactly once at creation time and is not
-- recoverable from the database afterward, same discipline as any real
-- API-key system (Stripe, GitHub PATs, etc).
--
-- Scoped to firebase_uid (an individual account) for v1, not an org --
-- the org/seat model doesn't exist yet either (see
-- docs/architecture-2026/02-identity-portals.md's org_id seam). Add an
-- org_id column here later without a breaking migration once that lands.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS api_keys (
  id            BIGSERIAL PRIMARY KEY,
  firebase_uid  TEXT NOT NULL,
  key_hash      TEXT NOT NULL UNIQUE,
  key_prefix    TEXT NOT NULL,   -- first 8 chars, shown in UI so a customer can identify a key without re-seeing the secret
  name          TEXT NOT NULL,   -- customer-chosen label, e.g. "Production MCP server"
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at  TIMESTAMPTZ,
  revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS api_keys_firebase_uid ON api_keys (firebase_uid);

CREATE TABLE IF NOT EXISTS api_key_usage (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  api_key_id    BIGINT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
  endpoint      TEXT NOT NULL,
  called_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_key_usage_key_id ON api_key_usage (api_key_id, called_at);

COMMIT;
