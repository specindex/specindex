"""Local run-state for incremental Socrata pulls (recordid watermark)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunState:
    """Incremental watermark for NJ DCA w9se-dmra.

    Socrata composite key is treasurycode + recordid. We advance on the highest
    numeric recordid successfully processed so subsequent runs never full-pull.
    """

    last_processed_id: str = "0"
    last_run_timestamp: str | None = None
    last_composite_key: str | None = None  # treasurycode:recordid
    last_fetched_count: int = 0
    last_extracted_count: int = 0
    last_golden_count: int = 0
    # Optional secondary fields kept for debugging / migration
    last_processdate: str | None = None
    seen_pks: list[str] = field(default_factory=list)
    notes: str = (
        "Watermark is recordid (ASC). First run with last_processed_id=0 uses "
        "lookback-days on processdate instead of pulling the entire dataset."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_processed_id": self.last_processed_id,
            "last_run_timestamp": self.last_run_timestamp,
            "last_composite_key": self.last_composite_key,
            "last_fetched_count": self.last_fetched_count,
            "last_extracted_count": self.last_extracted_count,
            "last_golden_count": self.last_golden_count,
            "last_processdate": self.last_processdate,
            "seen_pks": self.seen_pks[-5000:],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RunState":
        if not data:
            return cls()
        # Migrate older processdate-only state files
        last_id = data.get("last_processed_id")
        if last_id is None or last_id == "":
            last_id = "0"
        return cls(
            last_processed_id=str(last_id),
            last_run_timestamp=data.get("last_run_timestamp") or data.get("last_run_at"),
            last_composite_key=data.get("last_composite_key"),
            last_fetched_count=int(data.get("last_fetched_count") or 0),
            last_extracted_count=int(data.get("last_extracted_count") or 0),
            last_golden_count=int(data.get("last_golden_count") or 0),
            last_processdate=data.get("last_processdate"),
            seen_pks=list(data.get("seen_pks") or [])[-5000:],
            notes=data.get("notes") or cls().notes,
        )


def load_state(path: Path) -> RunState:
    if not path.exists():
        return RunState()
    return RunState.from_dict(json.loads(path.read_text()))


def save_state(path: Path, state: RunState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state.last_run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    state.seen_pks = list(dict.fromkeys(state.seen_pks))[-5000:]
    path.write_text(json.dumps(state.to_dict(), indent=2) + "\n")
