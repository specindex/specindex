#!/usr/bin/env python3
"""Email alert when a GitHub Actions workflow fails -- built specifically
because the production Firebase deploy silently failed for 2.5 days
(2026-07-27 through 2026-07-29) with nobody noticing until it was
investigated by hand. Add as a final `if: failure()` step to any workflow
where silent failure is unacceptable (deploy, DB migrations, etc).

Reuses the same Gmail SMTP credentials already configured for
scripts/state_agent_pipeline/notify.py and api/main.py's contact-form
notifications -- one set of email secrets, not a new one per workflow.

Usage (as a GitHub Actions step):
    - name: Notify on failure
      if: failure()
      run: python3 scripts/notify-workflow-failure.py
      env:
        EMAIL_SMTP_USERNAME: ${{ secrets.EMAIL_SMTP_USERNAME }}
        EMAIL_SMTP_PASSWORD: ${{ secrets.EMAIL_SMTP_PASSWORD }}
        WORKFLOW_NAME: ${{ github.workflow }}
        RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        COMMIT_SHA: ${{ github.sha }}
        NOTIFY_TO: asif@specindex.ai
"""

from __future__ import annotations

import os
import smtplib
import sys
from email.mime.text import MIMEText


def main() -> int:
    user = os.environ.get("EMAIL_SMTP_USERNAME", "")
    password = os.environ.get("EMAIL_SMTP_PASSWORD", "")
    to_addr = os.environ.get("NOTIFY_TO") or "asif@specindex.ai"
    workflow_name = os.environ.get("WORKFLOW_NAME", "unknown workflow")
    run_url = os.environ.get("RUN_URL", "")
    commit_sha = os.environ.get("COMMIT_SHA", "")[:12]

    if not user or not password:
        print("EMAIL_SMTP_USERNAME/PASSWORD not configured; skipping failure email", file=sys.stderr)
        return 0  # don't fail the failure-notification step itself over a missing secret

    subject = f"[SpecIndex] {workflow_name} FAILED"
    body = (
        f"Workflow: {workflow_name}\n"
        f"Commit: {commit_sha}\n"
        f"Run: {run_url}\n\n"
        "This ran as an `if: failure()` step -- something upstream in this workflow "
        "just failed. Check the run link above for the actual error."
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        print(f"Sent failure alert to {to_addr}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 -- best-effort notification, never block on this
        print(f"Failed to send failure alert: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
