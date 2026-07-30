"""Shared LLM daily/monthly spend circuit breaker (docs/architecture-2026/
01-data-platform.md P2). Reads llm_call_log (migration 029) -- every
grounded/ungrounded call from enrich-project-details.py and the NJ Flash/
Sonnet pipeline already writes a row there with a real estimated_cost_usd,
so this only works because that instrumentation already exists; it isn't
re-deriving cost from scratch.

Checked BEFORE a call, not after -- a circuit breaker that trips once the
money's already spent isn't a circuit breaker, it's a report.
"""

from __future__ import annotations

import os

DAILY_CAP_USD = float(os.environ.get("LLM_DAILY_BUDGET_USD", "50"))
MONTHLY_CAP_USD = float(os.environ.get("LLM_MONTHLY_BUDGET_USD", "1000"))


class BudgetExceeded(RuntimeError):
    pass


def check_budget(conn) -> None:
    """Raises BudgetExceeded if today's or this calendar month's
    llm_call_log spend is already at/over the configured cap. conn is any
    open psycopg2 connection -- no transaction state assumed or left
    behind (autocommit-neutral SELECT only)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(sum(estimated_cost_usd), 0) FROM llm_call_log "
            "WHERE called_at > now() - interval '1 day'"
        )
        daily = float(cur.fetchone()[0])
        cur.execute(
            "SELECT COALESCE(sum(estimated_cost_usd), 0) FROM llm_call_log "
            "WHERE called_at > date_trunc('month', now())"
        )
        monthly = float(cur.fetchone()[0])

    if daily >= DAILY_CAP_USD:
        raise BudgetExceeded(f"Daily LLM spend cap hit: ${daily:.2f} >= ${DAILY_CAP_USD:.2f}")
    if monthly >= MONTHLY_CAP_USD:
        raise BudgetExceeded(f"Monthly LLM spend cap hit: ${monthly:.2f} >= ${MONTHLY_CAP_USD:.2f}")
