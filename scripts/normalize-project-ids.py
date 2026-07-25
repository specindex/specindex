#!/usr/bin/env python3
"""Normalize project IDs and remove duplicates across all state JSON files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATES_DIR = ROOT / "data" / "states"

sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import dedupe_projects  # noqa: E402


def main() -> int:
    if not STATES_DIR.exists():
        print(f"Missing {STATES_DIR}", file=sys.stderr)
        return 1

    total_before = 0
    total_after = 0
    total_merges = 0

    for path in sorted(STATES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        projects = data.get("projects") or []
        before = len(projects)
        deduped, merges = dedupe_projects(projects, path.stem.upper())
        after = len(deduped)

        # Verify uniqueness
        ids = [p["id"] for p in deduped]
        if len(ids) != len(set(ids)):
            print(f"ERROR: duplicate ids remain in {path.name}", file=sys.stderr)
            return 1

        data["projects"] = deduped
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

        total_before += before
        total_after += after
        total_merges += merges
        if merges or before != after:
            print(f"{path.name}: {before} → {after} ({merges} merges)")

    print(
        f"\nTotal: {total_before} → {total_after} projects, "
        f"{total_merges} duplicate merges across all states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
