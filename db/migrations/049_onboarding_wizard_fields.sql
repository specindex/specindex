-- Two new user_profiles columns for the onboarding wizard redesign
-- (docs artifact reviewed by Gemini 2026-07-30):
--
-- territory_refinement: optional free text (counties/metros/zips) below
-- the state multi-select -- Gemini-flagged real gap, a rep's actual
-- territory is often sub-state.
--
-- inferred_lead_source: the pathname-based guess AuthSync already computed
-- automatically, kept as a secondary signal now that lead_source itself
-- becomes an explicit wizard-step answer (Gemini: combine both rather
-- than replacing one with the other).
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS territory_refinement TEXT,
  ADD COLUMN IF NOT EXISTS inferred_lead_source TEXT;

COMMIT;
