-- Pre-expiry trial reminder.
--
-- WHY. Trial expiry is enforced live in require_firebase_user: the moment
-- trial_ends_at passes, the user's next request gets a 403 telling them to
-- email hello@specindex.ai. That is correct enforcement and a terrible first
-- experience -- someone who put 14 days of call notes on tracked projects
-- discovers the deadline by being locked out of them, with no warning and no
-- chance to convert. Under the "specs plus CRM" moat the tracked record is the
-- thing that makes them stay; hitting a wall in front of it is the single worst
-- moment to surprise someone.
--
-- IDEMPOTENCY IS THE WHOLE DESIGN. A reminder job runs on a schedule, and a
-- schedule retries: a re-run, an overlapping run, or a backfill must never mail
-- the same person twice. The timestamp column is the interlock -- the query
-- that selects who to mail excludes anyone already stamped, so "who still needs
-- this" is a fact in the database rather than something the job has to
-- remember. Nullable because the vast majority of rows never need one.
--
-- Separate columns per reminder rather than a count, so adding a second
-- touchpoint later (say a day-before nudge) cannot be confused with the first,
-- and so the send history stays readable when someone asks why a given user
-- did or did not get mailed.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS trial_reminder_sent_at timestamptz;

COMMENT ON COLUMN user_profiles.trial_reminder_sent_at IS
    'When the pre-expiry trial reminder was sent. NULL = not yet sent. Set only '
    'after the SMTP send succeeds, so a failed send is retried on the next run '
    'rather than silently skipped.';

-- The reminder job filters on exactly this shape: trial tier, not yet expired,
-- ending soon, never reminded. Partial index so the daily scan stays cheap as
-- user_profiles grows and never touches the free/pro/team majority.
CREATE INDEX IF NOT EXISTS idx_user_profiles_trial_reminder_due
    ON user_profiles (trial_ends_at)
    WHERE subscription_tier = 'trial' AND trial_reminder_sent_at IS NULL;
