-- Stop two accounts sharing one email address.
--
-- THE BUG. asif@specindex.ai appeared twice in the CRM. /v1/signup treats
-- EMAIL_ALREADY_EXISTS as a normal "log in instead" case and returns success,
-- and the profile insert deduped only ON CONFLICT (firebase_uid) -- so two
-- different UIDs with the same email produced two rows and nothing objected.
--
-- Both observed duplicates are Clerk->Firebase migration residue: a dead
-- `user_*` row that never logged in, plus the real Firebase row. Clerk is gone,
-- so nobody can authenticate as a `user_*` UID -- those rows cannot be anyone's
-- account, only clutter in the CRM.
--
-- They are DEACTIVATED, not deleted. The rule here is relabel over delete: a
-- deactivated row is reversible and still carries whatever history it had,
-- while a deleted one is gone with its created_at and lead_source.
UPDATE user_profiles
   SET is_active = false, updated_at = now()
 WHERE firebase_uid LIKE 'user\_%'
   AND EXISTS (
       SELECT 1 FROM user_profiles u2
        WHERE lower(u2.email) = lower(user_profiles.email)
          AND u2.firebase_uid NOT LIKE 'user\_%'
   );

-- Partial on is_active so historical deactivated rows stay queryable: the
-- invariant that matters is "one LIVE account per address", not "this address
-- was never used".
CREATE UNIQUE INDEX IF NOT EXISTS user_profiles_active_email_uniq
    ON user_profiles (lower(email))
    WHERE is_active;
