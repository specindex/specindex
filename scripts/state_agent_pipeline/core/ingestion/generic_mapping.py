"""Shared field-mapping to_projects() helper for clean structured sources.

Most ArcGIS/Socrata permit feeds are already clean structured government
data (a real address field, a real date field, a real cost field) --
running Flash/Sonnet over rows like that is pure wasted LLM cost for no
quality gain, same reasoning as sam_gov_provider.py / usaspending_provider.py
(see pipeline.py's NO_LLM_PROVIDER_TYPES docstring).

Ported from the asif-test sandbox's proven rows_to_projects() (2026-07-28
national county pass, verified against 10 real counties) rather than
redesigned from scratch. Opt-in only: a state config must explicitly set
name_fields/address_fields (see ArcGISProvider/SocrataProvider's
to_projects()) -- states that don't set these keep going through
Flash/Sonnet exactly as before.
"""

from __future__ import annotations

import re
from typing import Any


def _first(row: dict[str, Any], fields: list[str]) -> str:
    for f in fields:
        v = row.get(f)
        if v not in (None, ""):
            return str(v)
    return ""


def _join(row: dict[str, Any], fields: list[str]) -> str:
    """Space-join every non-empty field, in order -- for sources that split
    an address into components (street_number/street_name/street_suffix)
    instead of providing one pre-combined address column. _first() picking
    only the first component (e.g. San Francisco's DBI feed: street_number
    alone, "2331") is wrong here; every other wired source's address_fields
    is a single already-combined column, which is why _first() has been
    the right default everywhere else."""
    return " ".join(str(row[f]).strip() for f in fields if row.get(f) not in (None, ""))


def _money(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _iso_date(raw: Any) -> str | None:
    """Normalize a source date to YYYY-MM-DD.

    Handles the three shapes real permit feeds actually return:
    already-ISO strings (pass through), Esri epoch-milliseconds ints,
    and US MM/DD/YYYY strings (Snohomish County PDS stores IssueDate as
    an esriFieldTypeString in that format). Anything unrecognized falls
    back to the previous behavior (first 10 chars) so this can't
    regress an existing feed.
    """
    if raw in (None, ""):
        return None
    s = str(raw).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if re.match(r"^-?\d{10,}$", s):
        import datetime as _dt

        try:
            return _dt.datetime.utcfromtimestamp(int(s) / 1000).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return s[:10]


def field_mapped_to_projects(
    rows: list[dict[str, Any]],
    *,
    feed_id: str,
    state_code: str,
    county: str,
    id_field: str,
    watermark_field: str,
    name_fields: list[str],
    address_fields: list[str],
    desc_fields: list[str] | None = None,
    value_fields: list[str] | None = None,
    date_field: str | None = None,
    source_url: str,
    city_fields: list[str] | None = None,
    join_address_fields: bool = False,
    default_city: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        rid = _first(row, [id_field]) or str(row.get(watermark_field, ""))
        if not rid:
            continue
        address = _join(row, address_fields) if join_address_fields else _first(row, address_fields)
        # "__ADDRESS__" sentinel: some feeds (e.g. SF DBI) have no
        # separate project-name-like column at all -- the address itself
        # is the only sensible per-record name, same convention already
        # used by feeds whose real "primary_address" field doubles as name.
        if name_fields == ["__ADDRESS__"]:
            name = address or f"{county} permit {rid}"
        else:
            name = _first(row, name_fields) or f"{county} permit {rid}"
        desc = "; ".join(p for p in (_first(row, [f]) for f in (desc_fields or [])) if p) or name
        value = None
        for vf in value_fields or []:
            value = _money(row.get(vf))
            if value is not None:
                break
        date_val = _iso_date(row.get(date_field)) if date_field else None
        city = ""
        for cf in city_fields or []:
            if row.get(cf):
                # Some feeds' "city" column is really an address line-2
                # ("EVERETT, WA 98204-4880" on Snohomish County's PDS
                # layers) -- keep only the part before the state/zip.
                city = str(row[cf]).split(",")[0].strip().title()
                break
        if not city and address and "," in address:
            # Real bug found 2026-07-28 (San Diego): "7676 Hazard Center
            # Dr, San Diego, CA" / "...San Diego, CA 92121" is
            # "street, city, ST[ zip]" (3 comma parts) -- always taking
            # the last part gave "CA" or "CA 92121" as the city, not
            # "San Diego". If the last part starts with a 2-letter state
            # abbreviation (with or without a trailing zip), use the
            # second-to-last part instead (still falls back to the plain
            # last-part split for "street, city" 2-part addresses, e.g.
            # LA's format).
            parts = [p.strip() for p in address.split(",")]
            if len(parts) >= 3 and re.match(r"^[A-Za-z]{2}(\s|$)", parts[-1]):
                city = parts[-2]
            else:
                city = parts[-1]
        if not city and default_city:
            city = default_city
        slug = re.sub(r"[^a-z0-9]+", "-", f"{feed_id}-{rid}".lower()).strip("-")[:80]
        # feed_id is already state-prefixed by convention (mi-detroit-wayne,
        # ca-losangeles-ladbs, il-cook-assessor, ...) -- don't prefix again.
        full_id = slug if slug.startswith(state_code.lower() + "-") else f"{state_code.lower()}-{slug}"
        out.append(
            {
                "id": full_id[:80],
                "name": name[:120],
                "city": city,
                "county": county,
                "status": "permitting",
                "project_type": "commercial",
                "estimated_value_usd": value,
                "square_footage": None,
                "owner": "",
                "architect": "",
                "general_contractor": "",
                "opened_or_announced_date": date_val,
                "description": desc[:900],
                "key_specs": [],
                "mentioned_brands": [],
                "competitor_watch": ["hvac", "roofing", "lighting", "flooring", "fire suppression"],
                "sources": [{"title": f"{county} {feed_id} {rid}", "url": source_url}],
                "open_for": "Active commercial building permit application. Early product/spec window.",
                "state": state_code.upper(),
                "zip": "",
            }
        )
    return out
