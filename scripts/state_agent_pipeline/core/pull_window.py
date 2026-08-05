"""The pull window, expressed absolutely.

The standing policy is a FIXED anchor -- pull everything since 2025-01-01, not
a rolling "last N days". But every provider takes `lookback_days`, a relative
integer, so the anchor has had to be recomputed by hand as
`(today - date(2025,1,1)).days` at the start of each session and pasted into
configs and command lines.

That drifts, and it drifted: on 2026-08-04 the config file held `579` on 76
configs and `576` on nine others -- three days adrift, silently pulling a
different window, with no error anywhere to notice. The anchor is a date; a
day-count is a derived value that goes stale the moment the clock rolls over.

So: state the date once, derive the integer at run time.

    from core.pull_window import PULL_ANCHOR, anchor_lookback_days
    lookback = anchor_lookback_days()          # always correct today

Providers are untouched -- they still receive `lookback_days`. This only
removes the manual arithmetic and the stale constants it produced.
"""

from __future__ import annotations

from datetime import date

# Per Asif (2026-07-31): bulk/historical pulls go back to 2025-01-01 -- a fixed
# anchor, not a rolling lookback, and not further back. Change this one line to
# move the window; nothing else should hardcode a day-count.
PULL_ANCHOR = date(2025, 1, 1)


def lookback_days_since(since: str | date, *, today: date | None = None) -> int:
    """Days from `since` to today, as providers' `lookback_days` expects.

    Never returns less than 1: a zero or negative window would make a provider
    fetch nothing at all, which reads as "this source is empty" rather than as
    a bad argument -- the same silent-failure shape that has cost us repeatedly.
    """
    if isinstance(since, str):
        since = date.fromisoformat(since)
    ref = today or date.today()
    return max(1, (ref - since).days)


def anchor_lookback_days(*, today: date | None = None) -> int:
    """`lookback_days` for the standing 2025-01-01 anchor, correct for today."""
    return lookback_days_since(PULL_ANCHOR, today=today)
