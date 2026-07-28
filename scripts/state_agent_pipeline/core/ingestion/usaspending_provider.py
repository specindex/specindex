"""USAspending.gov ingestion provider.

Unlike SAM.gov's bulk-CSV-filtered-client-side approach, USAspending's
spending_by_award search endpoint genuinely supports server-side
per-state filtering (place_of_performance_locations), no API key or
quota. Ported from scripts/pull-usaspending-ga.py (verified live
2026-07-25 -- top GA construction awards in the last 2 years include a
$491M CDC lab and a $195M Navy facility expansion) into the
BaseIngestionProvider interface.

Watermark is a date string (award Start Date), not a monotonic id --
USAspending has no incrementing key. First run and every incremental
run both filter by a start_date lower bound; the only difference is
what that bound is (lookback_days vs. the last watermark, with a small
overlap buffer since awards can be back-dated after posting).

No Flash/Sonnet involvement, same reasoning as sam_gov_provider.py --
this is clean structured award data, to_projects() below is the
existing verified deterministic mapping, ported as-is.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields

API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DEFAULT_AWARD_TYPE_CODES = ["A", "B", "C", "D"]

FIELDS = [
    "Award ID",
    "Recipient Name",
    "Award Amount",
    "Description",
    "Start Date",
    "End Date",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Place of Performance State Code",
    "Place of Performance City",
    "Place of Performance County Name",
    "Place of Performance Zip5",
]

PROJECT_TYPE_KEYWORDS = [
    ("data_center", ("data center", "data centre")),
    ("healthcare", ("hospital", "medical", "clinic", "laboratory", "lab ")),
    ("aviation", ("hangar", "airfield", "runway", "aviation")),
    ("housing", ("barracks", "housing", "dormitory", "quarters")),
    ("industrial", ("warehouse", "distribution", "industrial", "manufacturing plant")),
    ("office", ("office building", "headquarters", "admin building")),
]

COMPETITOR_WATCH_DEFAULT = {
    "data_center": ["hvac", "switchgear", "fire suppression", "generators", "raised flooring"],
    "healthcare": ["hvac", "medical gas", "elevators", "flooring", "lighting", "fire suppression"],
    "aviation": ["roofing", "hvac", "doors and hardware", "concrete", "lighting"],
    "housing": ["hvac", "roofing", "plumbing fixtures", "flooring", "lighting"],
    "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression"],
    "office": ["glazing", "hvac", "elevators", "lighting", "flooring", "fire suppression"],
}

# Awards can be back-dated (posted after their nominal Start Date), so an
# incremental run re-checks a small window before the last watermark
# instead of trusting Start Date to be strictly monotonic with post time.
OVERLAP_DAYS = 5


def _project_type_from(text: str) -> str:
    t = text.lower()
    for ptype, keywords in PROJECT_TYPE_KEYWORDS:
        if any(kw in t for kw in keywords):
            return ptype
    return "commercial"


def _status_from_dates(start: str | None, end: str | None, today: dt.date) -> str:
    start_d = dt.date.fromisoformat(start) if start else None
    end_d = dt.date.fromisoformat(end) if end else None
    if start_d and start_d > today:
        return "planning"
    if end_d and end_d < today:
        return "completed"
    return "under_construction"


class USASpendingProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        state_code: str,
        psc_codes: list[str] | None = None,
        award_type_codes: list[str] | None = None,
        lookback_days: int = 730,
        page_size: int = 100,
        max_retries: int = 4,
        delay: float = 0.3,
    ) -> None:
        self.state_code = state_code.upper()
        self.psc_codes = psc_codes or ["Y"]
        self.award_type_codes = award_type_codes or DEFAULT_AWARD_TYPE_CODES
        self.lookback_days = lookback_days
        self.page_size = page_size
        self.max_retries = max_retries
        self.delay = delay

    def _api_post(self, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    API_URL, data=data, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")
                raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from None
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"USAspending POST failed after {self.max_retries} retries: {last_exc}")

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        today = dt.date.today()
        # State.last_processed_id defaults to "0" (the integer-watermark
        # providers' convention) -- not a valid date, treat same as "no
        # watermark yet" for this date-based provider.
        last_watermark = "" if last_watermark in (None, "", "0") else last_watermark
        if last_watermark:
            start_date = dt.date.fromisoformat(last_watermark) - dt.timedelta(days=OVERLAP_DAYS)
        else:
            start_date = today - dt.timedelta(days=self.lookback_days)

        awards: dict[str, dict] = {}
        page = 1
        while True:
            payload = {
                "filters": {
                    "time_period": [{"start_date": start_date.isoformat(), "end_date": today.isoformat()}],
                    "place_of_performance_locations": [{"country": "USA", "state": self.state_code}],
                    "award_type_codes": self.award_type_codes,
                    "psc_codes": {"require": [["Product", c] for c in self.psc_codes]},
                },
                "fields": FIELDS,
                "page": page,
                "limit": self.page_size,
                "sort": "Award Amount",
                "order": "desc",
            }
            try:
                data = self._api_post(payload)
            except RuntimeError as exc:
                print(f"[usaspending:{self.state_code}] STOPPED on page {page}: {exc}", file=sys.stderr)
                break

            batch = data.get("results", [])
            for award in batch:
                key = award.get("generated_internal_id") or award.get("Award ID") or str(award.get("internal_id"))
                awards[key] = award

            has_next = (data.get("page_metadata") or {}).get("hasNext", False)
            if not batch or not has_next:
                break
            page += 1
            time.sleep(self.delay)

        rows = [a for a in awards.values() if (a.get("Award Amount") or 0) > 0]
        print(f"[usaspending:{self.state_code}] {len(rows)} awards since {start_date.isoformat()}", file=sys.stderr)
        return rows

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        return hash_fields(row, ["Award ID"])

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        current = "" if current in (None, "", "0") else current
        starts = [r.get("Start Date") for r in rows if r.get("Start Date")]
        if not starts:
            return current
        best = max(starts)
        return max(current, best) if current else best

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deterministic mapping to SpecIndex project dicts -- ported
        as-is from pull-usaspending-ga.py's to_project()."""
        from project_identity import slugify

        today = dt.date.today()
        out = []
        for award in rows:
            award_id = award.get("Award ID") or str(award.get("internal_id", "unknown"))
            description = (award.get("Description") or "Untitled award").strip()
            name = description.title()[:120]
            recipient = (award.get("Recipient Name") or "").strip()
            agency = (award.get("Awarding Agency") or "").strip()
            sub_agency = (award.get("Awarding Sub Agency") or "").strip()
            zip5 = (award.get("Place of Performance Zip5") or "").strip()
            city = (award.get("Place of Performance City") or "").strip()
            county = (award.get("Place of Performance County Name") or "").strip()
            amount = award.get("Award Amount")
            start = award.get("Start Date")
            end = award.get("End Date")

            ptype = _project_type_from(description)
            generated_id = award.get("generated_internal_id", "")

            key_specs = [f"Award {award_id}", f"Awarding agency: {sub_agency or agency}"]
            if zip5:
                key_specs.append(f"ZIP {zip5}")

            desc_parts = [description]
            if sub_agency and sub_agency != agency:
                desc_parts.append(f"Awarded by {sub_agency} ({agency})")
            elif agency:
                desc_parts.append(f"Awarded by {agency}")
            if end:
                desc_parts.append(f"Period of performance through {end}")
            full_description = ". ".join(p.rstrip(".") for p in desc_parts if p) + "."

            status = _status_from_dates(start, end, today)
            open_for = {
                "planning": (
                    "Awarded federal construction contract, not yet started. Design/construction-documents "
                    "phase is likely still open for product substitution requests."
                ),
                "under_construction": (
                    "Awarded federal construction contract, in progress. Construction-documents phase may "
                    "still be open for product substitution requests."
                ),
                "completed": (
                    "Completed federal contract (period of performance has ended). Not an active spec "
                    "window -- useful for GC/agency relationship history and competitor-win tracking only."
                ),
            }[status]

            out.append(
                {
                    "id": f"{self.state_code.lower()}-usaspending-{slugify(award_id)[:40]}",
                    "name": name,
                    "city": city,
                    "county": county,
                    "status": status,
                    "project_type": ptype,
                    "estimated_value_usd": amount,
                    "square_footage": None,
                    "owner": agency,
                    "architect": "",
                    "general_contractor": recipient,
                    "opened_or_announced_date": start,
                    "description": full_description[:900],
                    "key_specs": key_specs,
                    "mentioned_brands": [],
                    "competitor_watch": COMPETITOR_WATCH_DEFAULT.get(
                        ptype, ["hvac", "roofing", "lighting", "concrete"]
                    ),
                    "sources": [
                        {
                            "title": f"USAspending.gov award {award_id}: {name[:80]}",
                            "url": f"https://www.usaspending.gov/award/{generated_id}" if generated_id else "https://www.usaspending.gov",
                        }
                    ],
                    "open_for": open_for,
                    "state": self.state_code,
                    "zip": zip5,
                }
            )
        return out
