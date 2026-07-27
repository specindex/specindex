"""Orchestrate Node 1 (Ingestion Factory) -> Flash -> Sonnet -> persist -> notify.

Generalized from the original NJ-only version to run any state in
core/state_configs.py -- Node 1 now goes through IngestionFactory instead
of a hardcoded Socrata call, so adding a state is a config entry, not new
pipeline code (per the state-agent architecture: only the provider
changes, Nodes 2-4 stay the same).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from .config import STATE_PATH, Settings
from .core.ingestion.factory import build_provider
from .core.state_configs import STATE_CONFIGS
from .model_a_flash import extract_with_flash
from .model_b_sonnet import dedupe_with_sonnet
from .notify import send_run_email
from .persist import golden_to_corpus_projects, merge_into_nj_state, persist_run
from .state import load_state, save_state


def run_pipeline(
    *,
    state_code: str = "NJ",
    lookback_days: int = 30,
    limit: int = 0,
    skip_llm: bool = False,
    merge_state: bool = False,
    dry_run: bool = False,
    notify: bool = False,
) -> dict[str, Any]:
    if state_code not in STATE_CONFIGS:
        raise ValueError(f"No state config for {state_code!r} -- add one to core/state_configs.py")
    state_config = dict(STATE_CONFIGS[state_code])
    # CLI/caller value always wins over a config-level default -- a
    # per-state hardcoded "lookback_days" must never silently shadow an
    # explicit --lookback-days (setdefault() was a real bug here: it
    # never overrides a key state_configs.py already sets).
    state_config["lookback_days"] = lookback_days
    if limit:
        state_config["hard_limit"] = limit
    provider = build_provider(state_config)

    settings = Settings.from_env()
    state_path = STATE_PATH.parent / f"state-{state_code.lower()}.json" if state_code != "NJ" else STATE_PATH
    state = load_state(state_path)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary: dict[str, Any] = {"run_id": run_id, "state_code": state_code, "provider_type": state_config["provider_type"]}

    try:
        rows = provider.fetch_delta(state.last_processed_id)
        if limit:
            rows = rows[:limit]

        if dry_run:
            print(
                f"[dry-run] {state_code}: would process {len(rows)} rows; not calling LLMs or saving watermark",
                file=sys.stderr,
            )
            summary.update({"fetched": len(rows), "dry_run": True})
            if notify:
                summary["notify"] = send_run_email(summary, ok=True)
            return summary

        if skip_llm:
            from .model_a_flash import _deterministic_entities
            from .model_b_sonnet import _passthrough_golden

            entities = _deterministic_entities(rows)
            golden = _passthrough_golden([e.model_dump() for e in entities])
        else:
            entities = extract_with_flash(rows, settings)
            golden = dedupe_with_sonnet(entities, settings)

        paths = persist_run(run_id=run_id, raw_rows=rows, entities=entities, golden=golden)

        # Only advance the watermark after a successful extract+dedupe --
        # a crash mid-run must not lose rows on the next attempt.
        state.last_processed_id = provider.next_watermark(rows, state.last_processed_id)
        state.last_fetched_count = len(rows)
        state.last_extracted_count = len(entities)
        state.last_golden_count = len(golden)
        save_state(state_path, state)

        merged = None
        if merge_state and golden:
            projects = golden_to_corpus_projects(golden)
            merged = merge_into_nj_state(projects) if state_code == "NJ" else None
            if merged is None and merge_state:
                print(
                    f"[persist] --merge-state requested for {state_code} but no corpus merge "
                    "path is wired for non-NJ states yet -- golden records were written to "
                    "data/pipeline/ only, not merged. Wire this deliberately once NJ's output "
                    "has been reviewed, not as a side effect of adding a new state config.",
                    file=sys.stderr,
                )

        summary.update(
            {
                "fetched": len(rows),
                "extracted": len(entities),
                "golden": len(golden),
                "last_processed_id": state.last_processed_id,
                "last_run_timestamp": state.last_run_timestamp,
                "paths": paths,
                "sonnet_backend": settings.sonnet_backend,
                "flash_model": settings.flash_model,
                "merged": merged,
            }
        )
        print(json_summary(summary), file=sys.stderr)
        if notify:
            summary["notify"] = send_run_email(summary, ok=True)
        return summary
    except Exception as e:
        summary.update(
            {
                "fetched": summary.get("fetched"),
                "extracted": summary.get("extracted"),
                "golden": summary.get("golden"),
                "last_processed_id": state.last_processed_id,
                "flash_model": settings.flash_model,
                "sonnet_backend": settings.sonnet_backend,
            }
        )
        if notify:
            summary["notify"] = send_run_email(summary, ok=False, error=str(e))
        raise


def json_summary(summary: dict[str, Any]) -> str:
    import json

    return json.dumps({k: v for k, v in summary.items() if k != "paths"}, indent=2)
