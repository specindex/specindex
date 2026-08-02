"""City of Troy, MI (Oakland County) "Permits Issued" provider.

Oakland County, MI (1.27M people, 2nd largest county in Michigan) has NO
county-level commercial permit feed: its official open-data portal
(accessoakland.oakgov.com, ArcGIS Hub) publishes 365 datasets and not one
of them is building permits -- the only "construction" layers are road
construction projects. No Socrata domain, no CKAN, and no Accela Citizen
Access tenant exists for Oakland County or any of its cities (probed
2026-08-02: aca-prod.accela.com/{ROCHESTERHILLS,SOUTHFIELD,NOVI,TROY,
PONTIAC,AUBURNHILLS,ROYALOAK,FARMINGTONHILLS,WATERFORD,OAKLANDCOUNTY} all
404; /ROCHESTER is Rochester MN and /BIRMINGHAM is Birmingham AL). Most
Oakland County cities run BS&A Online, whose community-development permit
search is behind a login and exposes no public API.

The one real, public, no-auth structured feed found in the county is the
City of Troy's own "Permits Issued" application:

  GET https://apps.troymi.gov/PermitsIssued/Results
      ?PageNumber=1
      &PermitType=Building%20-%20Commercial
      &DateIssuedWhereClause.StartDate=01/01/2025
      &DateIssuedWhereClause.EndDate=08/02/2026

It is an ASP.NET MVC AJAX endpoint (discovered from the page's own
/PermitsIssued/Scripts/PermitsIssued/Index.js, which calls
`siteRoot + 'Results'`), returns JSON `{"data":{"table": "<html>"}}`, and
is fully stateless -- no cookies, session, or CSRF token, same as
tdlr_tabs_provider. The payload is a rendered HTML table with a fixed,
labeled header row: Permit Type / Permit Number / Date Issued / Address /
Applicant / Applicant Address / Applicant City State Zip / Parcel # /
Lot / Subdivision / Work Description / Value. Parsed by header text, not
fixed index, for the same reason AccelaProvider does.

Pagination is 25 rows/page; the visible pager only ever shows 5 links, so
"last page" is found by walking until a page returns zero data rows.

Verified live 2026-08-02: PermitType="Building - Commercial" over
01/01/2025-08/02/2026 returns 132 real permits (e.g. PB2026-1808,
575 W BIG BEAVER, Cervi Construction LLC, parcel 88-20-28-203-035);
"Project Construction" and "Parking Lot" add more commercial work.

DOCUMENT CAPTURE (roadmap): this endpoint has NO per-permit detail page
and NO attachments/documents sub-resource. The result table cells are
plain text with no <a href> anywhere; the only other routes the app
exposes are /PermitsIssued/AddressSearch and /PermitsIssued/
DescriptionSearch, both of which are just different filters over the same
flat table. Troy's e-permitting/plan documents live in BS&A Online
(bsaonline.com uid=406), which requires an account. So: no PDFs, no site
plans, no per-permit URL -- structured metadata only.
"""

from __future__ import annotations

import html as _html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields

RESULTS_URL = "https://apps.troymi.gov/PermitsIssued/Results"
PORTAL_URL = "https://apps.troymi.gov/PermitsIssued"

# Header text -> canonical field name.
HEADER_ALIASES = {
    "permit type": "permit_type",
    "permit number": "permit_number",
    "date issued": "date_issued",
    "address": "address_raw",
    "applicant": "applicant",
    "applicant address": "applicant_address",
    "applicant city state zip": "applicant_city_state_zip",
    "parcel #": "parcel",
    "lot": "lot",
    "subdivision": "subdivision",
    "work description": "work_description",
    "value": "value",
}

# Real values from the portal's own PermitType <select>. Restricted to the
# commercial/industrial-bearing types; "Building" (unqualified) is the
# residential-heavy catch-all (2,800+ rows since 2025) and is excluded.
DEFAULT_PERMIT_TYPES = ["Building - Commercial", "Project Construction", "Parking Lot"]

_TAG_RE = re.compile(r"<[^>]+>")


def _cell_text(cell_html: str) -> str:
    return _html.unescape(_TAG_RE.sub(" ", cell_html)).replace("\r", " ").replace("\n", " ").strip()


class TroyPermitsProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        state_code: str = "MI",
        county: str = "Oakland",
        city: str = "Troy",
        permit_types: list[str] | None = None,
        lookback_days: int = 30,
        max_pages: int = 200,
        timeout: int = 40,
    ) -> None:
        self.state_code = state_code.upper()
        self.county = county
        self.city = city
        self.permit_types = permit_types or DEFAULT_PERMIT_TYPES
        self.lookback_days = lookback_days
        self.max_pages = max_pages
        self.timeout = timeout

    # -- fetch ------------------------------------------------------

    def _cutoff_date(self, last_watermark: str) -> date:
        if last_watermark and last_watermark not in ("0", ""):
            try:
                return datetime.strptime(last_watermark, "%Y-%m-%d").date()
            except ValueError:
                pass
        return date.today() - timedelta(days=self.lookback_days)

    def _get_table(self, permit_type: str, page: int, start: date) -> str:
        query = urllib.parse.urlencode(
            {
                "PageNumber": page,
                "PermitType": permit_type,
                "DateIssuedWhereClause.StartDate": start.strftime("%m/%d/%Y"),
                "DateIssuedWhereClause.EndDate": date.today().strftime("%m/%d/%Y"),
            }
        )
        req = urllib.request.Request(
            f"{RESULTS_URL}?{query}",
            headers={
                "User-Agent": "Mozilla/5.0 SpecIndex-StateAgent/0.2",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read())
        return (payload.get("data") or {}).get("table") or ""

    @staticmethod
    def _parse_table(table_html: str) -> list[dict[str, str]]:
        rows = re.findall(r"<tr>(.*?)</tr>", table_html, re.S)
        if not rows:
            return []
        headers = [_cell_text(c).lower() for c in re.findall(r"<th[^>]*>(.*?)</th>", rows[0], re.S)]
        col_map = {i: HEADER_ALIASES[h] for i, h in enumerate(headers) if h in HEADER_ALIASES}
        if len(col_map) < 3:
            return []
        out: list[dict[str, str]] = []
        for raw in rows[1:]:
            cells = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", raw, re.S)]
            if not cells:
                continue
            parsed = {field: cells[i] for i, field in col_map.items() if i < len(cells)}
            if parsed.get("permit_number"):
                out.append(parsed)
        return out

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        cutoff = self._cutoff_date(last_watermark)
        print(f"[troy] cutoff={cutoff.isoformat()} types={self.permit_types}", file=sys.stderr)

        all_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for permit_type in self.permit_types:
            for page in range(1, self.max_pages + 1):
                try:
                    table = self._get_table(permit_type, page, cutoff)
                except Exception as e:  # noqa: BLE001 - one bad page must not kill the run
                    print(f"[troy] {permit_type} page {page} failed: {e}", file=sys.stderr)
                    break
                parsed = self._parse_table(table)
                if not parsed:
                    break
                for r in parsed:
                    key = r.get("permit_number", "")
                    if key in seen:
                        continue
                    seen.add(key)
                    r["source_permit_type_filter"] = permit_type
                    all_rows.append(r)
                print(f"[troy] {permit_type} page {page}: {len(parsed)} rows ({len(all_rows)} total)", file=sys.stderr)
        print(f"[troy] fetched {len(all_rows)} rows", file=sys.stderr)
        return all_rows

    # -- identity / watermark ---------------------------------------

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        return hash_fields(row, ["permit_number"])

    @staticmethod
    def _parse_issue_date(value: str) -> date | None:
        for fmt in ("%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except (ValueError, AttributeError):
                continue
        return None

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        dates = [d for d in (self._parse_issue_date(r.get("date_issued", "")) for r in rows) if d]
        if not dates:
            return current
        best = max(dates)
        if current and current not in ("0", ""):
            try:
                if datetime.strptime(current, "%Y-%m-%d").date() >= best:
                    return current
            except ValueError:
                pass
        return best.isoformat()

    # -- mapping ----------------------------------------------------

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from project_identity import slugify

        out: list[dict[str, Any]] = []
        for r in rows:
            permit_no = r.get("permit_number") or ""
            issued = self._parse_issue_date(r.get("date_issued", ""))

            value_raw = (r.get("value") or "").replace("$", "").replace(",", "")
            try:
                value = float(value_raw) if value_raw else None
            except ValueError:
                value = None
            if value is not None and value <= 0:
                value = None

            desc = r.get("work_description") or r.get("permit_type") or "Commercial building permit."
            uid = slugify(f"troy-{permit_no}")
            out.append(
                {
                    "id": f"mi-oakland-troy-{uid}"[:80],
                    "name": (f"{r.get('address_raw') or permit_no} -- {r.get('permit_type') or ''}").strip(" -")[:120],
                    "address": r.get("address_raw") or "",
                    "city": self.city,
                    "county": self.county,
                    "status": "permitting",
                    "project_type": "commercial",
                    "estimated_value_usd": value,
                    "square_footage": None,
                    "owner": r.get("applicant") or "",
                    "architect": "",
                    "general_contractor": r.get("applicant") or "",
                    "opened_or_announced_date": issued.isoformat() if issued else None,
                    "description": desc[:900],
                    "key_specs": [
                        f"Permit number: {permit_no}",
                        f"Permit type: {r.get('permit_type') or ''}",
                        f"Parcel: {r.get('parcel') or ''}",
                    ],
                    "mentioned_brands": [],
                    "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression"],
                    "sources": [
                        {
                            "title": f"City of Troy, MI permit {permit_no}",
                            "url": PORTAL_URL,
                        }
                    ],
                    "open_for": "Active commercial building permit. Early product/spec window.",
                    "state": self.state_code,
                    "zip": "",
                }
            )
        return out
