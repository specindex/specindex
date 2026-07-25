#!/usr/bin/env python3
"""Rebuild data/states/ga.json from raw Georgia commercial sources.

Canonical reference: docs/states/ga.md

Sources merged (commercial only):
  - data/georgia-commercial-projects.json (prior research)
  - data/raw/ga-dri-projects.json
  - data/raw/ga-municipal-commercial.json
  - data/raw/ga-accela-commercial.json (when present)

Usage:
    python3 scripts/rebuild-ga-corpus.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import dedupe_projects  # noqa: E402

OUT = ROOT / "data" / "states" / "ga.json"
RESEARCH = ROOT / "data" / "georgia-commercial-projects.json"
DRI = ROOT / "data" / "raw" / "ga-dri-projects.json"
MUNI = ROOT / "data" / "raw" / "ga-municipal-commercial.json"
ACCELA = ROOT / "data" / "raw" / "ga-accela-commercial.json"

NOISE = re.compile(
    r"(seasonal sales|tower co-locate|construction trailer|temp sign|office trailer|"
    r"vegetative recycling|yard waste|compost)",
    re.I,
)
RESIDENTIAL = re.compile(
    r"\b(residential|single[- ]family|townhome|townhouse|subdivision|duplex|triplex|condo|dwelling)\b",
    re.I,
)


def load_projects(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    projects = data.get("projects") if isinstance(data, dict) else data
    return list(projects or [])


def filter_noise(projects: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for p in projects:
        blob = " ".join(
            [
                p.get("name") or "",
                p.get("description") or "",
                p.get("project_type") or "",
            ]
        )
        if NOISE.search(blob):
            continue
        if RESIDENTIAL.search(blob) and p.get("project_type") not in {
            "multifamily",
            "mixed_use",
            "commercial",
            "industrial",
            "office",
            "retail",
        }:
            continue
        if p.get("project_type") in {"housing", "residential", "single_family"}:
            continue
        kept.append(p)
    return kept


def main() -> int:
    research = filter_noise(load_projects(RESEARCH))
    dri = filter_noise(load_projects(DRI))
    muni = filter_noise(load_projects(MUNI))
    accela = filter_noise(load_projects(ACCELA))

    combined = research + dri + muni + accela
    deduped, merges = dedupe_projects(combined, "GA")

    ids = [p["id"] for p in deduped]
    if len(ids) != len(set(ids)):
        print("ERROR: duplicate ids after dedupe", file=sys.stderr)
        return 1

    payload = {
        "state": "GA",
        "generated_at": date.today().isoformat(),
        "date_range": "Last 12 months commercial",
        "capture_method": (
            "Georgia DRI filings, Alpharetta commercial permits, Johns Creek active "
            "developments, Marietta commercial/industrial parcels, Accela commercial "
            "permits (Atlanta, Gwinnett, Cobb), plus prior public research"
        ),
        "projects": deduped,
        "stats": {
            "total": len(deduped),
            "research": len(research),
            "dri_raw": len(dri),
            "municipal_raw": len(muni),
            "accela_raw": len(accela),
            "merges": merges,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print(
        f"Rebuilt {OUT}: {len(deduped)} projects "
        f"(research {len(research)}, dri {len(dri)}, muni {len(muni)}, "
        f"accela {len(accela)}, merges {merges})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
