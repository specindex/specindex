#!/usr/bin/env python3
"""Migrate Georgia corpus to data/states/ga.json with state field."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GA = ROOT / "data" / "georgia-commercial-projects.json"
OUT = ROOT / "data" / "states" / "ga.json"


def main() -> None:
    corpus = json.loads(GA.read_text())
    projects = []
    for p in corpus["projects"]:
        p = dict(p)
        p["state"] = "GA"
        if not p["id"].startswith("ga-"):
            p["id"] = f"ga-{p['id']}"
        projects.append(p)

    payload = {
        "state": "GA",
        "state_name": "Georgia",
        "generated_at": corpus.get("generated_at"),
        "date_range": corpus.get("date_range"),
        "capture_method": corpus.get("capture_method"),
        "projects": projects,
        "stats": {"total": len(projects)},
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(projects)} Georgia projects to {OUT}")


if __name__ == "__main__":
    main()
