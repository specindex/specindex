#!/usr/bin/env python3
"""Email trial users before their 14 days run out.

WHY. Trial expiry is enforced live in require_firebase_user (api/main.py): the
first request after trial_ends_at gets a 403 saying "Your 14-day trial has
ended. Email hello@specindex.ai to reactivate." Correct enforcement, awful
first experience -- someone who spent two weeks hanging call notes on tracked
projects finds out by being locked out of them. Under the specs-plus-CRM moat
the tracked record is precisely what makes an agency stay, so a wall in front
of it with no warning is the worst possible moment to surprise someone, and the
last moment anyone would choose to ask for a card.

IDEMPOTENT BY CONSTRUCTION. Scheduled jobs re-run: retries, overlapping runs,
manual backfills. The SELECT excludes anyone already stamped with
trial_reminder_sent_at, and the stamp is written ONLY after SMTP accepts the
message -- so a failed send is retried tomorrow rather than silently marked
done, and a successful send is never repeated. "Who still needs this" is a fact
in the database, not something this script has to remember between runs.

STAMPED PER USER, NOT PER BATCH. One commit per successful send. A crash
halfway through a batch must not re-mail everyone who was already contacted,
which is exactly what a single commit at the end would do.

SMTP is the same Gmail path /v1/contact already uses -- proven working
(10 of 10 notifications delivered, no errors). Firebase's hosted email handles
password resets only; it cannot send arbitrary mail, so this needs real SMTP.

Usage:
  python3 scripts/send-trial-reminders.py --dry-run
  python3 scripts/send-trial-reminders.py --days-before 3
  python3 scripts/send-trial-reminders.py --days-before 3 --only you@example.com
"""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db  # noqa: E402

SUPPORT = "hello@specindex.ai"


def smtp_credentials() -> tuple[str, str]:
    user = os.environ.get("EMAIL_SMTP_USERNAME", "")
    pwd = os.environ.get("EMAIL_SMTP_PASSWORD", "")
    if not (user and pwd):
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.is_file():
            vals = {}
            for line in env.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip()
            user = user or vals.get("EMAIL_SMTP_USERNAME", "")
            pwd = pwd or vals.get("EMAIL_SMTP_PASSWORD", "")
    return user, pwd


def body_for(name: str | None, days_left: int, tracked: int) -> str:
    who = (name or "").split(" ")[0] or "there"
    when = "tomorrow" if days_left <= 1 else f"in {days_left} days"
    # Lead with what they would LOSE, not with a deadline. The tracked project
    # count is the switching cost made visible -- and it is their own work, so
    # it is the honest reason to keep the account rather than a sales line.
    kept = (f"You're tracking {tracked} project{'s' if tracked != 1 else ''} in your "
            f"pipeline. Those records, and any notes on them, stay exactly as you "
            f"left them.\n\n") if tracked else ""
    return (
        f"Hi {who},\n\n"
        f"Your SpecIndex trial ends {when}.\n\n"
        f"{kept}"
        f"When it ends you'll lose access until the account is reactivated -- "
        f"nothing is deleted.\n\n"
        f"To keep going, or if you just want more time to evaluate, reply to this "
        f"email or write to {SUPPORT} and we'll sort it out.\n\n"
        f"-- SpecIndex\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-before", type=int, default=3,
                    help="remind when this many days or fewer remain (default 3)")
    ap.add_argument("--only", help="restrict to one email address (testing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print who would be mailed; send nothing, stamp nothing")
    args = ap.parse_args()

    conn = db.connect()
    cur = conn.cursor()

    # Deliberately excludes trials that have ALREADY expired: a reminder about a
    # deadline that has passed is worse than none. Expired users get the 403's
    # reactivation message instead.
    params: list = [args.days_before]
    sql = """
        SELECT p.firebase_uid, p.email, p.full_name, p.trial_ends_at,
               GREATEST(0, EXTRACT(DAY FROM (p.trial_ends_at - now()))::int) AS days_left,
               (SELECT count(*) FROM user_tracked_projects t
                 WHERE t.firebase_uid = p.firebase_uid) AS tracked
        FROM user_profiles p
        WHERE p.subscription_tier = 'trial'
          AND p.trial_ends_at IS NOT NULL
          AND p.trial_ends_at > now()
          AND p.trial_ends_at <= now() + (%s || ' days')::interval
          AND p.trial_reminder_sent_at IS NULL
          AND p.email IS NOT NULL
    """
    if args.only:
        sql += " AND p.email = %s"
        params.append(args.only)
    sql += " ORDER BY p.trial_ends_at"
    cur.execute(sql, params)
    due = cur.fetchall()

    print(f"trials ending within {args.days_before} day(s), not yet reminded: {len(due)}")
    if not due:
        print("TRIAL REMINDERS COMPLETE")  # sentinel
        return 0

    user, pwd = smtp_credentials()
    if not args.dry_run and not (user and pwd):
        print("EMAIL_SMTP_USERNAME/PASSWORD not configured -- cannot send",
              file=sys.stderr)
        return 2

    sent = failed = 0
    for uid, email, name, ends, days_left, tracked in due:
        print(f"  {email:<40} ends {ends:%Y-%m-%d}  {days_left}d left  "
              f"tracked={tracked}")
        if args.dry_run:
            continue
        try:
            msg = EmailMessage()
            msg["Subject"] = (f"Your SpecIndex trial ends "
                              f"{'tomorrow' if days_left <= 1 else f'in {days_left} days'}")
            msg["From"] = user
            msg["To"] = email
            msg["Reply-To"] = SUPPORT
            msg.set_content(body_for(name, days_left, tracked))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
                smtp.login(user, pwd)
                smtp.send_message(msg)
        except Exception as e:  # noqa: BLE001 -- one bad address must not end the run
            print(f"    SEND FAILED: {type(e).__name__}: {e}")
            failed += 1
            continue
        # Stamped only after SMTP accepted it, and committed per user so a
        # crash cannot re-mail the people already done.
        cur.execute(
            "UPDATE user_profiles SET trial_reminder_sent_at = now() "
            "WHERE firebase_uid = %s", (uid,))
        conn.commit()
        sent += 1

    print(f"\n=== TRIAL REMINDERS ===")
    print(f"  due    : {len(due)}")
    print(f"  sent   : {sent}")
    print(f"  failed : {failed}  (retried on the next run -- not stamped)")
    if args.dry_run:
        print("  DRY RUN -- nothing sent, nothing stamped")
    print("TRIAL REMINDERS COMPLETE")  # sentinel
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
