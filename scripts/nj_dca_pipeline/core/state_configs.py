"""Per-state agent configuration -- one dict per state, consumed by
core/ingestion/factory.py's build_provider(). Nodes 2-4 (Flash, Sonnet,
persist/checkpoint) stay identical regardless of provider_type; only
Node 1's config changes per state.

Endpoints below are real, previously-verified-live sources from this
session's own coverage work (see docs/states/nj.md, docs/states/nc.md),
not placeholders -- NC in particular uses the real Mecklenburg County
(Charlotte) ArcGIS endpoint rather than a generic gis.nc.gov guess, since
that's what was actually confirmed live.
"""

from __future__ import annotations

from typing import Any

NJ_CONFIG: dict[str, Any] = {
    "state_code": "NJ",
    "provider_type": "socrata",
    "endpoint": "https://data.nj.gov/resource/w9se-dmra.json",
    "watermark_field": "recordid",
    "hash_fields": ["treasurycode", "block", "lot", "permitno"],
    "commercial_where": (
        "usegroupdesc in ("
        "'Business Uses','Mercantile buildings','Restaurants/Night Clubs',"
        "'Hotels/motels','Educational','Factory and industrial (low hazard)',"
        "'Factory and industrial (moderate hazard)','Storage (low hazard)',"
        "'Storage (moderate hazard)','Institutional')"
    ),
    "lookback_days": 30,
}

# Mecklenburg County (Charlotte) -- verified live earlier this session,
# see docs/states/nc.md. Real ArcGIS commercial filter is permittype=
# 'Commercial'; OBJECTID is Esri's standard autoincrement watermark field
# (this layer wasn't originally pulled incrementally -- pull-nc-arcgis.py
# re-pulls a rolling date window each run -- OBJECTID-based delta is new
# for the state-agent framework, verify it behaves as expected before
# trusting it as NC's sole incremental path).
NC_CONFIG: dict[str, Any] = {
    "state_code": "NC",
    "provider_type": "arcgis",
    "endpoint": "https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingPermits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["permitnum"],
    "commercial_where": "permittype = 'Commercial'",
    "out_fields": "permitnum,permitdesc,permittype,usdcdesc,projname,projadd,zipcode,issuedate,bldgcost,totalsqft,ownname,worktype,workdesc",
    # OBJECTID alone is meaningless as a first-run bound on a long-lived
    # layer (see ArcGISProvider docstring) -- bound the first pull by a
    # real date field instead, same as NJ's Socrata processdate fallback.
    "date_field": "issuedate",
    "lookback_days": 30,
}

STATE_CONFIGS: dict[str, dict[str, Any]] = {
    "NJ": NJ_CONFIG,
    "NC": NC_CONFIG,
}
