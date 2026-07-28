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

# Federal sources (SAM.gov, USAspending) aren't one-config-per-state the
# way Socrata/ArcGIS are -- a state can have more than one federal source,
# so these are keyed by "{STATE}-{SOURCE}" rather than bare state code.
# GA first: it already had verified, live-tested deterministic pullers
# (scripts/pull-sam-gov-bulk-ga.py, pull-usaspending-ga.py) before this
# framework existed, so it's the lowest-risk proof point for porting the
# same logic into BaseIngestionProvider.
GA_SAM_CONFIG: dict[str, Any] = {
    "state_code": "GA",
    "provider_type": "sam_gov",
}

GA_USASPENDING_CONFIG: dict[str, Any] = {
    "state_code": "GA",
    "provider_type": "usaspending",
    "lookback_days": 730,
}

# Verified live 2026-07-28: no date-range filter for anonymous users, but
# results sort newest-first so pagination-until-watermark works without
# one (see accela_provider.py). "Building" permit type search returns
# Gwinnett's own COMBLD- (commercial) prefixed permits.
GA_GWINNETT_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "GA",
    "provider_type": "accela",
    "county": "Gwinnett",
    "endpoint": "https://aca-prod.accela.com/GWINNETT",
    "permit_type_label": "Building",
    "lookback_days": 30,
}

# Verified live 2026-07-28: City of El Paso's Accela portal (agency code
# "ELPASO", not "ELPASOCO"/"EPCOUNTY" -- those 404). Unlike Gwinnett, this
# deployment REQUIRES Start/End Date to return any results at all, and
# uses explicit "Commercial New"/"Commercial Alteration"/etc. permit
# types rather than an implicit id-prefix convention -- confirmed real
# data (e.g. a "TXE2 Data Center Building" permit, a 60-unit apartment
# complex). Different column layout than Gwinnett
# (Action/Status/Date/Building Number/Building Type/Project Name/
# Description vs Gwinnett's Date/Permit Number/Permit Type/Project Name/
# Status/Action/Short Notes) -- accela_provider.py parses by header text,
# not fixed position, specifically because of this difference.
TX_ELPASO_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "El Paso",
    "endpoint": "https://aca-prod.accela.com/ELPASO",
    "permit_type_label": "Commercial New",
    "lookback_days": 30,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

# Verified live 2026-07-28: City of San Antonio's Accela portal (agency
# code "COSA" -- guessed from "City Of San Antonio" after ELPASOCO-style
# guesses 404'd; same trial pattern likely needed for the next city).
# Third distinct column layout (Date/Record Number/Record Type/
# Description/Project Name/Address/Expiration Date/Created By/Status/
# Action/Short Notes) -- has an explicit Address header this time, unlike
# Gwinnett/El Paso. "Project Name" here is a placeholder
# ("Building No: N/A; Unit No: N/A"), not a real name -- same acceptable
# tradeoff as NJ DCA's block/lot-style fallback naming.
TX_SANANTONIO_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Bexar",
    "endpoint": "https://aca-prod.accela.com/COSA",
    "permit_type_label": "Commercial New Building Permit",
    "lookback_days": 30,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

STATE_CONFIGS: dict[str, dict[str, Any]] = {
    "NJ": NJ_CONFIG,
    "NC": NC_CONFIG,
    "GA-SAM": GA_SAM_CONFIG,
    "GA-USASPENDING": GA_USASPENDING_CONFIG,
    "GA-GWINNETT": GA_GWINNETT_ACCELA_CONFIG,
    "TX-ELPASO": TX_ELPASO_ACCELA_CONFIG,
    "TX-SANANTONIO": TX_SANANTONIO_ACCELA_CONFIG,
}
