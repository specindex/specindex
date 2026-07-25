#!/usr/bin/env python3
"""Merge per-state project JSON files into a national corpus."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import dedupe_projects, ensure_state_prefixed  # noqa: E402

STATES_DIR = ROOT / "data" / "states"
OUT = ROOT / "data" / "national-commercial-projects.json"
PUBLIC = ROOT / "public" / "data" / "national-commercial-projects.json"

CUTOFF_DAYS = 90


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "project"


def normalize_project(p: dict, state_code: str) -> dict:
    return ensure_state_prefixed(p, state_code)


def load_state_file(path: Path) -> tuple[str, list[dict]]:
    data = json.loads(path.read_text())
    code = path.stem.upper()
    projects = data.get("projects") if isinstance(data, dict) else data
    if not isinstance(projects, list):
        return code, []
    return code, [normalize_project(p, code) for p in projects]


def main() -> None:
    if not STATES_DIR.exists():
        raise SystemExit(f"Missing {STATES_DIR}")

    all_projects: list[dict] = []
    states_covered: list[str] = []
    seen_ids: set[str] = set()

    for path in sorted(STATES_DIR.glob("*.json")):
        code, projects = load_state_file(path)
        if not projects:
            continue
        projects, _ = dedupe_projects(projects, code)
        states_covered.append(code)
        for p in projects:
            if p["id"] in seen_ids:
                continue
            seen_ids.add(p["id"])
            all_projects.append(p)

    all_projects.sort(
        key=lambda p: (p.get("opened_or_announced_date") or "0000", p.get("name", "")),
        reverse=True,
    )

    cutoff = (date.today() - timedelta(days=CUTOFF_DAYS)).isoformat()
    recent = [
        p for p in all_projects
        if (p.get("opened_or_announced_date") or "") >= cutoff
    ]

    payload = {
        "generated_at": date.today().isoformat(),
        "geography": "United States",
        "capture_method": (
            "Multi-jurisdiction web research: state economic development releases, "
            "permit filings, REBusinessOnline, BLDUP, city and county announcements"
        ),
        "date_range": f"{cutoff} to {date.today().isoformat()} (last {CUTOFF_DAYS} days)",
        "states_covered": sorted(states_covered),
        "projects": all_projects,
        "stats": {
            "total": len(all_projects),
            "opened_last_90_days": len(recent),
            "states": len(states_covered),
        },
        "notes": (
            f"{len(all_projects)} commercial projects across {len(states_covered)} states, "
            f"{len(recent)} of them with activity in the last {CUTOFF_DAYS} days. "
            "Records are built from public permit filings, groundbreakings, and owner or "
            "developer announcements, and every project links back to its sources. "
            "Coverage depth varies by jurisdiction. Not every county publishes permits "
            "as open data, and we are still adding the ones that do."
        ),
    }

    text = json.dumps(payload, indent=2) + "\n"
    OUT.write_text(text)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(text)
    print(
        f"Merged {len(all_projects)} projects from {len(states_covered)} states "
        f"({len(recent)} in last {CUTOFF_DAYS} days) → {OUT}"
    )


if __name__ == "__main__":
    main()
