#!/usr/bin/env python3
"""Pull Travis County TX (Austin) commercial building permits (Socrata).

Verified live 2026-07-28: datahub.austintexas.gov/resource/3syk-w9eu
(Issued Construction Permits), 14,484 commercial permits
(permit_class_mapped='Commercial') in the last 12 months -- real,
current activity (e.g. a 46,219 SF Behavior Health Hospital new
construction, tenant office build-outs, public school remodels).
Real date field is `issue_date` (singular), not `issued_date` --
ordering/filtering on the wrong name silently 400s.

Usage:
    python3 scripts/pull-tx-travis.py --months 24 --merge
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

DOMAIN = "datahub.austintexas.gov"
DATASET = "3syk-w9eu"

PERMIT_TYPE_KEYWORDS = [
    ("healthcare", ("hospital", "medical", "clinic", "behavior health")),
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
    permit_no = str(row.get("permit_number") or "").strip()
    city = (row.get("original_city") or "Austin").strip().title()
    permit_type = (row.get("permit_type_desc") or "").strip()
    work_class = (row.get("work_class") or "").strip()
    description = (row.get("description") or "").strip()
    date_str = (row.get("issue_date") or "")[:10]
    address = (row.get("original_address1") or "").strip()
    zip_code = (row.get("original_zip") or "").strip()
    link = row.get("link")
    link_url = (link.get("url") if isinstance(link, dict) else link) or (
        f"https://data.texas.gov/dataset/Issued-Construction-Permits/{DATASET}"
    )

    name = f"{work_class or permit_type} - {address}".strip(" -") or f"Travis County permit {permit_no}"

    uid = slugify(f"{city}-{permit_no}")
    return {
        "id": f"tx-travis-{uid}",
        "name": name[:120],
        "city": city,
        "county": "Travis",
        "status": "permitting",
        "project_type": project_type_from(description + " " + permit_type),
        "estimated_value_usd": None,
        "square_footage": None,
        "owner": "",
        "architect": "",
        "general_contractor": "",
        "opened_or_announced_date": date_str or None,
        "description": (description or permit_type or "Travis County commercial building permit.")[:900],
        "key_specs": [p for p in [permit_type, work_class, f"Permit {permit_no}" if permit_no else None] if p],
        "mentioned_brands": [],
        "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression", "doors and hardware"],
        "sources": [{"title": f"Austin/Travis County building permit {permit_no}", "url": link_url}],
        "open_for": "Active commercial building permit. Early product/spec window.",
        "state": "TX",
        "address": address or None,
        "zip": zip_code or None,
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
    where = f"issue_date > '{cutoff.isoformat()}' AND permit_class_mapped = 'Commercial'"
    print(f"[travis] querying {DOMAIN}/{DATASET} where={where}", file=sys.stderr)
    rows = query_socrata(DOMAIN, DATASET, where=where, order="issue_date DESC")
    if args.limit:
        rows = rows[: args.limit]
    print(f"[travis] fetched {len(rows)} commercial rows", file=sys.stderr)

    projects = [to_project(r) for r in rows if r.get("permit_number")]
    projects = assign_unique_ids(projects, "TX")
    print(f"[travis] mapped {len(projects)} projects", file=sys.stderr)

    if args.merge:
        added, total = merge_into_state(projects)
        print(f"[travis] merged +{added} (total {total}) into data/states/tx.json")
    else:
        out = ROOT / "data" / "raw" / "tx-travis-commercial.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        import json

        out.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
        print(f"[travis] wrote {len(projects)} projects to {out} (dry run, not merged)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
