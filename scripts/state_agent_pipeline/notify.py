"""Email notify after daily NJ DCA cron finishes."""

from __future__ import annotations

import os
import smtplib
import sys
from email.mime.text import MIMEText
from typing import Any


DEFAULT_TO = "asif@specindex.ai"


def send_run_email(summary: dict[str, Any], *, ok: bool, error: str | None = None) -> str:
    """Send a short completion email via Gmail SMTP (same pattern as api/main.py).

    Env:
      EMAIL_SMTP_USERNAME / EMAIL_SMTP_PASSWORD  (required)
      NJ_DCA_NOTIFY_TO  (default asif@specindex.ai)
      NJ_DCA_NOTIFY_FROM (default EMAIL_SMTP_USERNAME)
    """
    user = os.environ.get("EMAIL_SMTP_USERNAME", "")
    password = os.environ.get("EMAIL_SMTP_PASSWORD", "")
    to_addr = os.environ.get("NJ_DCA_NOTIFY_TO") or DEFAULT_TO
    from_addr = os.environ.get("NJ_DCA_NOTIFY_FROM") or user

    if not user or not password:
        msg = "EMAIL_SMTP_USERNAME/PASSWORD not configured; skipped notify email"
        print(f"[notify] {msg}", file=sys.stderr)
        return msg

    status = "OK" if ok else "FAILED"
    run_id = summary.get("run_id") or "?"
    subject = f"[SpecIndex] NJ DCA pipeline {status} ({run_id})"
    body_lines = [
        f"Status: {status}",
        f"Run ID: {run_id}",
        f"Fetched: {summary.get('fetched')}",
        f"Extracted: {summary.get('extracted')}",
        f"Golden records: {summary.get('golden')}",
        f"last_processed_id: {summary.get('last_processed_id') or summary.get('watermark')}",
        f"Flash model: {summary.get('flash_model')}",
        f"Sonnet backend: {summary.get('sonnet_backend')}",
    ]
    if summary.get("merged"):
        body_lines.append(f"Merged into nj.json: {summary.get('merged')}")
    if error:
        body_lines.append("")
        body_lines.append(f"Error: {error}")
    body_lines.append("")
    body_lines.append("Log: data/pipeline/nj-dca/pipeline.log")
    body = "\n".join(body_lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        print(f"[notify] emailed {to_addr}: {subject}", file=sys.stderr)
        return f"sent:{to_addr}"
    except Exception as e:
        print(f"[notify] email failed: {e}", file=sys.stderr)
        return f"error:{e}"
