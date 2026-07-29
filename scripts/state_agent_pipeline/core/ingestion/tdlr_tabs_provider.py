"""TDLR TABS (Texas Architectural Barriers project registry) provider.

Under Texas Administrative Code Ch. 68, most commercial construction,
renovation, or alteration projects with an estimated cost >= $50,000
must register with TDLR's Texas Architectural Barriers online System
(TABS) before local permitting. This is a real, live, STATEWIDE source
covering every Texas county in one feed -- found 2026-07-28 chasing a
Gemini-suggested lead (whose specific URL was wrong, but the underlying
"TDLR TABS" pointer was real) while investigating Harris County dead
ends. Verified live: 339,076 total projects on record, 66,749 in Harris
County alone, 353 registered in a real 30-day window.

Confirmed fully stateless -- no cookies, session, or CSRF token needed
at all (unlike every Playwright-based provider this session): a plain
HTTP GET fetches the county code lookup table (parsed from the search
page's <select> dropdown via regex, no HTML-parsing dependency needed),
and a plain HTTP POST to /TABS/Search/SearchProjects (a standard
jQuery DataTables server-side endpoint) returns paginated JSON directly.

Unlike every other provider in this pipeline, this one is not scoped to
a single county via config -- it can pull ALL Texas counties in a
single run (RegistrationCounty omitted from the POST body), with each
row's real county attributed from its own numeric County code, via the
live-fetched lookup table. A specific county can still be requested via
config for narrower/faster runs.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields

SEARCH_PAGE_URL = "https://www.tdlr.texas.gov/TABS/Search"
SEARCH_API_URL = "https://www.tdlr.texas.gov/TABS/Search/SearchProjects"

# Confirmed live 2026-07-28. Only a handful of statuses exist and they
# rarely change; the county table (258 entries) is fetched live every
# run instead, since parsing it costs one extra GET and there's no
# reason to risk it going stale.
PROJECT_STATUS_LABELS = {
    3001: "Inspection Complete",
    3007: "Project Closed",
    3008: "Project Registered",
    3009: "Review Complete",
}

_DATATABLES_FIELDS = [
    "ProjectId", "ProjectNumber", "ProjectName", "ProjectCreatedOn",
    "ProjectStatus", "FacilityName", "City", "County", "TypeOfWork",
    "EstimatedCost", "DataVersionId", "EstimatedStartDate", "EstimatedEndDate",
]


class TdlrTabsProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        state_code: str = "TX",
        county_code: int | None = None,
        lookback_days: int = 30,
        page_size: int = 100,
        max_pages: int = 200,
    ) -> None:
        self.state_code = state_code.upper()
        self.county_code = county_code
        self.lookback_days = lookback_days
        self.page_size = page_size
        self.max_pages = max_pages
        self._county_names: dict[int, str] | None = None

    def _fetch_county_names(self) -> dict[int, str]:
        if self._county_names is not None:
            return self._county_names
        req = urllib.request.Request(SEARCH_PAGE_URL, headers={"User-Agent": "Mozilla/5.0 SpecIndex-StateAgent/0.2"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        m = re.search(r'<select[^>]*id="filter-location-county"[^>]*>(.*?)</select>', html, re.S)
        names: dict[int, str] = {}
        if m:
            for value, label in re.findall(r'<option value="(\d*)">([^<]*)</option>', m.group(1)):
                if value:
                    names[int(value)] = label.strip()
        self._county_names = names
        return names

    def _fetch_page(self, cutoff: date, start: int) -> dict[str, Any]:
        params: list[tuple[str, str]] = []
        for i, field in enumerate(_DATATABLES_FIELDS):
            params += [
                (f"columns[{i}][data]", field),
                (f"columns[{i}][name]", ""),
                (f"columns[{i}][searchable]", "true"),
                (f"columns[{i}][orderable]", "true"),
                (f"columns[{i}][search][value]", ""),
                (f"columns[{i}][search][regex]", "false"),
            ]
        params += [
            ("draw", "1"),
            ("order[0][column]", "3"),
            ("order[0][dir]", "desc"),
            ("start", str(start)),
            ("length", str(self.page_size)),
            ("search[value]", ""),
            ("search[regex]", "false"),
            ("RegistrationDateBegin", cutoff.strftime("%m/%d/%Y")),
            ("RegistrationDateEnd", date.today().strftime("%m/%d/%Y")),
        ]
        if self.county_code is not None:
            params.append(("LocationCounty", str(self.county_code)))

        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(
            SEARCH_API_URL,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 SpecIndex-StateAgent/0.2",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        cutoff = self._cutoff_date(last_watermark)
        print(f"[tdlr-tabs] cutoff={cutoff.isoformat()} county_code={self.county_code}", file=sys.stderr)

        county_names = self._fetch_county_names()
        rows: list[dict[str, Any]] = []
        start = 0
        total_filtered = None
        for _ in range(self.max_pages):
            try:
                body = self._fetch_page(cutoff, start)
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
                print(f"[tdlr-tabs] fetch error at start={start}: {e}", file=sys.stderr)
                break
            total_filtered = body.get("recordsFiltered", 0)
            page = body.get("data", [])
            if not page:
                break
            for r in page:
                r["_county_name"] = county_names.get(r.get("County"), "")
                r["_status_label"] = PROJECT_STATUS_LABELS.get(r.get("ProjectStatus"), "")
            rows.extend(page)
            start += len(page)
            if start >= (total_filtered or 0):
                break
        print(f"[tdlr-tabs] fetched {len(rows)} of {total_filtered} filtered rows", file=sys.stderr)
        return rows

    def _cutoff_date(self, last_watermark: str) -> date:
        if last_watermark and last_watermark not in ("0", ""):
            try:
                return date.fromisoformat(last_watermark[:10])
            except ValueError:
                pass
        return date.today() - timedelta(days=self.lookback_days)

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        return hash_fields(row, ["ProjectId"])

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        # ProjectCreatedOn is a real, reliable registration timestamp --
        # advance to the max seen, same pattern as every date-bounded
        # provider in this pipeline.
        best = current or "0"
        for r in rows:
            created = (r.get("ProjectCreatedOn") or "")[:10]
            if created and created > best:
                best = created
        return best

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for r in rows:
            pid = r.get("ProjectId")
            if not pid:
                continue
            cost = r.get("EstimatedCost")
            reg_date = (r.get("ProjectCreatedOn") or "")[:10] or None
            out.append(
                {
                    "id": f"tx-tdlr-tabs-{pid}"[:80],
                    "name": (r.get("ProjectName") or r.get("FacilityName") or r.get("ProjectNumber") or "")[:120],
                    "city": "",
                    "county": r.get("_county_name") or "",
                    "status": "permitting",
                    "project_type": "commercial",
                    "estimated_value_usd": float(cost) if cost is not None else None,
                    "square_footage": None,
                    "owner": "",
                    "architect": "",
                    "general_contractor": "",
                    "opened_or_announced_date": reg_date,
                    "description": (r.get("FacilityName") or r.get("ProjectName") or "")[:900],
                    "key_specs": [s for s in [r.get("_status_label"), r.get("ProjectNumber")] if s],
                    "mentioned_brands": [],
                    "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression"],
                    "sources": [
                        {
                            "title": f"TDLR TABS project {r.get('ProjectNumber')}",
                            "url": f"https://www.tdlr.texas.gov/TABS/Search/Project/{r.get('ProjectNumber')}",
                        }
                    ],
                    "open_for": "Registered commercial construction project (TX Architectural Barriers requirement, projects >= $50k). Early product/spec window.",
                    "state": self.state_code,
                    "zip": "",
                }
            )
        return out
