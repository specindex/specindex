"""Persist raw / extracted / golden outputs and optional state corpus merge."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .config import GOLDEN_DIR, RAW_DIR, EXTRACTED_DIR, PIPELINE_DIR, ROOT
from .schemas import CandidateEntity, GoldenRecord


def _dirs_for_state(state_code: str) -> tuple[Path, Path, Path]:
    """NJ keeps the legacy data/pipeline/nj-dca/ layout (existing consumers
    already point at it); every other state gets its own
    data/pipeline/{state}/ directory. Real bug found 2026-07-28: these were
    hardcoded to the NJ path regardless of state, so NC's run was writing
    (and the daily-commit race then conflicting on) NJ's own
    golden/latest.json -- exactly the kind of collision the per-state
    watermark file (state.py) already avoided, just missed here."""
    if state_code.upper() == "NJ":
        return RAW_DIR, EXTRACTED_DIR, GOLDEN_DIR
    base = PIPELINE_DIR.parent / state_code.lower()
    return base / "raw", base / "extracted", base / "golden"


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path


def persist_run(
    *,
    run_id: str,
    raw_rows: list[dict[str, Any]],
    entities: list[CandidateEntity],
    golden: list[GoldenRecord],
    state_code: str = "NJ",
) -> dict[str, str]:
    raw_dir, extracted_dir, golden_dir = _dirs_for_state(state_code)
    for d in (raw_dir, extracted_dir, golden_dir):
        d.mkdir(parents=True, exist_ok=True)
    paths = {
        "raw": str(write_json(raw_dir / f"{run_id}.json", {"run_id": run_id, "rows": raw_rows})),
        "extracted": str(
            write_json(
                extracted_dir / f"{run_id}.json",
                {"run_id": run_id, "entities": [e.model_dump() for e in entities]},
            )
        ),
        "golden": str(
            write_json(
                golden_dir / f"{run_id}.json",
                {"run_id": run_id, "records": [g.model_dump() for g in golden]},
            )
        ),
    }
    # Latest pointers for the UI / cron consumers
    write_json(golden_dir / "latest.json", {"run_id": run_id, "records": [g.model_dump() for g in golden]})
    return paths


def golden_to_corpus_projects(golden: list[GoldenRecord]) -> list[dict[str, Any]]:
    """Map golden records into SpecIndex project-shaped dicts for optional merge."""
    projects: list[dict[str, Any]] = []
    for g in golden:
        pid = g.golden_id if g.golden_id.startswith("nj-") else f"nj-dca-{g.golden_id}"
        projects.append(
            {
                "id": pid[:80],
                "name": (g.project_name or f"Permit {', '.join(g.permit_numbers) or g.source_pks[0]}")[:120],
                "city": g.municipality or "",
                "county": g.county or "",
                "status": "permitting",
                "project_type": _ptype(g.use_group or ""),
                "estimated_value_usd": g.construction_cost_usd,
                "square_footage": g.square_feet,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": g.earliest_permit_date,
                "description": g.merge_reason or "NJ DCA commercial permit golden record.",
                "key_specs": [s for s in [g.use_group, *g.permit_types, f"Block {g.block} Lot {g.lot}" if g.block else None] if s],
                "mentioned_brands": [],
                "competitor_watch": [],
                "sources": [
                    {
                        "title": "NJ DCA construction permit data",
                        "url": "https://data.nj.gov/Reference-Data/NJ-Construction-Permit-Data/w9se-dmra",
                    }
                ],
                "open_for": "Active commercial building permit. Early product/spec window.",
                "state": "NJ",
                "latitude": None,
                "longitude": None,
            }
        )
    return projects


def _ptype(use_group: str) -> str:
    t = use_group.lower()
    if "factory" in t or "industrial" in t or "storage" in t:
        return "industrial"
    if "hotel" in t:
        return "hospitality"
    if "business" in t:
        return "office"
    if "mercantile" in t:
        return "retail"
    if "restaurant" in t:
        return "hospitality"
    if "educational" in t:
        return "education"
    if "institutional" in t:
        return "civic"
    return "other"


def merge_into_state(state_code: str, projects: list[dict[str, Any]]) -> tuple[int, int]:
    """Generic per-state merge, id-exact-match only (same as every
    existing pull-*.py script's merge_into_state()) -- semantic/fuzzy
    cross-source dedup happens later, at merge-national-corpus.py time,
    not here."""
    path = ROOT / "data" / "states" / f"{state_code.lower()}.json"
    data = json.loads(path.read_text()) if path.exists() else {
        "state": state_code.upper(),
        "generated_at": date.today().isoformat(),
        "projects": [],
        "stats": {},
    }
    existing = data.get("projects") or []
    ids = {p["id"] for p in existing}
    added = 0
    for p in projects:
        if p["id"] in ids:
            continue
        existing.append(p)
        ids.add(p["id"])
        added += 1
    data["projects"] = existing
    data["stats"] = {**(data.get("stats") or {}), "total": len(existing)}
    data["generated_at"] = date.today().isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"[persist] merged into {state_code.lower()}.json +{added} (total {len(existing)})", file=sys.stderr)
    return added, len(existing)


def merge_into_nj_state(projects: list[dict[str, Any]]) -> tuple[int, int]:
    return merge_into_state("NJ", projects)
