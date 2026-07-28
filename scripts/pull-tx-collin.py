#!/usr/bin/env python3
"""Pull Collin County TX commercial building permits (Socrata).

Verified live 2026-07-28: data.texas.gov/resource/82ee-gbj5 (Collin CAD
Building Permits), 5,943 permits in the last 4 months, 2,330 commercial
(proprescom='Commercial') in the last 12 months -- real cities (Plano,
Celina, Prosper), real values (e.g. Plano ISD $200M remodel). Raw
MAX(permitissueddate) returns 2026-12-29, a bad/future outlier -- same
"don't trust raw MAX" lesson as docs/states/nj.md; a small number of rows
do carry genuine future-scheduled dates, clamped out below with an
upper-date bound rather than trusted as-is.

Usage:
    python3 scripts/pull-tx-collin.py --months 24 --merge
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from project_identity import assign_unique_ids, slugify  # noqa: E402
from socrata_adapter import query_socrata  # noqa: E402

DOMAIN = "data.texas.gov"
DATASET = "82ee-gbj5"

PERMIT_TYPE_KEYWORDS = [
    ("healthcare", ("hospital", "medical", "clinic")),
    ("education", ("school", "isd", "campus")),
    ("hospitality", ("hotel", "restaurant")),
    ("retail", ("retail", "store", "shell")),
    ("industrial", ("warehouse", "industrial", "manufacturing")),
]


def project_type_from(text: str) -> str:
    t = (text or "").lower()
    for ptype, keywords in PERMIT_TYPE_KEYWORDS:
        if any(kw in t for kw in keywords):
            return ptype
    return "commercial"


def to_project(row: dict) -> dict:
    permit_id = str(row.get("permitid") or row.get("permitnum") or "").strip()
    owner = (row.get("propownername") or "").strip()
    builder = (row.get("permitbuildername") or "").strip()
    city = (row.get("situscity") or "").strip().title()
    permit_type = (row.get("permittypedescr") or "").strip()
    date_str = (row.get("permitissueddate") or "")[:10]
    try:
        value = float(row.get("permitvalue") or 0)
    except (TypeError, ValueError):
        value = 0.0
    try:
        area = float(row.get("permitbldgarea") or 0)
    except (TypeError, ValueError):
        area = 0.0
    addr_parts = [
        row.get("situsbldgnum", ""),
        row.get("situsstreetname", ""),
        row.get("situsstreetsuffix", ""),
    ]
    address = " ".join(p for p in addr_parts if p).strip()
    name = owner or f"{permit_type or 'Commercial Permit'} - {city}"

    uid = slugify(f"{city}-{permit_id}")
    return {
        "id": f"tx-collin-{uid}",
        "name": name[:120],
        "city": city,
        "county": "Collin",
        "status": "permitting",
        "project_type": project_type_from(permit_type + " " + (row.get("permitcomments") or "")),
        "estimated_value_usd": value if value > 0 else None,
        "square_footage": area if area > 0 else None,
        "owner": owner.title() if owner else "",
        "architect": "",
        "general_contractor": builder.title() if builder else "",
        "opened_or_announced_date": date_str or None,
        "description": (row.get("permitcomments") or permit_type or "Collin County commercial building permit.")[:900],
        "key_specs": [p for p in [permit_type, f"Permit {permit_id}" if permit_id else None] if p],
        "mentioned_brands": [],
        "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression", "doors and hardware"],
        "sources": [
            {
                "title": f"Collin County building permit {permit_id}",
                "url": f"https://data.texas.gov/dataset/Collin-CAD-Building-Permits/{DATASET}",
            }
        ],
        "open_for": "Active commercial building permit. Early product/spec window.",
        "state": "TX",
        "address": address or None,
    }


def merge_into_state(projects: list[dict]) -> tuple[int, int]:
    import json

    path = ROOT / "data" / "states" / "tx.json"
    data = json.loads(path.read_text()) if path.exists() else {
        "state": "TX", "generated_at": dt.date.today().isoformat(), "projects": [], "stats": {},
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
    data["generated_at"] = dt.date.today().isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return added, len(existing)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    today = dt.date.today()
    cutoff = today - dt.timedelta(days=int(args.months * 30.44))
    # Upper-bound the date too -- a handful of rows carry genuine
    # future-scheduled dates (confirmed live 2026-07-28: Dec 2026 permits
    # exist alongside a raw MAX of 2026-12-29), clamp to "not more than a
    # few weeks ahead" rather than trusting the field unbounded.
    upper = today + dt.timedelta(days=30)
    where = (
        f"permitissueddate > '{cutoff.isoformat()}' AND "
        f"permitissueddate < '{upper.isoformat()}' AND "
        "proprescom = 'Commercial'"
    )
    print(f"[collin] querying {DOMAIN}/{DATASET} where={where}", file=sys.stderr)
    rows = query_socrata(DOMAIN, DATASET, where=where, order="permitissueddate DESC")
    if args.limit:
        rows = rows[: args.limit]
    print(f"[collin] fetched {len(rows)} commercial rows", file=sys.stderr)

    projects = [to_project(r) for r in rows if r.get("permitid") or r.get("permitnum")]
    projects = assign_unique_ids(projects, "TX")
    print(f"[collin] mapped {len(projects)} projects", file=sys.stderr)

    if args.merge:
        added, total = merge_into_state(projects)
        print(f"[collin] merged +{added} (total {total}) into data/states/tx.json")
    else:
        out = ROOT / "data" / "raw" / "tx-collin-commercial.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        import json

        out.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
        print(f"[collin] wrote {len(projects)} projects to {out} (dry run, not merged)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
