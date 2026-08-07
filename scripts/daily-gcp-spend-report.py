#!/usr/bin/env python3
"""Daily GCP spend report, emailed to Asif.

BILLING EXPORT ALREADY EXISTED. I claimed it was not enabled and would need
24 hours to populate -- wrong, and I said "as far as I can tell" instead of
checking. specindex-ai.billing_export.gcp_billing_export_v1_* has been
collecting for weeks.

WHY GCP ONLY. Claude Code runs on Asif's Max plan and its usage is not exposed
through any API, so a "consolidated" report would silently show zero for half of
it. This reports the meter that is actually queryable, and says so.

Sent over the same SMTP path as the trial reminders, which is verified working.
"""
from __future__ import annotations
import argparse, datetime as dt, os, smtplib, ssl, sys
from email.message import EmailMessage

PROJECT = "specindex-ai"
TABLE = "specindex-ai.billing_export.gcp_billing_export_v1_01CF1E_0D08DD_275C6A"


def rows(sql: str) -> list[tuple]:
    from google.cloud import bigquery
    return [tuple(r.values()) for r in bigquery.Client(project=PROJECT).query(sql).result()]


def build() -> tuple[str, str]:
    yday = (dt.date.today() - dt.timedelta(days=1)).isoformat()

    daily = rows(f"""
        SELECT DATE(usage_start_time) d, ROUND(SUM(cost),2) usd
          FROM `{TABLE}`
         WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
         GROUP BY d ORDER BY d DESC""")
    by_svc = rows(f"""
        SELECT service.description, ROUND(SUM(cost),2) usd
          FROM `{TABLE}`
         WHERE DATE(usage_start_time) = '{yday}'
         GROUP BY 1 HAVING SUM(cost) > 0 ORDER BY usd DESC LIMIT 10""")
    mtd = rows(f"""
        SELECT ROUND(SUM(cost),2), ROUND(SUM(IFNULL((
                 SELECT SUM(c.amount) FROM UNNEST(credits) c),0)),2)
          FROM `{TABLE}`
         WHERE DATE(usage_start_time) >= DATE_TRUNC(CURRENT_DATE(), MONTH)""")

    gross, credits = (mtd[0] if mtd else (0, 0))
    net = round((gross or 0) + (credits or 0), 2)
    ydays = [d for d in daily if str(d[0]) == yday]
    y_total = ydays[0][1] if ydays else 0
    prev = daily[1][1] if len(daily) > 1 else 0
    delta = round(y_total - prev, 2)

    L = [f"GCP spend — {yday}", "=" * 34, "",
         f"Yesterday          ${y_total:,.2f}",
         f"Day before         ${prev:,.2f}   ({'+' if delta >= 0 else ''}{delta:,.2f})",
         f"Month to date      ${gross:,.2f} gross",
         f"Credits applied    ${credits:,.2f}",
         f"NET month to date  ${net:,.2f}", "",
         "By service, yesterday", "-" * 34]
    L += [f"  {s[:34]:<36}${u:>8,.2f}" for s, u in by_svc] or ["  (no charges)"]
    L += ["", "Last 14 days", "-" * 34]
    L += [f"  {d}   ${u:>8,.2f}" for d, u in daily]
    L += ["", "Claude Code runs on the Max plan and is not billed here;",
          "its usage is not exposed through any API, so this covers GCP only.",
          "", f"Source: {TABLE}"]
    return f"SpecIndex GCP spend {yday} — ${y_total:,.2f}", "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default="asif@specindex.ai")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    subject, body = build()
    if args.dry_run:
        print(f"SUBJECT: {subject}\n\n{body}")
        return 0

    host = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("EMAIL_SMTP_PORT", "465"))
    user = os.environ["EMAIL_SMTP_USERNAME"]
    pwd = os.environ["EMAIL_SMTP_PASSWORD"]
    sender = os.environ.get("EMAIL_FROM", "hello@specindex.ai")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = args.to
    msg.set_content(body)

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, pwd); s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=ctx); s.login(user, pwd); s.send_message(msg)
    print(f"sent to {args.to}: {subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
