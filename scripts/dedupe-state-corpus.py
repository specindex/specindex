#!/usr/bin/env python3
"""Fuzzy-dedupe a state's project list in place using project_identity's
same_project/merge logic (name similarity + shared source URLs), not just
exact-ID matching.

Georgia has its own multi-source rebuild pipeline (rebuild-ga-corpus.py)
that does this as part of combining raw sources. States without that kind
of tiered raw-file setup yet (NC, TX, ...) just get their existing
data/states/{code}.json project list deduped directly.

Usage:
    python3 scripts/dedupe-state-corpus.py NC
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import dedupe_projects  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: dedupe-state-corpus.py <STATE_CODE>", file=sys.stderr)
        return 1
    state = sys.argv[1].upper()
    path = ROOT / "data" / "states" / f"{state.lower()}.json"
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text())
    before = len(data.get("projects") or [])
    deduped, merges = dedupe_projects(data.get("projects") or [], state)
    data["projects"] = deduped
    data["stats"] = {**(data.get("stats") or {}), "total": len(deduped)}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{state}: {before} -> {len(deduped)} projects ({merges} merges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
