#!/usr/bin/env python3
"""CLI entry for NJ DCA incremental pipeline.

Daily cron (preferred): scripts/state_agent_pipeline/run_job.sh
See scripts/state_agent_pipeline/CRON_SETUP.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from state_agent_pipeline.pipeline import run_pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        default="NJ",
        help="State code from core/state_configs.STATE_CONFIGS (default: NJ)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="First-run / empty-state lookback when last_processed_id is 0. "
             "Relative and therefore drifty -- prefer --since-date.",
    )
    parser.add_argument(
        "--since-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Absolute pull-window start. Converted to the equivalent "
             "lookback_days at run time, so every provider keeps working "
             "unchanged. Use PULL_ANCHOR for the standing 2025-01-01 anchor.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Cap rows fetched (0 = no cap)")
    parser.add_argument("--skip-llm", action="store_true", help="Deterministic extract/passthrough only")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only; no LLM, no state write")
    parser.add_argument("--merge-state", action="store_true", help="Merge golden records into data/states/nj.json")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Email asif@specindex.ai (or NJ_DCA_NOTIFY_TO) when the run finishes",
    )
    args = parser.parse_args(argv)

    # An absolute date is the honest way to express the pull window; the
    # relative lookback has to be recomputed every session and silently
    # drifts. Nine configs were found holding 576 while the rest held 579 --
    # three days adrift, pulling a different window with no error anywhere.
    # Converting here keeps every provider's lookback_days contract intact.
    lookback_days = args.lookback_days
    if args.since_date:
        from core.pull_window import lookback_days_since  # noqa: PLC0415

        lookback_days = lookback_days_since(args.since_date)
        print(
            f"[pull-window] --since-date {args.since_date} -> lookback_days={lookback_days}",
            file=sys.stderr,
        )

    summary = run_pipeline(
        state_code=args.state,
        lookback_days=lookback_days,
        limit=args.limit,
        skip_llm=args.skip_llm,
        merge_state=args.merge_state,
        dry_run=args.dry_run,
        notify=args.notify,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
