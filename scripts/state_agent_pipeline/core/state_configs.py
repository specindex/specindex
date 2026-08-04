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
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
}

# Mecklenburg County (Charlotte) -- verified live earlier this session,
# see docs/states/nc.md. Real ArcGIS commercial filter is permittype=
# 'Commercial'; OBJECTID is Esri's standard autoincrement watermark field
# (this layer wasn't originally pulled incrementally -- pull-nc-arcgis.py
# re-pulls a rolling date window each run -- OBJECTID-based delta is new
# City of Los Angeles (LADBS) -- deterministic-first find, 2026-07-28.
# "Building and Safety - Building Permits Issued from 2020 to Present (N)"
# on data.lacity.org, verified live via real row query (not catalog
# metadata): 403K+ rows, MAX(issue_date) = 3 days before verification,
# daily refresh_time field confirms an actively-updating pipeline, not a
# stale export -- data.lacity.org's catalog has ~30 old duplicate/frozen
# "permit" datasets (many sharing an identical May-2023 rowsUpdatedAt);
# this is the one that's genuinely current. permit_sub_type='Commercial'
# is the real commercial/residential split (vs Apartment/1-2 Family
# Dwelling/Onsite/Offsite). permit_nbr isn't purely numeric, so this
# always re-scans the lookback window rather than advancing past it --
# acceptable for the 30-day rolling-window approach already used for TX.
CA_LOSANGELES_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "socrata",
    "county": "Los Angeles",
    "endpoint": "https://data.lacity.org/resource/pi9x-tg5x.json",
    "watermark_field": "permit_nbr",
    "hash_fields": ["permit_nbr"],
    "commercial_where": "permit_sub_type='Commercial'",
    "date_field": "issue_date",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    # Opt into deterministic (no Flash/Sonnet) mapping -- clean structured
    # permit data, no free text worth an LLM's judgment. See
    # generic_mapping.py / roadmap item 66.
    "feed_id": "ca-losangeles-ladbs",
    "id_field": "permit_nbr",
    "name_fields": ["primary_address", "work_description", "permit_type"],
    "address_fields": ["primary_address"],
    "value_fields": ["valuation"],
    "desc_fields": ["work_description", "permit_type"],
}

# LA County government (unincorporated areas + ~40 contract cities without
# their own building dept), via EPIC-LA (Tyler Technologies), the county's
# own case-management system. Owner account dpwgis_lacounty confirms this
# is the real county GIS org, not third-party noise (a "shovelsai"-owned
# item with the same "Los Angeles County Construction Permits" framing
# showed up in the same search -- that's a third-party static snapshot,
# not this). 907K total rows spanning building, grading, sewer, and
# planning cases -- not building-only -- so this layer needs both a
# MODULENAME/USE filter. USE_CURR is null on 89% of rows (mostly non-
# building case types); USE_PROPOSED1 is the populated field on actual
# permit applications and carries the real category prefix ("Commercial -
# Retail stores", "Service - Restaurants...", "Industrial - Storage" vs.
# "Residential -"/"Accessory -"). Verified live: real rows dated
# 2026-07-27/28 exist (today, at data-pull time); a single 2026-11-29
# grading application is a legitimate future-dated outlier, not a bug
# (unlike Collin County's bad future timestamp fixed earlier this
# session), so no upper-bound clamp needed here.
CA_LACOUNTY_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Los Angeles",
    "endpoint": "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/EPIC-LA_Case_History_view/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["CASENUMBER"],
    "commercial_where": "USE_PROPOSED1 LIKE 'Commercial%' OR USE_PROPOSED1 LIKE 'Service%' OR USE_PROPOSED1 LIKE 'Industrial%'",
    "out_fields": "CASENUMBER,PROJECTNAME,PROJECT_NAME,MODULENAME,WORKCLASS_NAME,USE_PROPOSED1,STATUS,MAIN_ADDRESS,APPLY_DATE,ISSUANCE_DATE,PERMIT_VALUATION,DISTRICT_DISPLAY",
    "date_field": "APPLY_DATE",
    "lookback_days": 30,
    "feed_id": "ca-lacounty-epicla",
    "id_field": "CASENUMBER",
    "name_fields": ["PROJECTNAME", "PROJECT_NAME", "CASENUMBER"],
    "address_fields": ["MAIN_ADDRESS"],
    "value_fields": ["PERMIT_VALUATION"],
    "desc_fields": ["USE_PROPOSED1", "STATUS"],
    "source_url": "https://egis-lacounty.hub.arcgis.com/datasets/la-county-permitting-epic-la-case-history",
}

# City of Torrance -- owner TorranceCA_GIS confirms this is the city's own
# GIS org. RESORCOM ('RESIDENTIAL'/'NON RESIDENTIAL') is the real
# commercial split. Named "Quarterly_Permit" and behaves like it: MAX
# ISSUEDDATE verified live at ~28 days old relative to pull date, so a
# 30-day lookback would miss data between refreshes -- widened to 45.
CA_TORRANCE_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Los Angeles",
    "endpoint": "https://services1.arcgis.com/38fAqAZVRCrVtPUU/arcgis/rest/services/Quarterly_Permit/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMIT_NUM"],
    "commercial_where": "RESORCOM = 'NON RESIDENTIAL'",
    "out_fields": "PERMIT_NUM,TYPEOFPERM,STATUS_1,ISSUEDDATE,SUBMITTEDD,JOBADDRESS,JOBVALUE,JOBDESCRIP,TYPEOFUSE,TYPEOFWORK",
    "date_field": "ISSUEDDATE",
    "lookback_days": 45,
}

# NOTE: City of Santa Clarita has a live Accela portal
# (aca-prod.accela.com/SANTACLARITA), but its Building module
# redirects unauthenticated requests straight to Login.aspx --
# confirmed dead end for a public/anonymous puller, unlike the Gwinnett/
# El Paso/San Antonio/McAllen/Brownsville Accela deployments that allow
# anonymous general search. Only EnviroServices/Licenses modules are
# public here. Not worth a config entry.

# City of Pasadena. The "Active Building Permits" layer (4 fields, no
# date/type) was a dead end on its own; this richer "Permit_Activity"
# service (same 637-row source data, owner CityOfPasadenaCAGIS, found via
# data.cityofpasadena.net's open-data listing) has both a real date field
# and a usable case-type discriminator. CASE_NUMBER prefix encodes
# Pasadena's own permit categories: BLDSFR=single-family, BLDMF=multi-
# family, BLDNR=non-residential (commercial), BLDMU=mixed-use. Verified
# live: MAX(LATEST_ACTIVITY) = today at research time.
CA_PASADENA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Los Angeles",
    "endpoint": "https://services2.arcgis.com/zNjnZafDYCAJAbN0/arcgis/rest/services/Permit_Activity/FeatureServer",
    "layer": 0,
    "watermark_field": "ESRI_OID",
    "hash_fields": ["CASE_NUMBER"],
    "commercial_where": "CASE_NUMBER LIKE 'BLDNR%' OR CASE_NUMBER LIKE 'BLDMU%'",
    "out_fields": "CASE_NUMBER,ADDRESS,DESCRIPTION,TOTAL_SQFT,LATEST_ACTIVITY,LAND_PARCEL_NO,PARCEL_NO",
    "date_field": "LATEST_ACTIVITY",
    "lookback_days": 30,
}

# City of Santa Monica -- CKAN platform (data.santamonica.gov), a 5th
# open-data platform type this session (after Socrata/ArcGIS/Accela/
# OpenDataSoft). permit_type='Commercial' is the real filter (also
# 'Mixed Use', 'Residential'). Verified live: MAX(date_entered) = 1 day
# before research pull. data.smgov.net (the old subdomain many stale
# search results point to) no longer resolves -- data.santamonica.gov
# is the real, current portal.
CA_SANTAMONICA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "ckan",
    "county": "Los Angeles",
    "endpoint": "https://data.santamonica.gov",
    "resource_id": "d6867c7d-89bc-4975-be35-4d2673a4764b",
    "watermark_field": "_id",
    "hash_fields": ["permit_number"],
    "commercial_where": "permit_type = 'Commercial'",
    "date_field": "date_entered",
    "lookback_days": 30,
}

# NOTE: City of Whittier has a live Accela portal (aca-prod.accela.com/
# WHITTIER) but the Building module redirects unauthenticated requests
# straight to Login.aspx -- confirmed dead end live 2026-07-28, same
# pattern as Santa Clarita. Not worth a config entry.

# City of Palmdale -- Accela agency code PALMDALE, confirmed real (city's
# own Building & Safety page directs applicants to this exact portal).
# Real dropdown option is "Commercial Permit" (the combo-permit type),
# not "Commercial" -- confirmed by fetching the live page's option list.
# A companion ArcGIS "Current_Development" layer on the city's own GIS
# server exists but is confirmed stale (newest ApprovalDate ~15 months
# old at research time) -- not used as the primary source.
CA_PALMDALE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Los Angeles",
    "endpoint": "https://aca-prod.accela.com/PALMDALE",
    "permit_type_label": "Commercial Permit",
    "lookback_days": 579,
}

# City of Long Beach -- owner arcgis_clb confirmed as the city's own
# official GIS org (233 public items, all civic layers). "Development
# Projects (Public)" tracks entitlement-through-construction, including
# real USER_Building_Permit_Issue_Date/Submission_Date fields and a coded
# USER_Project_Type (Residential/Mixed Use/Industrial/Commercial/Public
# Facility/Other). Small, curated feed of larger/significant projects
# (not routine Express Permits), so filtered to numbers, not a rolling
# permit-issuance cadence -- verified live: 'Commercial' alone is stale
# (max filed Nov 2022), but 'Mixed Use'/'Industrial' carry the real
# recent activity (filed through Nov 2025, issued through Apr 2026), so
# both are included. Long lookback (this is a low-volume dataset, not a
# daily feed) and USER_Date_Filed (more consistently populated than
# Issue_Date, which is often null pre-construction).
CA_LONGBEACH_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Los Angeles",
    "endpoint": "https://services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services/Development_Projects_(Public)/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["USER_Case_File_Number___Display"],
    "commercial_where": "USER_Project_Type___Display IN ('Commercial','Mixed Use','Industrial')",
    "out_fields": "USER_Project_Name___Display,USER_Address___Display,USER_Case_File_Number___Display,USER_Application_Type___Display,USER_Date_Filed___Display,USER_Current_Stage___Display,USER_Project_Type___Display,USER_Units___Display,USER_Number_of_Stories___Display,USER_Floor_Area__Sq__Ft_____Display,USER_Building_Permit_Submission_Date___Display,USER_Building_Permit_Issue_Date___Display,USER_Project_Completion_Date___Display",
    "date_field": "USER_Date_Filed___Display",
    "lookback_days": 400,
}

# NOTE: City of Inglewood has a real, city-confirmed Accela portal
# (aca-prod.accela.com/INGLEWOOD -- Inglewood permits its own marquee
# venues, SoFi Stadium/the Forum, under this code, not via LA County),
# but live testing 2026-07-28 shows the Building module also redirects
# unauthenticated requests to Login.aspx -- same dead end as Whittier/
# Santa Clarita. The real usable source is the secondary lead: monthly
# Crystal-Reports PDF exports pulled directly from the same Accela
# Oracle backend at cityofinglewood.org/Archive.aspx?AMID=41, verified
# fresh (May 2026 report, PDF created 2026-06-26, real commercial TI
# rows e.g. BLD26-00793 SoFi Stadium sound stage work). Worth a
# dedicated PDF puller later -- not built yet.

# City of Downey -- Accela agency code DOWNEY. Verified via a real live
# row-level query (not catalog metadata): rows dated 07/27-07/28/2026,
# i.e. today/yesterday at research time. The city's marketing CNAME
# (permits.downeyca.org) is broken (302s to an error page) -- use the
# aca-prod.accela.com/DOWNEY root directly. Confirmed as Downey's own
# standalone Accela system, not an LA County/EPIC-LA contract-city
# arrangement.
CA_DOWNEY_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Los Angeles",
    "endpoint": "https://aca-prod.accela.com/DOWNEY",
    "permit_type_label": "Commercial Addition-Alteration",
    "lookback_days": 579,
}

# City of Lancaster -- Accela agency code LANCASTER (only valid code;
# LANCASTERCA/CITYOFLANCASTER both 404). A one-time historical ArcGIS
# export (COL_Issued_Permits_wValuation_07012023_10202023) confirms
# Accela is the real backend and shares the identical commercial-permit
# taxonomy, but is itself ~2.75 years stale -- not used as the source.
CA_LANCASTER_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "accela",
    "county": "Los Angeles",
    "endpoint": "https://aca-prod.accela.com/LANCASTER",
    "permit_type_label": "Commercial New",
    "module": "Permits",  # module=Building errors out for this jurisdiction; only Permits exists
    "lookback_days": 579,
}

# City of El Monte -- Tyler EnerGov Citizen Self Service, tenant "El
# Monte" (tenantId 1). See core/ingestion/energov_provider.py docstring
# for why this drives the real UI rather than hand-crafting the API call
# (a bare/session-bound POST replicating the real request 500s; only a
# genuine click-triggered XHR succeeds). Real category text confirmed
# live: "Business Occupancy Permit (Non-Residential)" etc.
#
# KNOWN LIMITATION, verified live 2026-07-28: the "Advanced" panel (which
# would hold record-type + date-range filters) stays ng-hide'd in every
# UI state tried on this tenant's theme, so there's no confirmed way to
# set a server-side date filter or sort. The blank/default search returns
# a fixed-ish sample of real commercial permits dated ~mid-2025 -- NOT
# the most recent records -- regardless of when this runs. Treat this as
# a one-time backfill source (real, verified data, just not a rolling
# "what's new" feed) until the Advanced-panel access is solved; don't
# assume re-running this on a schedule surfaces genuinely new permits.
CA_ELMONTE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "energov",
    "county": "Los Angeles",
    "endpoint": "https://elmonteca-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "El Monte",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# City of Glendale -- Tyler EnerGov, same tylerhost.net/apps/selfservice
# pattern as El Monte, but a live dry-run (2026-07-28) returned 0 rows
# (navigation/search didn't error, just no captured response) -- unlike
# Accela, where every deployment needed some per-jurisdiction tuning
# (label text, module name, login-gating), this EnerGov deployment likely
# needs the same treatment (different tenant_name, or a theme where the
# "Search" button selector/flow differs). Not yet debugged -- registered
# but not verified working.
CA_GLENDALE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "energov",
    "county": "Los Angeles",
    "endpoint": "https://glendaleca-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Glendale",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# City of Alhambra -- same tylerhost.net/apps/selfservice pattern as El
# Monte/Glendale, not the self-hosted variant originally assumed. URL
# confirmed live (2026-07-28) via web search + HTTP 200 check.
CA_ALHAMBRA_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "energov",
    "county": "Los Angeles",
    "endpoint": "https://alhambraca-energovpub.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Alhambra",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# City of Carson -- "Carson Civic Access", live since 2024-06-04, also
# tylerhost.net (not self-hosted). Confirmed live 2026-07-28.
CA_CARSON_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "energov",
    "county": "Los Angeles",
    "endpoint": "https://cityofcarsonca-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Carson",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# Ventura County, CA (rank 77 by population, no coverage before this).
# Researched live 2026-08-03. The county's own portal is a dead end for an
# anonymous puller: Ventura County RMA runs self-hosted Accela Citizen
# Access at vcca.venturacounty.gov/citizenaccess, but EVERY module
# (Building/Planning/Fire/EnvHealth/Enforcement/PublicWorks) and even
# APO/APOLookup.aspx 302 straight to Login.aspx -- "This feature requires
# registration and/or login". Same for the county GIS (gis.ventura.org,
# maps.ventura.org): the only "Permitting" FeatureServer there carries
# Communication Facilities / Mining Permits / Oil Permits, no building
# permits. Oxnard's Socrata dataset (data.oxnard.org vmzx-48vx "Building
# Permits") still appears in Socrata's discovery catalog but the domain now
# 301s every /resource/ and /api/ path to oxnardca.opengov.com/data
# (budget-only OpenGov), so its SODA API is gone; last data_updated_at was
# 2024-12-03 anyway, entirely outside the 2025-01-01 window.
#
# What IS live and open is the City of Ventura's own ArcGIS Server, which
# publishes its production EnerGov land-management database directly:
# CityShift/EnerGovEnt/MapServer/0 ("Permits"). Verified live 2026-08-03 --
# 51,066 rows total, 9,277 issued on/after 2025-01-01, MAX(ISSUEDDATE)
# 3 days before verification, so this tracks the live system rather than
# being a frozen export. (The sibling CityShift/permits/MapServer/0 layer
# has the same shape but stopped updating in 2024 -- only ONE row with
# ISSUEDDATE >= 20240101 -- do not use it.)
#
# Two real quirks, both handled by config rather than a one-off script:
#   * This is an old ArcGIS Server: advancedQueryCapabilities reports
#     supportsPagination=false AND supportsOrderBy=false, and the server
#     hard-errors ("Pagination is not supported.") on any request carrying
#     resultOffset/resultRecordCount. Hence supports_pagination=False --
#     maxRecordCount is 50000, comfortably above the whole commercial
#     window, so a single unpaginated query returns everything.
#   * ISSUEDDATE/APPLYDATE are esriFieldTypeInteger in YYYYMMDD form, with
#     29990101 used as the "not yet issued" sentinel -- so the commercial
#     filter carries an explicit `ISSUEDDATE < 29990101` guard, otherwise
#     every unissued application matches any `>= 2025xxxx` lookback.
# Commercial split is PTYPENAME ('BLD - Building Commercial Permit: PLCK/
# OTC', 'BLD - Mixed Com/Res Permit', 'BLD - Building Commercial Parklet
# Permit', 'BLD - Sign Permit') plus PWORKCNAME='Commercial', which picks
# up commercial PEM (plumbing/electrical/mechanical) combo and demolition
# permits on commercial buildings. 649 rows match since 2025-01-01.
CA_VENTURA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Ventura",
    "endpoint": "https://map.cityofventura.net/arcgis/rest/services/CityShift/EnerGovEnt/MapServer",
    "layer": 0,
    # This layer's OID field is FID, not the Esri-default OBJECTID.
    "watermark_field": "FID",
    "hash_fields": ["PERMITNUM"],
    "supports_pagination": False,
    "include_geometry": False,
    "commercial_where": (
        "(PTYPENAME LIKE '%Commercial%' OR PTYPENAME LIKE '%Mixed Com/Res%' "
        "OR PTYPENAME LIKE '%Sign Permit%' OR PWORKCNAME LIKE '%Commercial%') "
        "AND ISSUEDDATE < 29990101"
    ),
    "out_fields": (
        "FID,PERMITID,PERMITNUM,PLANCASE,PTYPENAME,PWORKCNAME,PSTATDESC,"
        "ISSUEDDATE,APPLYDATE,ESTIMVALUE,SQUAREFEET,PADDRFULL,PARCELNUM,DESCWORK"
    ),
    "date_field": "ISSUEDDATE",
    "date_literal_style": "yyyymmdd_int",
    # Standing pull window: fixed 2025-01-01 anchor (see CLAUDE.md),
    # recomputed for 2026-08-03.
    "lookback_days": 579,
    "feed_id": "ca-ventura-cityofventura-energov",
    "id_field": "PERMITNUM",
    "name_fields": ["DESCWORK", "PERMITNUM"],
    "address_fields": ["PADDRFULL"],
    "value_fields": ["ESTIMVALUE"],
    "desc_fields": ["DESCWORK", "PTYPENAME", "PWORKCNAME", "PSTATDESC"],
    "source_url": "https://map.cityofventura.net/arcgis/rest/services/CityShift/EnerGovEnt/MapServer/0",
}

# City of Pomona -- the genuinely self-hosted EnerGov tenant (own domain
# connect.pomonaca.gov, not tylerhost.net; path also differs:
# energov_prod/selfservice, lowercase/underscore -- confirmed live via
# HTTP 200, and the provider's selfservice_path param handles that fine).
# NOT wired into STATE_CONFIGS yet -- live testing 2026-07-28 found this
# specific tenant's own infra is meaningfully slower/flakier than
# tylerhost.net's hosted tenants: page load alone took ~49s (vs ~3-6s for
# El Monte/Glendale/Alhambra/Carson) and no search response captured even
# after that. Config kept here for when this gets revisited with a much
# longer timeout budget + more debugging; see ROADMAP item 63 backlog note.
_CA_POMONA_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "energov",
    "county": "Los Angeles",
    "endpoint": "https://connect.pomonaca.gov",
    "tenant_id": "1",
    "tenant_name": "Pomona",
    "lookback_days": 900,
    "max_pages": 5,
    "selfservice_path": "energov_prod/selfservice",
}

# Maricopa County government (unincorporated areas), owner MaricopaCountyGIS
# confirms this is the county's own GIS org. PermitType='Building (Commercial)'
# is the real clean filter (vs 'Building (Residential)'/'Grading and
# Infrastructure'/'Standard Plan'/stormwater types). Verified live:
# MAX(IssuedDate) within the last few weeks of research date.
AZ_MARICOPACOUNTY_CONFIG: dict[str, Any] = {
    "state_code": "AZ",
    "provider_type": "arcgis",
    "county": "Maricopa",
    "endpoint": "https://services.arcgis.com/ykpntM6e3tHvzKRJ/arcgis/rest/services/Building_Permits_(view)/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PermitNumber"],
    "commercial_where": "PermitType = 'Building (Commercial)'",
    "out_fields": "PermitNumber,PermitType,WorkClass,PermitStatus,PermitDescription,FullStreetAddress,ZipCode,ApplicationDate,IssuedDate,ExpirationDate",
    "date_field": "IssuedDate",
    "lookback_days": 30,
    "feed_id": "az-maricopa",
    "id_field": "PermitNumber",
    "name_fields": ["FullStreetAddress", "PermitDescription", "PermitNumber"],
    "address_fields": ["FullStreetAddress"],
    "desc_fields": ["PermitDescription", "WorkClass", "PermitType"],
}

# City of Mesa -- citydata.mesaaz.gov (Socrata), real live building-permit
# dataset with a clean permit_type IN ('COM','RES') split. Verified live:
# MAX(issued_date) = 3 days before research date, 151 commercial permits
# in the trailing 30 days alone -- large, active dataset (155K+ rows back
# to 2003).
AZ_MESA_CONFIG: dict[str, Any] = {
    "state_code": "AZ",
    "provider_type": "socrata",
    "county": "Maricopa",
    "endpoint": "https://citydata.mesaaz.gov/resource/m2kk-w2hz.json",
    "watermark_field": "permit_number",
    "hash_fields": ["permit_number"],
    "commercial_where": "permit_type='COM'",
    "date_field": "issued_date",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
}

# City of Scottsdale -- self-hosted ArcGIS Server (maps.scottsdaleaz.gov),
# owner MMcPherson@ScottsdaleAZ.gov_COS_GIS confirms this is the city's
# own GIS org. Discovered via a dashboard web map's /data?f=json config
# (the dashboard-hides-the-service trap). type_desc LIKE '%COMM%' is the
# real commercial filter (vs SFR-* residential prefixes). Note: Scottsdale
# DOES run Accela (aca-prod.accela.com/SCOTTSDALE) but it's scoped to
# Business Licensing/Alarm Permits only, NOT building permits -- would be
# a false positive if used for this purpose. Verified live: most recent
# issuance_date rows dated May 2026.
AZ_SCOTTSDALE_CONFIG: dict[str, Any] = {
    "state_code": "AZ",
    "provider_type": "arcgis",
    "county": "Maricopa",
    "endpoint": "https://maps.scottsdaleaz.gov/arcgis/rest/services/Active_CDS_Cases/MapServer",
    "layer": 1,
    "watermark_field": "OBJECTID",
    "hash_fields": ["permit_number"],
    "commercial_where": "type_desc LIKE '%COMM%'",
    "out_fields": "permit_number,status_desc,issuance_date,type_desc,full_case_num,case_status,case_name",
    "date_field": "issuance_date",
    "lookback_days": 90,
}

# Pima County (Tucson metro) -- Accela agency code PIMA. Verified live:
# permits.pima.gov is Pima's own Accela Citizen Access front end
# (customization/PIMA/... paths, apikey embedded), which maps directly
# to the standard aca-prod.accela.com/PIMA backend (200 on both
# CapHome.aspx?module=Building and the bare root). Playwright dropdown
# probe on the live generalSearchForm found no Commercial-prefixed
# permit type at all (options are Aquatic Facility, Building Permit,
# C of O Historical, Construction Noise Permit, COT Plan Review,
# Damage/Demo Permit, Electrical/Mechanical Permit, Floodplain Use
# Permit, Green Building Certification, Historical Permit, Manufactured
# Building Permit, Model Plan Approval, Other Structures Permit,
# Oversize Overweight Vehicle, Public Records Request, Registered
# Plant, Revision, Right of Way Permit, Septic, Site Work Permit,
# Special Event Permit) -- "Building Permit" is the broadest real
# catch-all covering commercial work here, used as permit_type_label.
AZ_PIMACOUNTY_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "AZ",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Pima",
    "endpoint": "https://aca-prod.accela.com/PIMA",
    "permit_type_label": "Building Permit",
    "lookback_days": 579,
}

# NC_CONFIG (the "NC" key, Flash+Sonnet LLM path) was removed 2026-07-29 --
# it hit this exact same meckgis.mecklenburgcountync.gov endpoint as
# NC_MECKLENBURG_CONFIG below, just through paid Flash/Sonnet instead of
# the free deterministic generic_mapping path. Its watermark
# (data/pipeline/nj-dca/state-nc.json) never actually advanced past 0
# fetched, so removing it discards no captured data -- this was a landmine
# defused before it could duplicate-capture on a future cron re-enable,
# not a cleanup of an active bug. pull-nc-pipeline.yml now runs
# --state NC-MECKLENBURG instead.

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
    "lookback_days": 579,
}

# Indianapolis, IN (Marion County -- consolidated city-county
# government/Unigov, so this is genuine full-county coverage). A prior
# session flagged Marion County as hard, assuming the only option was
# the statewide Indiana CDR system (Oracle Reports, ~92 counties, no
# "ALL" option, complex HTML parsing per county). Re-investigated
# 2026-07-29 and found Indianapolis actually runs its own Accela
# instance (agency code "INDY", reached via a redirect from the city's
# branded permitsandcases.indy.gov/citizenaccess/ URL -- same non-
# standard-domain pattern as Boise). Same recurring "Building" module
# is empty for this agency (0 dropdown options) -- real module is
# "Permits" (matches the Omaha NE pattern exactly). No "Commercial"
# terminology in the dropdown at all -- Indianapolis/Indiana zoning
# uses "Improvement Location Permit" (ILP) terminology instead;
# "Improvement Location Permit-Non-Residential" is the real commercial-
# equivalent record type (vs. "...1-2 Family"/"...Multi-Family").
IN_INDIANAPOLIS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "IN",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Marion",
    "endpoint": "https://aca-prod.accela.com/INDY",
    "module": "Permits",
    "permit_type_label": "Improvement Location Permit-Non-Residential",
    "lookback_days": 579,
}

# Crown Point, IN -- Lake County seat, Tyler EnerGov Citizen Self Service,
# same tylerhost.net/apps/selfservice hosted pattern as the CA EnerGov
# tenants above. Gemini's URL guessed the wrong subdomain form
# ("crownpointin-energov.tylerhost.net" -- SSL connect error); the real,
# live one follows the standard "{tenant}-energovweb.tylerhost.net"
# pattern used elsewhere, confirmed via curl (HTTP 200) 2026-07-31. Lake
# County itself and its other cities (Gary/Hammond/East Chicago/
# Merrillville) have no live structured permit API (Gary uses OpenGov,
# unverified as pullable; the rest are paper/in-person only) -- Crown
# Point is the only confirmed live source in the county so far.
IN_CROWNPOINT_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "IN",
    "provider_type": "energov",
    "county": "Lake",
    "endpoint": "https://crownpointin-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Crown Point",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# Allen County / Fort Wayne, IN -- joint city-county Accela instance,
# agency code ACFW. Confirmed live 2026-07-31: module=Building AND
# module=Permits both redirect to Login.aspx/Error.aspx (login-gated or
# not configured), but module=Planning loads the general search form
# with no login wall and has a real permit-type dropdown
# (#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType). No single
# "Commercial" catch-all option exists; broadest real non-residential
# label is "08. Site Plan Review (Commercial, Industrial, Multifamily,
# School, Religious Institution)" (vs. residential-only options like
# "04. Improvement Location Permit (Residential decks...)" and "05. New
# Single Family Dwelling").
IN_ALLEN_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "IN",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Allen",
    "endpoint": "https://aca-prod.accela.com/ACFW",
    "module": "Planning",
    "permit_type_label": "08. Site Plan Review (Commercial, Industrial, Multifamily, School, Religious Institution)",
    "lookback_days": 579,
}

# City of Noblesville, IN -- Hamilton County seat, Tyler EnerGov Citizen
# Self Service, "-energovpub.tylerhost.net" subdomain form (not
# "-energovweb", which fails DNS for this tenant) -- confirmed live via
# curl HTTP 200 2026-07-31. Other Hamilton County cities (Fishers uses
# OpenGov Permitting & Licensing, Carmel uses Cityworks PLL, Westfield
# has no structured portal) are not one of the 8 existing provider
# types, not wired this pass.
IN_NOBLESVILLE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "IN",
    "provider_type": "energov",
    "county": "Hamilton",
    "endpoint": "https://noblesvillein-energovpub.tylerhost.net",
    "selfservice_path": "Apps/SelfService",
    "tenant_id": "1",
    "tenant_name": "Noblesville",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# Sioux Falls, SD (Minnehaha County's top jurisdiction, ~85% of the
# county's population). Gemini's domain had a typo -- gis.siouxfalls.
# ORG doesn't resolve (NXDOMAIN), real domain is gis.siouxfalls.GOV --
# found the correct one via an ArcGIS Online item search on the same
# item ID Gemini referenced in a GeoJSON download URL. Verified live
# 2026-07-29: MAX(ISSUEDATE)=2026-07-25, PERMITTYPE='Commercial
# Building' real (vs 'Residential Building', only two values exist).
# Minnehaha County's own lead (mcgis.minnehahacounty.org) was also
# fabricated (NXDOMAIN) -- not pursued further given Sioux Falls
# already covers the large majority of the county.
SD_SIOUXFALLS_CONFIG: dict[str, Any] = {
    "state_code": "SD",
    "provider_type": "arcgis",
    "county": "Minnehaha",
    "endpoint": "https://gis.siouxfalls.gov/arcgis/rest/services/Data/Community/MapServer/3",
    "layer": 3,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMITNUMBER"],
    "commercial_where": "PERMITTYPE='Commercial Building'",
    "out_fields": "PERMITNUMBER,PERMITTYPE,PERMITSTATUS,WORKCLASS,APPLYDATE,ISSUEDATE,VALUATION,MAINADDRESS,contractor_name",
    "date_field": "ISSUEDATE",
    "lookback_days": 180,
    "feed_id": "sd-siouxfalls",
    "id_field": "PERMITNUMBER",
    "name_fields": ["WORKCLASS", "MAINADDRESS", "PERMITTYPE"],
    "address_fields": ["MAINADDRESS"],
    "value_fields": ["VALUATION"],
    "desc_fields": ["WORKCLASS", "PERMITTYPE"],
    "source_url": "https://dataworks.siouxfalls.gov/datasets/cityofsfgis::building-permits",
}

# Ada County, ID (Boise, state's most populous county). Accela agency
# is NOT at the standard aca-prod.accela.com/boise URL (that 301-
# redirects); the real, live instance is hosted at Boise's own branded
# domain, permits.cityofboise.org/CitizenAccess -- confirmed live
# 2026-07-29, real Building module dropdown has "502-New or Added
# Commercial" among several Commercial-prefixed record types.
ID_ADA_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "ID",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Ada",
    "endpoint": "https://permits.cityofboise.org/CitizenAccess",
    "permit_type_label": "502-New or Added Commercial",
    "lookback_days": 579,
}

# East Baton Rouge Parish, LA (state's most populous parish/county).
# Genuine parish-level source (data.brla.gov is the Parish/City-Parish
# consolidated government's own portal). Verified live 2026-07-29:
# MAX(issueddate)=2026-07-24, designation='Commercial' is real (46,656
# of 142,426 total rows; also Residential=93,097).
LA_EBR_CONFIG: dict[str, Any] = {
    "state_code": "LA",
    "provider_type": "socrata",
    "county": "East Baton Rouge",
    "endpoint": "https://data.brla.gov/resource/7fq7-8j7r.json",
    "watermark_field": "permitid",
    "hash_fields": ["permitid"],
    "commercial_where": "designation='Commercial'",
    "date_field": "issueddate",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "la-ebr-batonrouge",
    "id_field": "permitid",
    "name_fields": ["projectdescription", "permittype", "streetaddress"],
    "address_fields": ["streetaddress", "city1", "state1", "zip"],
    "value_fields": ["projectvalue"],
    "desc_fields": ["projectdescription", "permittype"],
    "source_url": "https://data.brla.gov/Housing-and-Development/EBR-Building-Permits/7fq7-8j7r",
}

# Greenville County, SC (state's most populous county). County
# government itself has no public API (eTRAKiT web portal only) --
# wired City of Greenville instead, which extracts nightly from its
# Accela database into a public ArcGIS layer. Gemini gave the right
# layer name ("BuildingPermits_PriorTwoYears") but not its real
# service URL -- found via an ArcGIS Online owner-scoped item search
# (owner cdurham@greenvillesc.gov_grvlsc). Verified live 2026-07-29:
# MAX(NewIssueDate)=2026-07-28 (today), PERMIT_TYPE='BLDC' is real and
# matches Gemini's claimed code exactly (BLDG=residential, DEMR/DEMC=
# demolition). Real dead end found mid-verification: this old ArcGIS
# Server (10.81) rejects DATE/TIMESTAMP literal queries against
# NewIssueDate entirely (a genuine server bug, "Failed to execute
# query" on every literal style, PERMIT_TYPE-only queries work fine) --
# used APPLICDATE instead, a plain esriFieldTypeDouble storing YYYYMMDD
# as a number (e.g. 20260406.0), queryable with a bare numeric
# comparison. Added a new "yyyymmdd_int" date_literal_style to
# arcgis_provider.py for this.
# City of Columbia, SC (Richland County seat / state capital). Richland
# County itself (unincorporated areas) runs CentralSquare eTRAKiT
# (https://etrakit.rcgov.us/etrakit/, confirmed live 200 2026-07-31) with
# no public API/open-data feed -- eTRAKiT here is a plain login-gated
# search UI, same class of dead end as other eTRAKiT county deployments
# in this codebase. City of Columbia (the county's largest incorporated
# jurisdiction) redirects access.columbiasc.gov/selfservice to
# https://cityofcolumbiasc-energovweb.tylerhost.net/apps/selfservice --
# same tylerhost.net Tyler EnerGov Citizen Self Service pattern as the
# CA EnerGov configs above. REAL DEAD END, confirmed live 2026-07-31: a
# dry-run's Search-button click timed out (0 rows); a direct Playwright
# probe of the search route shows why -- it 302s to
# .../apps/selfservice/#/sso.html?redirectUrl=%2Fsearch (page title "Log
# In"), i.e. this tenant's search is login-gated unlike El Monte/Glendale/
# Carson's anonymous-accessible search. Left registered (same as
# CA-GLENDALE's real 0-row dead end above) in case Tyler changes the
# tenant's auth config later, but do NOT call this VERIFIED_WORKING --
# logged FAILED_NEED_ALT in jurisdiction_health_matrix.json.
SC_COLUMBIA_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "SC",
    "provider_type": "energov",
    "county": "Richland",
    "endpoint": "https://cityofcolumbiasc-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "City of Columbia",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# Spartanburg County, SC. Tyler EnerGov CSS at
# spartanburgcountysc-energovweb.tylerhost.net/apps/selfservice --
# confirmed live and NOT login-gated (unlike SC_COLUMBIA_ENERGOV_CONFIG
# above): Playwright probe of #/search loads with page title "Public
# Information" (no SSO redirect), and a real click-triggered search
# captured a genuine POST to .../api/energov/search/search returning
# live case rows (e.g. CaseNumber MANUHMPARK-000035-2022, IssueDate
# 2026-05-14), confirmed 2026-07-31.
SC_SPARTANBURG_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "SC",
    "provider_type": "energov",
    "county": "Spartanburg",
    "endpoint": "https://spartanburgcountysc-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Spartanburg County",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

SC_GREENVILLE_CONFIG: dict[str, Any] = {
    "state_code": "SC",
    "provider_type": "arcgis",
    "county": "Greenville",
    "endpoint": "https://citygis.greenvillesc.gov/arcgis/rest/services/InfoHUB/BuildingPermits_PriorTwoYears/MapServer/0",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMIT_NUM"],
    "commercial_where": "PERMIT_TYPE='BLDC'",
    "out_fields": "PERMIT_NUM,PERMIT_TYPE,Status,BP_STATUS,APPLIC_DESCRIPTION,PERMIT_VALUATION,STREETADDRESS,PERMIT_LOCATION,APPLICDATE,NewIssueDate,OWNER_NAME",
    "date_field": "APPLICDATE",
    "date_literal_style": "yyyymmdd_int",
    "lookback_days": 180,
    "feed_id": "sc-greenville",
    "id_field": "PERMIT_NUM",
    "name_fields": ["APPLIC_DESCRIPTION", "STREETADDRESS"],
    "address_fields": ["STREETADDRESS", "PERMIT_LOCATION"],
    "value_fields": ["PERMIT_VALUATION"],
    "desc_fields": ["APPLIC_DESCRIPTION"],
    "source_url": "https://www.greenvillesc.gov/383/Building-Permits-InfoHub",
}

# Douglas County, NE (Omaha, state's most populous county). Accela
# agency code "OMAHA" verified live -- but its default "Building"
# module returns zero dropdown options (200 status, empty page, same
# symptom seen for MO-STLOUIS and AL-JCCAL); the real module is
# "Permits" (confirmed by fetching OMAHA's Welcome.aspx module list:
# Enforcement/Fire/Licenses/Permits/Planning/PublicWorks/Rentals --
# no "Building" at all). Real dropdown option "New Building" (value=
# Permits/BUILDING/COMMERCIAL/NEW BUILDING) confirmed live 2026-07-29.
NE_DOUGLAS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "NE",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Douglas",
    "endpoint": "https://aca-prod.accela.com/OMAHA",
    "module": "Permits",
    "permit_type_label": "New Building",
    "lookback_days": 579,
}

# Bernalillo County, NM (Albuquerque, state's most populous county).
# Gemini's primary lead (City of Albuquerque's gis.cabq.gov ArcGIS
# service) is unreachable -- DNS resolves but the TCP connection to
# port 443 times out (confirmed live 2026-07-29, not a transient blip,
# retried with a 25s timeout). Fell back to Gemini's secondary lead:
# Bernalillo County's own Accela portal (unincorporated county areas),
# agency code "bernco" verified live (200 on Welcome.aspx), real
# Building module dropdown has "Commercial Building" (value=Building/
# Commercial/BCBP/NA -- the "BCBP" code matches what Gemini separately
# claimed as the bulk-export module code, good corroboration).
NM_BERNALILLO_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "NM",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Bernalillo",
    "endpoint": "https://aca-prod.accela.com/bernco",
    "permit_type_label": "Commercial Building",
    "lookback_days": 579,
}

# Fulton County, GA (state's top county by population -- but the county
# government itself issues almost no permits, since nearly all of Fulton
# is incorporated into Atlanta/Sandy Springs/Roswell/etc; City of Atlanta
# carries the vast majority of commercial volume). Also fills a gap in
# existing GA coverage: GA_GWINNETT_ACCELA_CONFIG is GA's #2 county by
# population, not #1. Accela agency code "ATLANTA_GA" verified live
# 2026-07-29 (200 on Welcome.aspx), real Building module dropdown has
# "Commercial New" among 20+ Commercial-prefixed record types.
GA_ATLANTA_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "GA",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Fulton",
    "endpoint": "https://aca-prod.accela.com/ATLANTA_GA",
    "permit_type_label": "Commercial New",
    "lookback_days": 579,
}

# Jefferson County, KY (Louisville Metro -- consolidated city-county
# government, so this genuinely covers the whole county, not just a top
# city). Verified live 2026-07-29: real ArcGIS item confirmed via a
# direct ArcGIS Online search, real service URL retrieved via item-info
# lookup (services1.arcgis.com/79kfd2K6fskCAkyg/.../active_construction_
# permits/FeatureServer -- Gemini didn't give this exact URL, just the
# dataset name, found the rest by searching). MAX(ISSUE_DATE)=2026-07-28
# (today -- exceptionally fresh), CATEGORY_NAME='Commercial' is real
# (888 rows; other values are Single Family/Multifamily/Condo-Patio/null).
KY_JEFFERSON_CONFIG: dict[str, Any] = {
    "state_code": "KY",
    "provider_type": "arcgis",
    "county": "Jefferson",
    "endpoint": "https://services1.arcgis.com/79kfd2K6fskCAkyg/arcgis/rest/services/active_construction_permits/FeatureServer",
    "layer": 0,
    "watermark_field": "ObjectId",
    "hash_fields": ["PERMIT_NUMBER"],
    "commercial_where": "CATEGORY_NAME='Commercial'",
    "out_fields": "PERMIT_NUMBER,PERMIT_TYPE,PERMIT_STATUS,CONTRACTOR,CATEGORY_NAME,WORK_TYPE,SQFT,PROJECT_COSTS,ADDRESS,CITY,STATE,ZIPCODE,ISSUE_DATE",
    "date_field": "ISSUE_DATE",
    "lookback_days": 180,
    "feed_id": "ky-jefferson-louisville",
    "id_field": "PERMIT_NUMBER",
    "name_fields": ["WORK_TYPE", "ADDRESS", "PERMIT_TYPE"],
    "address_fields": ["ADDRESS", "CITY", "STATE", "ZIPCODE"],
    "value_fields": ["PROJECT_COSTS"],
    "desc_fields": ["WORK_TYPE", "PERMIT_TYPE", "CATEGORY_NAME"],
    "source_url": "https://louisville-metro-opendata-lojic.hub.arcgis.com/",
}

# Multnomah County, OR (Portland -- top jurisdiction by population, ~95%
# of commercial permitting volume per Gemini). Portland Permitting &
# Development (formerly BDS) does NOT use Accela -- publishes directly
# via PortlandMaps ArcGIS REST services instead. Verified live 2026-07-29:
# layer name is literally "Commercial Construction Permit" -- already
# pre-filtered to commercial by the city itself, no where-clause needed
# (same pattern as MD-MONTGOMERY). MAX(ISSUED)=2026-07-24, 7,071 total
# rows.
OR_MULTNOMAH_CONFIG: dict[str, Any] = {
    "state_code": "OR",
    "provider_type": "arcgis",
    "county": "Multnomah",
    "endpoint": "https://www.portlandmaps.com/arcgis/rest/services/Public/BDS_Permit/MapServer/2",
    "layer": 2,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMIT"],
    "commercial_where": None,
    "out_fields": "PERMIT,TYPE,STATUS,WORK_DESCRIPTION,ISSUED,HOUSE,DIRECTION,PROPSTREET,STREETTYPE,CITY",
    "date_field": "ISSUED",
    "lookback_days": 180,
    "feed_id": "or-multnomah-portland",
    "id_field": "PERMIT",
    "name_fields": ["WORK_DESCRIPTION", "TYPE", "PROPSTREET"],
    "address_fields": ["HOUSE", "DIRECTION", "PROPSTREET", "STREETTYPE", "CITY"],
    "value_fields": [],
    "desc_fields": ["WORK_DESCRIPTION", "TYPE"],
    "source_url": "https://www.portlandmaps.com/arcgis/rest/services/Public/BDS_Permit_Commercial_Construction/MapServer",
}

# St. Louis County, MO (state's most populous county, NOT the independent
# City of St. Louis). Accela agency code is "SLC" -- confusingly the same
# code the initials-based guess for Salt Lake City hit first (see
# UT_SALTLAKE_ACCELA_CONFIG's note below -- these are two different real
# agencies that happen to collide on the same 3-letter code). The default
# "Building" module 404s for this agency; the real vertical-construction
# permits live under the "PublicWorks" module's search form, record type
# "PublicWorks/Building/Commercial/New Building" (visible label "BUILDING
# COMMERCIAL NEW BUILDING") -- confirmed live 2026-07-29 by fetching the
# module's real dropdown option list.
MO_STLOUIS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "MO",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "St. Louis",
    "endpoint": "https://aca-prod.accela.com/SLC",
    "module": "PublicWorks",
    "permit_type_label": "BUILDING COMMERCIAL NEW BUILDING",
    "lookback_days": 579,
}

# City of Columbia, MO -- Boone County's seat/largest city (county itself
# has no online permit system per Gemini, only a departmental info page).
# Self-hosted Tyler EnerGov (own domain energov.como.gov, not
# tylerhost.net), same energov_prod/selfservice path convention as the
# Pomona CA tenant. Verified live 2026-07-31: HTTP 200, page title
# "SelfService Public Site", real EnerGov Angular app markup present, and
# the provider successfully fetches real rows (50 across 5 pages, real
# CaseNumber/CaseType/dates). BUT: same known limitation as El Monte CA --
# the Advanced search panel isn't reachable, so the blank/default search
# is the only query possible, and on this tenant that fixed sample is
# 100% Fire/Open-Burning and Deck-Only residential permits, 0 commercial,
# across every page and both a 90-day and 900-day lookback tried
# 2026-07-31. NOT wired into STATE_CONFIGS -- would need Advanced-panel
# access (same open problem as Pomona/El Monte) before this becomes a
# usable commercial source. Kept here for when that gets solved.
_MO_COLUMBIA_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "MO",
    "provider_type": "energov",
    "county": "Boone",
    "endpoint": "https://energov.como.gov",
    "tenant_id": "1",
    "tenant_name": "Columbia",
    "lookback_days": 900,
    "max_pages": 5,
    "selfservice_path": "energov_prod/selfservice",
}

# Salt Lake City (Salt Lake County's top jurisdiction by population -- UT
# county government's Municipal Services District handles unincorporated
# areas only, no clean statewide/countywide ArcGIS building-permit layer
# found on a direct ArcGIS Online org search; SLC's own Accela portal is
# the real, live system). IMPORTANT: agency code is "SLCREF", not the
# obvious guess "SLC" -- "SLC" is already taken on Accela's shared hosting
# by St. Louis County, MO (confirmed live 2026-07-29: aca-prod.accela.com/
# SLC's error-page links reference stlouiscountymo.gov, and its module list
# -- Licenses/N/PublicWorks/WaterandSewer, no Building module -- doesn't
# match a building-permit portal at all). Accela agency codes are NOT
# globally unique or guessable from a city's initials -- always verify the
# real one live, never assume. "SLCREF" verified live: 200 on Welcome.aspx,
# has a real Building module (plus Engineering/Fire/Planning/etc).
UT_SALTLAKE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "UT",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Salt Lake",
    "endpoint": "https://aca-prod.accela.com/SLCREF",
    "permit_type_label": "Commercial Building Permit",
    "lookback_days": 579,
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
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

# City of Dallas -- Accela agency code DALLASTX (a Gemini-suggested code
# "dallastx8" 404'd; the real one found by trying plausible variants).
# Every URL in Gemini's first-pass structured JSON payload for Dallas
# turned out to be fully hallucinated (fabricated domains, 404 pages,
# an ArcGIS endpoint with no permits data) -- confirmed real here only
# by direct live verification (DNS + HTTP + inspecting the actual
# rendered dropdown), not by trusting the model's output. Real
# ddlGSPermitType dropdown values confirmed live 2026-07-28:
# "Commercial New Construction Permit" and "Commercial Alteration
# Addition Permit" (Gemini's guesses were close but not exact --
# "Commercial New Construction Permit"/"Commercial Alteration" wasn't
# the literal dropdown text). AccelaProvider only supports one exact
# permit_type_label per config, so this is split into two state keys to
# capture both commercial categories.
TX_DALLAS_NEW_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Dallas",
    "endpoint": "https://aca-prod.accela.com/DALLASTX",
    "permit_type_label": "Commercial New Construction Permit",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

TX_DALLAS_ALT_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Dallas",
    "endpoint": "https://aca-prod.accela.com/DALLASTX",
    "permit_type_label": "Commercial Alteration Addition Permit",
    "lookback_days": 579,
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
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

# --- TX county-agent research wave, 2026-07-28: agent-verified live sources ---

# City of Midland (dominant commercial-permit jurisdiction in Midland County).
# Sourced from Tyler EnerGov via GIS automation, verified fresh (dataLastEditDate
# same-day). DateIssued has a garbage 2068 placeholder for unissued permits --
# ApplyDate is the reliable field, used here as date_field.
TX_MIDLAND_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Midland",
    "endpoint": "https://services.arcgis.com/0H6bQdxd9223gQB5/arcgis/rest/services/Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PermitNumber"],
    "commercial_where": "PermitWorkClass LIKE 'Commercial%'",
    "out_fields": "PermitNumber,PermitStatus,Name,DateIssued,ApplyDate,Description,Address,PermitWorkClass,YEAR,URL",
    "date_field": "ApplyDate",
    "lookback_days": 30,
}

# City of San Marcos (Hays County). Native ArcGIS Server, hours-old edits at
# verification time. LANDUSE='Commercial' is the real classification field.
TX_HAYS_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Hays",
    "endpoint": "https://smgis.sanmarcostx.gov/arcgis/rest/services/Planning/CoSM_BuildingPermits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMITID"],
    "commercial_where": "LANDUSE = 'Commercial'",
    "out_fields": "PERMITID,ADDRESS,STATUS,DESCRIPTION,LANDUSE,TYPE,APPLIED,ISSUED,SQUAREFEET,PROJECTNUMBER,ProjectName",
    "date_field": "APPLIED",
    "lookback_days": 30,
}

# City of New Braunfels (straddles Comal/Guadalupe counties -- Permit_County
# field is dirty/free-text, not used as a hard filter here per the research
# agent's finding; tagged Comal since New Braunfels is the Comal county seat).
TX_COMAL_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Comal",
    "endpoint": "https://gismaps.newbraunfels.gov/arcserverwa22/rest/services/OpenData/PlanningZoning/MapServer",
    "layer": 10,
    "watermark_field": "OBJECTID",
    "hash_fields": ["CoNB_Permit_Number"],
    "commercial_where": "Permit_Group = 'BUILDING' AND Permit_Classification LIKE '%Commercial%' AND Permit_County = 'Comal'",
    "out_fields": "CoNB_Permit_Number,Permit_Type_Name,Permit_Group,Permit_Classification,Permit_Status,Permit_Address,Applicant_Name,Contractor_Name,Permit_Submit_Date,Permit_Issue_Date,Permit_County",
    "date_field": "Permit_Submit_Date",
    "lookback_days": 30,
}

# New Braunfels straddles Comal and Guadalupe counties -- same MapServer/10
# layer as TX_COMAL_CONFIG, split by the real Permit_County attribute so
# neither state file double-counts or mislabels the other's records.
TX_GUADALUPE_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Guadalupe",
    "endpoint": "https://gismaps.newbraunfels.gov/arcserverwa22/rest/services/OpenData/PlanningZoning/MapServer",
    "layer": 10,
    "watermark_field": "OBJECTID",
    "hash_fields": ["CoNB_Permit_Number"],
    "commercial_where": "Permit_TYPE_DESC LIKE 'Commercial%' AND Permit_County = 'Guadalupe'",
    "out_fields": "CoNB_Permit_Number,Permit_Type_Name,Permit_TYPE_DESC,Permit_Group,Permit_Status,Permit_Address,Applicant_Name,Property_Owner_Name,Contractor_Name,Permit_Submit_Date,Permit_Issue_Date,Permit_County",
    "date_field": "Permit_Submit_Date",
    "lookback_days": 30,
}

# City of Tyler (dominant jurisdiction in Smith County). Real commercial
# PermitType values confirmed: COMMERCIAL NEW / TENANT FINISH OUT / SHELL /
# LAKE TYLER.
TX_SMITH_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Smith",
    "endpoint": "https://services5.arcgis.com/RmXXW3PwBZGOxlSe/arcgis/rest/services/Permit_Data_With_XY/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMIT_NO"],
    "commercial_where": "PermitType LIKE 'COMMERCIAL%'",
    "out_fields": "PERMIT_NO,ISSUED,PermitType,PermitSubType,STATUS,SITE_ADDR,CONTRACTOR_NAME,OWNER_NAME,JOBVALUE,BLDG_SF,DESCRIPTION",
    "date_field": "ISSUED",
    "lookback_days": 30,
}

# City of Temple (Bell County). Type is free-text but cleanly prefixed --
# 'Comm ' vs 'Res '/'Residential' -- used as the commercial filter.
TX_BELL_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Bell",
    "endpoint": "https://arcgiswap02.ci.temple.tx.us/arcgiswap02/rest/services/PermitStatus/MapServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["Permit"],
    "commercial_where": "Type LIKE 'Comm%'",
    "out_fields": "Permit,Application_Date,Last_Update,Type,Description,Status,Address,Square_Footage,Estimated_Value,Applicant,Contractor",
    "date_field": "Application_Date",
    "lookback_days": 30,
}

# City of McAllen (Hidalgo County). Accela on a custom domain (not
# aca-prod.accela.com) -- confirmed same ACA page structure/field ids.
# CMM permit-number prefix = commercial; no date-range filter needed (same
# pagination-until-watermark pattern as Gwinnett).
TX_MCALLEN_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Hidalgo",
    "endpoint": "https://onlinepermits.mcallen.net/Portal",
    "permit_type_label": "Commercial New or Addition",
    "lookback_days": 579,
}

# City of Brownsville (Cameron County). Accela, lowercase agency code.
TX_BROWNSVILLE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Cameron",
    "endpoint": "https://aca-prod.accela.com/BROWNSVILLE",
    "permit_type_label": "Commercial Alteration Permit",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

# Oklahoma County, OK (Oklahoma City -- ~65% of the county's population
# and effectively all of its commercial construction). Verified live
# 2026-08-02/03 against aca-prod.accela.com/OKC:
#   * module="Building" errors out (Error.aspx) -- real module is
#     "Permits" (same pattern as Omaha/Indianapolis).
#   * The Permits module's record-type dropdown has 68 options; the
#     commercial building one is exactly "Building - Commercial"
#     (siblings: "Building - Residential", "Electrical - Commercial",
#     "Mechanical - Commercial", "Plumbing - Commercial", ...).
#   * This deployment DOES expose an anonymous Start/End Date filter
#     (txtGSStartDate/txtGSEndDate), so the full 2025-01-01 anchor
#     window can be requested directly instead of paging blind.
#   * Results grid headers are the bare "Number"/"Type"/"Application
#     Name" variants -- HEADER_ALIASES in accela_provider.py extended
#     accordingly.
#   * DOCUMENTS: this instance serves real plan-review PDFs anonymously.
#     Record detail pages are stable at
#     /Cap/CapDetail.aspx?Module=Permits&TabName=Permits&capID1=..&capID2=..&capID3=..&agencyCode=OKC
#     and the Attachments tab loads /FileUpload/AttachmentsList.aspx
#     (session-scoped to the last-viewed record). Confirmed by actually
#     downloading a 98KB / 2-page PDF ("Latest Mark-up with Questions
#     (1).pdf") off BLDC-2026-05486 with no login.
OK_OKLAHOMA_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "OK",
    "provider_type": "accela",
    "county": "Oklahoma",
    "endpoint": "https://aca-prod.accela.com/OKC",
    "module": "Permits",
    "permit_type_label": "Building - Commercial",
    # (date.today() - date(2025, 1, 1)).days as of 2026-08-03.
    "lookback_days": 579,
    # 10 rows/page in this deployment; the standing 2025-01-01 window is
    # thousands of records, so the default max_pages=30 (300 rows) would
    # truncate badly.
    #
    # KNOWN CEILING (measured, not assumed): ACA throttles long anonymous
    # paging sessions -- #divGlobalLoadingMask stops clearing and every
    # Next click gets intercepted. Run 1 died at page 62 (610 rows), run 2
    # at page 43 (430 rows), and a follow-up probe couldn't even load
    # CapHome for a while afterwards. So a single run realistically yields
    # ~40-60 pages, NOT the full 579-day window (~5,500 records at OKC's
    # ~70 commercial permits/week). First ingest landed 06/15/2026 ->
    # 07/31/2026. Real remaining scope: chunk the backfill into
    # month-sized start/end windows with a fresh browser session per
    # chunk, instead of one long paging session.
    "max_pages": 300,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

# City of Pearland (Brazoria County's largest city). Real Cityworks-backed
# commercial-specific layer -- BUS_CASE_DESC has values like "Commercial
# Alteration"/"Commercial Demolition Permit"/"Commercial Site Work Permit".
TX_BRAZORIA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Brazoria",
    "endpoint": "https://gis.pearlandtx.gov/hosting/rest/services/Commercial_Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["CASE_NUMBER"],
    "commercial_where": "1=1",  # layer is already commercial-only by name/source
    "out_fields": "CASE_NUMBER,DATE_ISSUED,BUS_CASE_DESC,CASE_STATUS,LOCATION,CASE_NAME,Applicant,PropertyOwner",
    "date_field": "DATE_ISSUED",
    "date_field_is_string": True,  # esriFieldTypeString "2021-02-23 0:00", not a real Date field
    "lookback_days": 30,
}

# City of Beaumont (Jefferson County). Already commercial-scoped layer
# ("Active Commercial Permits from Cityworks") -- no residential mixed in.
TX_JEFFERSON_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Jefferson",
    "endpoint": "https://cityworks.beaumonttexas.gov/CityworksNAD/gis/1/2662/rest/services/cw/FeatureServer",
    "layer": 5,
    "watermark_field": "OBJECTID",
    "hash_fields": ["CASE_NUMBER"],
    "commercial_where": "1=1",  # layer is already commercial-only by source
    "out_fields": "CASE_NUMBER,CASE_TYPE_DESC,SUB_TYPE_DESC,CASE_NAME,CASE_STATUS,LOCATION,DATE_ENTERED,DATE_ISSUED,DATE_MODIFIED,BUSINESS_NAME,CONTRACTOR_FIRST_NAME,CONTRACTOR_LAST_NAME",
    "date_field": "DATE_ENTERED",
    "date_literal_style": "timestamp",  # this Cityworks/SQL-Server layer rejects `DATE '...'`
    "lookback_days": 30,
}

# City of Odessa (Ector County). MGO permit data mirrored into Odessa's own
# ArcGIS org -- permitType carries a "(C)" suffix for all commercial trades.
TX_ECTOR_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Ector",
    "endpoint": "https://services6.arcgis.com/96XBo0KviQ3nV6zg/arcgis/rest/services/MGO_Data_From_API_to_OGIS/FeatureServer",
    "layer": 0,
    "watermark_field": "permitID",
    "hash_fields": ["permitNumber"],
    "commercial_where": "permitType LIKE '%Building-C%'",
    "out_fields": "permitID,permitNumber,description,permitType,projectValue,squareFootage,address,status,createdDate,issuedDate,updatedDate,projectName,county",
    "date_field": "createdDate",
    "lookback_days": 30,
}

# City of Leander (Williamson County). LandUse field distinguishes commercial
# (COMM/RETAIL/OFFICE/HOTEL/MED/BANK/IND/HC/EDU) from residential.
TX_WILLIAMSON_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Williamson",
    "endpoint": "https://services1.arcgis.com/L0MLvN0Ay0iEjnCT/arcgis/rest/services/Site_Development/FeatureServer",
    "layer": 47,
    "watermark_field": "OBJECTID",
    "hash_fields": ["ProjNum"],
    "commercial_where": "LandUse IN ('COMM','RETAIL','OFFICE','HOTEL','MED','BANK','IND','HC','EDU')",
    "out_fields": "ProjName,ProjAlias,ProjNum,LandUse,Status,Const_Status,FinalPlatDate,IssuedDate,ApvDate,CoCDate,SDP_Year,CoC_Year",
    "date_field": "IssuedDate",
    "lookback_days": 30,
}

# Wayne County (Detroit BSEED) -- verified live 2026-07-28: real
# esriFieldTypeDateOnly `issued_date` field, MAX = 2026-07-27 (fresh).
# 50 commercial-filtered rows in the last 30 days, confirmed by direct
# query before wiring. use_group covers Michigan Building Code groups
# (M/B/A/E/U); proposed_use_type keyword OR covers cases where use_group
# is null but the free-text use type is clearly commercial.
MI_WAYNE_CONFIG: dict[str, Any] = {
    "state_code": "MI",
    "provider_type": "arcgis",
    "county": "Wayne",
    "endpoint": "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/bseed_building_permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["record_id"],
    "commercial_where": (
        "(use_group IN ('M','B','A','E','U') OR proposed_use_type LIKE '%COMMERCIAL%' "
        "OR proposed_use_type LIKE '%RETAIL%' OR proposed_use_type LIKE '%OFFICE%' "
        "OR proposed_use_type LIKE '%WAREHOUSE%' OR proposed_use_type LIKE '%INDUSTRIAL%' "
        "OR proposed_use_type LIKE '%RESTAURANT%') "
        "AND proposed_use_type NOT LIKE '%RESIDENTIAL%' AND proposed_use_type NOT LIKE '%SINGLE FAMILY%'"
    ),
    "out_fields": "record_id,address,issued_date,permit_type,use_group,proposed_use_type,amt_estimated_contractor_cost,OBJECTID",
    "date_field": "issued_date",
    "date_literal_style": "timestamp",
    "lookback_days": 30,
    "feed_id": "mi-detroit-wayne",
    "id_field": "record_id",
    "name_fields": ["address", "proposed_use_type", "permit_type"],
    "address_fields": ["address"],
    "value_fields": ["amt_estimated_contractor_cost"],
    "desc_fields": ["proposed_use_type", "permit_type"],
}

# Kent County MI (Grand Rapids) Accela -- verified live 2026-07-31.
# County-level check found no county-wide feed (Kent County itself doesn't
# centralize permitting; most other Kent cities use BS&A Online, which has
# no public API). Grand Rapids, the county's largest city, runs Accela
# Citizen Access -- confirmed via Playwright (endpoint case-sensitive
# lowercase "grandrapids" in the path; module=Building 404s, only
# module=Permits works, same gotcha as other MI/GA Accela deployments).
# No single "Commercial" catch-all option in the #ddlGSPermitType dropdown
# -- picked the broadest real Commercial-prefixed label after probing all
# ~70 real options live: "Building Permit - Commercial or 3+ Family New or
# Addition".
MI_KENT_CONFIG: dict[str, Any] = {
    "state_code": "MI",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Kent",
    "endpoint": "https://aca-prod.accela.com/grandrapids",
    "module": "Permits",
    "permit_type_label": "Building Permit - Commercial or 3+ Family New or Addition",
    "lookback_days": 579,
    "feed_id": "mi-grandrapids-kent",
}

# Oakland County, MI (Detroit metro; 1.27M people) -- researched
# 2026-08-02. There is NO county-level commercial permit feed: Access
# Oakland (accessoakland.oakgov.com, ArcGIS Hub, 365 datasets) has zero
# building-permit layers, there is no Socrata/CKAN domain for the county,
# and no Accela Citizen Access tenant exists for the county or any of its
# cities (all probed and 404). Most Oakland cities run BS&A Online, whose
# community-development permit search requires a login.
#
# The one real public no-auth feed found is the City of Troy's own
# "Permits Issued" app (Troy is Oakland County's largest commercial
# corridor -- Big Beaver/Somerset). Undocumented but stateless AJAX
# endpoint, discovered from the page's own JS:
#   https://apps.troymi.gov/PermitsIssued/Results?PageNumber=1
#     &PermitType=Building%20-%20Commercial
#     &DateIssuedWhereClause.StartDate=01/01/2025
#     &DateIssuedWhereClause.EndDate=08/02/2026
# Verified live 2026-08-02: 132 "Building - Commercial" permits in the
# 2025-01-01..today window (e.g. PB2026-1808, 575 W BIG BEAVER, Cervi
# Construction LLC, parcel 88-20-28-203-035), plus Project Construction
# and Parking Lot types. See troy_permits_provider.py for the parsing
# contract.
#
# DOCUMENT CAPTURE: none available. No per-permit detail page (result
# cells contain no links at all), no attachments/documents sub-resource;
# the app's only other routes (AddressSearch, DescriptionSearch) are
# alternate filters over the same flat table. Plan documents live in
# BS&A Online (bsaonline.com uid=406) behind an account. Structured
# metadata only.
MI_OAKLAND_TROY_CONFIG: dict[str, Any] = {
    "state_code": "MI",
    "provider_type": "troy_permits",
    "county": "Oakland",
    "city": "Troy",
    "endpoint": "https://apps.troymi.gov/PermitsIssued/Results",
    "watermark_field": "date_issued",
    "hash_fields": ["permit_number"],
    "permit_types": ["Building - Commercial", "Project Construction", "Parking Lot"],
    # 2025-01-01 anchor per CLAUDE.md: (2026-08-02 - 2025-01-01).days
    "lookback_days": 578,
    "max_pages": 200,
    "feed_id": "mi-oakland-troy",
}

# Cook County (IL) Assessor's Permits (Socrata) -- verified live
# 2026-07-28: real, but date_issued has a data-quality bug (4 rows out
# of 92,437 total have a garbage future date, MAX() = year 2210). Bounded
# the commercial_where with a sanity upper bound to exclude those rather
# than trusting an unbounded date filter -- same "bad future timestamp"
# trap as TX Collin County. Real 30-day count with the bound: 17 (close
# to the ~21 estimate; small variance expected on a live dataset).
# DuPage County (IL) -- county government itself does not run a bulk
# permit feed (no Socrata/CKAN dataset found for dupageco.org, and its
# GIS open-data hub at gisdata-dupage.opendata.arcgis.com has no permits
# layer). Naperville (DuPage's largest city -- ~150K of the county's
# ~930K residents, Wheaton/Downers Grove/Elmhurst have no comparable open
# feed) publishes its own ArcGIS Hub "Building Permits" FeatureServer,
# owner org Naperville_GIS -- verified live 2026-08-02: 34,571 total
# rows, PERMITTYPE='COMMERCIAL' = 1,446 rows overall, 838 since
# 2025-01-01. Sample row confirmed real commercial data (COMM-0150-2026,
# "Interior Office- minor renovation... 5 new offices", $30,000,
# 400 <street>, Naperville). Same "largest city stands in for county"
# pattern as MI_OAKLAND_TROY_CONFIG (Troy for Oakland County).
IL_DUPAGE_NAPERVILLE_CONFIG: dict[str, Any] = {
    "state_code": "IL",
    "provider_type": "arcgis",
    "county": "DuPage",
    "city": "Naperville",
    "endpoint": "https://services1.arcgis.com/rXJ6QApc2sOtl1Pd/arcgis/rest/services/Building_Permits_View/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMITNUMBER"],
    "commercial_where": "PERMITTYPE = 'COMMERCIAL'",
    "out_fields": "PERMITNUMBER,PERMITWORKCLASS,DESCRIPTION,ISSUEDATE,PERMITSTATUS,STREETNUMBER,PREDIRECTION,STREETNAME,STREETTYPE,UNITORSUITE,CITY,STATE,POSTALCODE,PERMITVALUATION,SQUAREFEET,PERMITTYPE,APPLYDATE,TOWNSHIP",
    "date_field": "ISSUEDATE",
    # 2025-01-01 anchor per CLAUDE.md: (2026-08-02 - 2025-01-01).days
    "lookback_days": 578,
    "feed_id": "il-dupage-naperville",
    "id_field": "PERMITNUMBER",
    "name_fields": ["DESCRIPTION", "PERMITNUMBER"],
    "address_fields": ["STREETNUMBER", "PREDIRECTION", "STREETNAME", "STREETTYPE", "UNITORSUITE", "CITY"],
    "value_fields": ["PERMITVALUATION"],
    "desc_fields": ["DESCRIPTION", "PERMITWORKCLASS", "TOWNSHIP"],
    "source_url": "https://data.naperville.il.us/datasets/naperville::building-permits/about",
}

IL_COOK_CONFIG: dict[str, Any] = {
    "state_code": "IL",
    "provider_type": "socrata",
    "county": "Cook",
    "endpoint": "https://datacatalog.cookcountyil.gov/resource/6yjf-dfxs.json",
    "watermark_field": "pin",
    "hash_fields": ["local_permit_number", "permit_number", "pin"],
    "commercial_where": "job_code_primary='COMMERCIAL PERMIT' AND date_issued <= '2030-01-01T00:00:00'",
    "date_field": "date_issued",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "il-cook-assessor",
    "id_field": "local_permit_number",
    "name_fields": ["work_description", "local_permit_number"],
    "address_fields": ["property_address", "municipality"],
    "value_fields": ["amount"],
    "desc_fields": ["work_description", "municipality"],
    "source_url": "https://datacatalog.cookcountyil.gov/Property-Taxation/Cook-County-Assessor-s-Permits/6yjf-dfxs",
}

# New York City (NY's top jurisdiction by population -- spans New York,
# Kings, Queens, Bronx, Richmond counties) -- DOB NOW: Build Job Application
# Filings, verified live 2026-07-28: MAX(filing_date) = 2026-07-27 (fresh),
# 935,285 total rows. Legacy BIS dataset (ipu4-2q9a) ruled out as stale
# (MAX(issuance_date) = 2020-06-05). The trade-permit feed (rbx6-tga4,
# DOB NOW: Build Approved Permits) has no building-classification field at
# all -- this filings dataset does: building_type='Other' vs '1/2/3 Family'
# is the real commercial/residential split (mirrors the legacy BIS pattern),
# confirmed via a real GROUP BY: Other=702,095, 1 Family=91,101,
# 2 Family=100,437, 3 Family=24,044. id prefix is ny-nycdob (not ny-nyc --
# that prefix is already used by the earlier NYC Capital Projects Database
# manual-research batch, fi59-268w, a different source).
# NY-NASSAU: investigated 2026-08-02, NO VIABLE PUBLIC SOURCE -- intentionally
# not configured. Nassau County itself does not issue building permits; all
# permitting is delegated to its 3 towns / 2 cities / 64 villages, and none
# publish a bulk permit feed:
#   - data.ny.gov (Socrata): catalog search for "nassau" returns 0 permit
#     datasets (only parks/boundaries/census/MTA/fiscal items).
#   - Town of Hempstead -> OpenGov ViewPoint (hempsteadny.viewpointcloud.com).
#     SPA only; its backing API host (from the page's store3/config/environment
#     blob) is https://api-east.viewpointcloud.com/v2 and returns
#     {"errors":["forbidden"]} / HTTP 403 unauthenticated. All other services
#     are auth-gated GraphQL (records/search/inspections.viewpointcloud.com).
#   - Town of Oyster Bay -> eTRAKiT (https://oys-trk.aspgov.com/eTRAKiT/).
#     /Search/permit.aspx 302-redirects to login.aspx -- public permit search
#     requires an account; no JSON API.
#   - Town of North Hempstead -> OpenGov + Citizenserve constituent portal;
#     HTML form only, no API.
#   - ArcGIS Online / Hub: no Nassau County NY permit feature service exists
#     (search hits are Nassau County FL and unrelated Long Island layers).
# Document capture (step 10): NO. No public per-permit detail-page URL pattern
# and no attachments/documents endpoint is reachable without credentials on any
# of the above tenants. Revisit only if a town publishes an open-data portal.
NY_NYC_CONFIG: dict[str, Any] = {
    "state_code": "NY",
    "provider_type": "socrata",
    "county": "New York",
    "endpoint": "https://data.cityofnewyork.us/resource/w9ak-ipjd.json",
    "watermark_field": "job_filing_number",
    "hash_fields": ["job_filing_number"],
    # 2026-08-03: was bare "building_type='Other'" -- i.e. CITYWIDE, with
    # no borough filter, while county is hardcoded "New York". Since
    # generic_mapping takes county as a fixed per-config parameter (not
    # per-row from `borough`), every Brooklyn/Queens/Bronx/Staten Island
    # filing this config pulled was written into the corpus labelled
    # New York County (Manhattan). The NY-KINGS/NY-BRONX/NY-RICHMOND
    # sibling configs added 2026-07-31 all correctly scope by borough;
    # this one was simply never narrowed when they were split out.
    "commercial_where": "building_type='Other' AND borough='Manhattan'",
    "date_field": "filing_date",
    "lookback_days": 180,
    "feed_id": "ny-nycdob",
    "id_field": "job_filing_number",
    "name_fields": ["job_description", "job_type", "house_no", "street_name"],
    "address_fields": ["house_no", "street_name", "borough"],
    "value_fields": ["initial_cost"],
    "desc_fields": ["job_description", "job_type", "building_type"],
    "source_url": "https://data.cityofnewyork.us/Housing-Development/DOB-NOW-Build-Job-Application-Filings/w9ak-ipjd",
}

# Kings (Brooklyn), Bronx, and Richmond (Staten Island) counties -- same
# citywide DOB NOW Socrata dataset as NY_NYC_CONFIG above (w9ak-ipjd), just
# filtered to each borough via commercial_where (Socrata AND-combines this
# with the base commercial filter, confirmed by reading
# socrata_provider.py's _build_where). Added 2026-07-31: NY_NYC_CONFIG
# always wrote county="New York" (a fixed per-config string, not derived
# per-row from the borough field -- confirmed in generic_mapping.py, county
# is a passed-in parameter, not read off each row) even though the
# dataset's `borough` field has real per-borough data (live GROUP BY
# 2026-07-31: Bronx=90,621, Brooklyn=256,787, Manhattan=360,014,
# Queens=182,425, Staten Island=46,792 total rows). That's why Kings/
# Bronx/Richmond showed as no-coverage in county_coverage despite the
# citywide source already existing -- a classification/wiring gap, not a
# missing source, exactly as flagged in the task brief. feed_id is unique
# per borough (not reused from ny-nycdob) so each gets its own watermark
# and doesn't collide with the Manhattan config's incremental cursor.
NY_KINGS_CONFIG: dict[str, Any] = {
    **NY_NYC_CONFIG,
    "county": "Kings",
    "commercial_where": "building_type='Other' AND borough='Brooklyn'",
    "feed_id": "ny-nycdob-kings",
}

NY_BRONX_CONFIG: dict[str, Any] = {
    **NY_NYC_CONFIG,
    "county": "Bronx",
    "commercial_where": "building_type='Other' AND borough='Bronx'",
    "feed_id": "ny-nycdob-bronx",
}

NY_RICHMOND_CONFIG: dict[str, Any] = {
    **NY_NYC_CONFIG,
    "county": "Richmond",
    "commercial_where": "building_type='Other' AND borough='Staten Island'",
    "feed_id": "ny-nycdob-richmond",
}

# Queens was the one borough never split out when Kings/Bronx/Richmond
# were (2026-07-31) -- found 2026-08-03 during the top-50 completeness
# audit, which showed Queens (rank 13, 2.3M people) holding ONE project
# against 24,469 live commercial filings since 2025-01-01. Same shape as
# its siblings; unique feed_id so it gets its own watermark.
NY_QUEENS_CONFIG: dict[str, Any] = {
    **NY_NYC_CONFIG,
    "county": "Queens",
    "commercial_where": "building_type='Other' AND borough='Queens'",
    "feed_id": "ny-nycdob-queens",
}

# Erie County, NY (Buffalo) -- county government issues no permits (NY
# building permitting is municipal-only, confirmed by Gemini + matches
# every other NY county investigated so far). City of Buffalo's own
# Open Data Buffalo Socrata portal does have a real permits dataset
# though, verified live 2026-07-31: MAX(issued)=2026-07-30 (fresh).
# No commercial/residential boolean field -- aptype has a narrow
# 'NEW COM' bucket (338 rows total) but property_class_code (NY state
# assessment roll numeric code, 4xx=commercial) is the broader, more
# reliable classifier, confirmed via live query: 415 real rows with
# property_class_code 400-499 in the last ~90 days (issued>=2026-05-01).
NY_ERIE_BUFFALO_CONFIG: dict[str, Any] = {
    "state_code": "NY",
    "provider_type": "socrata",
    "county": "Erie",
    "endpoint": "https://data.buffalony.gov/resource/9p2d-f3yt.json",
    "watermark_field": "apno",
    "hash_fields": ["apno"],
    "commercial_where": "property_class_code between 400 and 499",
    "date_field": "issued",
    "lookback_days": 90,
    "feed_id": "ny-erie-buffalo",
    "id_field": "apno",
    "name_fields": ["aptype", "stname"],
    "address_fields": ["stname", "city", "zip"],
    "value_fields": ["value"],
    "desc_fields": ["aptype", "lictype"],
    "source_url": "https://data.buffalony.gov/Economic-Neighborhood-Development/Permits/9p2d-f3yt",
}

# Cambridge, MA (Middlesex County's top jurisdiction by construction volume --
# MA county government has no building-permit function at all, permits are
# purely municipal, no single Middlesex-wide source exists). Gemini's first
# answer gave a fabricated dataset ID (25q4-7asf, 404) -- the real one found
# via Cambridge's own Socrata catalog search is 9qm7-wbdc ("Building Permits:
# New Construction"). Verified live 2026-07-28: MAX(issue_date)=2026-07-20,
# proposed_building_use='Commercial / Mixed Use' is a real, clean commercial
# split (114 of 355 total rows). Somerville (nneb-s3f7) was also checked --
# real dataset, MAX(issue_date)=2026-07-27, but has no property-use/building-
# type field at all (just application_type='Building Permit' vs Electrical/
# Plumbing/etc, no commercial/residential split) -- skipped rather than guess
# at a keyword filter with no verified signal.
MA_CAMBRIDGE_CONFIG: dict[str, Any] = {
    "state_code": "MA",
    "provider_type": "socrata",
    "county": "Middlesex",
    "endpoint": "https://data.cambridgema.gov/resource/9qm7-wbdc.json",
    "watermark_field": "id",
    "hash_fields": ["id"],
    "commercial_where": "proposed_building_use='Commercial / Mixed Use'",
    "date_field": "issue_date",
    "lookback_days": 180,
    "feed_id": "ma-cambridge",
    "id_field": "id",
    "name_fields": ["description_of_work", "full_address"],
    "address_fields": ["full_address"],
    "value_fields": ["total_cost_of_construction", "building_cost"],
    "desc_fields": ["description_of_work", "proposed_building_use"],
    "source_url": "https://data.cambridgema.gov/Inspectional-Services/Building-Permits-New-Construction/9qm7-wbdc",
}

# City of Boston, MA (Suffolk County's only real jurisdiction -- MA county
# government has no permit function, purely municipal, same pattern as
# Cambridge/Middlesex above). CKAN platform (Analyze Boston, data.boston.gov)
# -- Gemini's answer verified live 2026-07-31: real resource_id
# 6ddcd912-32a0-43df-9908-63574f8c7e77 ("Approved Building Permits"),
# confirmed via datastore_search and datastore_search_sql. occupancytype
# is the real commercial filter -- values are inconsistent case/abbreviation
# ('Comm' 186,939 rows + 'COMM' 101 rows, also 'Mixed' 27,189), so the where
# clause covers both. MAX(issued_date)=2026-07-25T01:50:01, live and fresh.
MA_BOSTON_CONFIG: dict[str, Any] = {
    "state_code": "MA",
    "provider_type": "ckan",
    "county": "Suffolk",
    "endpoint": "https://data.boston.gov",
    "resource_id": "6ddcd912-32a0-43df-9908-63574f8c7e77",
    "watermark_field": "_id",
    "hash_fields": ["permitnumber"],
    "commercial_where": "occupancytype IN ('Comm', 'COMM', 'Mixed')",
    "date_field": "issued_date",
    "lookback_days": 90,
    "feed_id": "ma-boston",
    "id_field": "permitnumber",
    "name_fields": ["description", "worktype", "address"],
    "address_fields": ["address"],
    "value_fields": ["declared_valuation"],
    "desc_fields": ["description", "permittypedescr", "comments"],
    "source_url": "https://data.boston.gov/dataset/approved-building-permits",
}

# NOTE: Town of Brookline, MA (Norfolk County) has a live Accela portal
# (aca-prod.accela.com/BROOKLINE, module=Building loads cleanly, confirmed
# live 2026-07-31) with a real "Commercial Building" dropdown option
# (Playwright-probed #ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType,
# 27 total options). But both the automated provider (0 rows at 90-day and
# 365-day lookback) and a manual Playwright search-button click (dropdown
# resets to "--Select--" post-search, no results table) failed to return
# real data -- looks like a search-submission quirk specific to this
# deployment, not a data problem. Not wired as a config -- would need
# deeper debugging (network-tab inspection of the actual postback) beyond
# this batch's scope. Logged as FAILED_NEED_ALT in the health matrix.

# Minneapolis, MN (Hennepin County's top jurisdiction -- MN county government
# has no building-permit function, purely municipal). Gemini's first answer
# gave a fabricated ArcGIS org ID (1st35idbL2i24j8I, invalid URL) with the
# correct item GUID -- the real org ID (afSMGVsC7QlRK1kZ) found via a direct
# ArcGIS Online item-info lookup on that GUID. Verified live 2026-07-28:
# MAX(issueDate)=2026-07-27, 400,479 total rows, permitType='Commercial' is a
# real, clean commercial split (45,643 rows). Field names are camelCase
# (permitType, issueDate, applicantName) -- not the typical Title Case seen
# on most other ArcGIS configs in this file.
MN_HENNEPIN_CONFIG: dict[str, Any] = {
    "state_code": "MN",
    "provider_type": "arcgis",
    "county": "Hennepin",
    "endpoint": "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/CCS_Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["permitNumber"],
    "commercial_where": "permitType='Commercial'",
    "out_fields": "permitNumber,permitType,occupancyType,workType,status,value,comments,issueDate,Display,applicantName",
    "date_field": "issueDate",
    "lookback_days": 180,
    "feed_id": "mn-hennepin-minneapolis",
    "id_field": "permitNumber",
    "name_fields": ["comments", "occupancyType", "workType", "Display"],
    "address_fields": ["Display"],
    "value_fields": ["value"],
    "desc_fields": ["comments", "workType", "occupancyType"],
    "source_url": "https://opendata.minneapolismn.gov/datasets/CCS-Permits",
}

# Olmsted County, MN -- Rochester (the county's dominant city) has no live
# Accela search endpoint (aca.rochestermn.gov times out, unreachable). But
# Olmsted County itself DOES run its own live Accela portal at
# aca-prod.accela.com/OLMSTED (HTTP 200, confirmed live 2026-07-31) --
# covers county-administered building permits (unincorporated areas +
# townships, not Rochester city proper, per the portal's own permit-type
# taxonomy which is entirely prefixed "Building/Olmsted County/..."). No
# single "Commercial" catch-all option -- real dropdown options fetched
# directly from the live page's <select id=...ddlGSPermitType> are split
# into "Commercial Building (New Building)" / "(Addition)" / "(Alteration)"
# plus "Commercial Plumbing/Mechanical" and "Demo Permit - Commercial".
# Using "Commercial Building (New Building)" as the broadest single-label
# match the provider's select_option(label=...) API supports.
MN_OLMSTED_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "MN",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Olmsted",
    "endpoint": "https://aca-prod.accela.com/OLMSTED",
    "module": "Building",
    "permit_type_label": "Commercial Building (New Building)",
    "lookback_days": 579,
    "feed_id": "mn-olmsted-accela",
    "source_url": "https://aca-prod.accela.com/OLMSTED/Cap/CapHome.aspx?module=Building",
}

# Montgomery County, MD (state's most populous county -- unlike MA/MN/WI,
# MD county government DOES run permitting directly, so this is a genuine
# countywide source, not a top-city proxy). Verified live 2026-07-29:
# MAX(issueddate)=2026-07-24, and applicationtype is 100% 'COMMERCIAL
# BUILDING' already (2,272/2,272 rows) -- this dataset is pre-filtered to
# commercial by the county itself, no where-clause guesswork needed.
# Rockville and Gaithersburg run independent permitting outside county
# DPS jurisdiction (per Gemini, not yet verified/wired -- lower priority,
# county DPS covers the large majority of the county's incorporated area).
MD_MONTGOMERY_CONFIG: dict[str, Any] = {
    "state_code": "MD",
    "provider_type": "socrata",
    "county": "Montgomery",
    "endpoint": "https://data.montgomerycountymd.gov/resource/7ate-xrxm.json",
    "watermark_field": "permitno",
    "hash_fields": ["permitno"],
    "commercial_where": "applicationtype='COMMERCIAL BUILDING'",
    "date_field": "issueddate",
    "lookback_days": 180,
    "feed_id": "md-montgomery",
    "id_field": "permitno",
    "name_fields": ["description", "worktype", "stno", "stname"],
    "address_fields": ["stno", "stname", "suffix", "city", "state", "zip"],
    "value_fields": ["declaredvaluation"],
    "desc_fields": ["description", "worktype", "usecode"],
    "source_url": "https://data.montgomerycountymd.gov/d/7ate-xrxm",
}

# Milwaukee, WI (Milwaukee County's top jurisdiction -- WI, like MA/MN,
# has no county-level permit function, purely municipal). CKAN platform
# (6th platform type after Socrata/ArcGIS/Accela/EnerGov/CARTO/CSV --
# reused ckan_provider.py, first stood up for Santa Monica CA). Verified
# live 2026-07-29: real CKAN resource_id 828e9630-d7cb-42e4-960e-964eae916397,
# MAX("Date Issued")=2026-06-15 (monthly refresh, per the portal's own
# stated cadence), 16,685 total rows, "Permit Type" has real Commercial
# values: 'Commercial Alteration Permit' (7,512) + 'Commercial New
# Construction Permit' (745) = 8,257 real commercial rows. Field names
# contain spaces ("Permit Type", "Date Issued") -- ckan_provider.py
# inserts date_field/watermark_field literally into raw SQL, so they're
# pre-quoted with embedded double-quotes in this config rather than
# patching the provider for one source.
WI_MILWAUKEE_CONFIG: dict[str, Any] = {
    "state_code": "WI",
    "provider_type": "ckan",
    "county": "Milwaukee",
    "endpoint": "https://data.milwaukee.gov",
    "resource_id": "828e9630-d7cb-42e4-960e-964eae916397",
    "watermark_field": "_id",
    "hash_fields": ["Record ID"],
    "commercial_where": '"Permit Type" IN (\'Commercial Alteration Permit\', \'Commercial New Construction Permit\')',
    "date_field": '"Date Issued"',
    "lookback_days": 180,
    "feed_id": "wi-milwaukee",
    "id_field": "Record ID",
    "name_fields": ["Address", "Permit Type"],
    "address_fields": ["Address"],
    "value_fields": ["Construction Total Cost"],
    "desc_fields": ["Permit Type", "Use of Building"],
    "source_url": "https://data.milwaukee.gov/dataset/buildingpermits",
}

# Miami-Dade County (FL) -- verified live 2026-07-28: MAX(PermitIssuedDate)
# = 2026-07-24 (fresh), 36,944 total commercial-filtered records.
FL_MIAMIDADE_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "arcgis",
    "county": "Miami-Dade",
    "endpoint": "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/miamidade_permit_data/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PermitNumber"],
    "commercial_where": "ResidentialCommercial='C' AND ProposedUseDescription NOT LIKE '%RESIDENTIAL%'",
    "out_fields": "PermitNumber,PermitType,EstimatedValue,ApplicationTypeDescription,ProposedUseDescription,PropertyAddress,OwnerName,City,PermitIssuedDate,OBJECTID",
    "date_field": "PermitIssuedDate",
    "lookback_days": 30,
    "feed_id": "fl-miamidade",
    "id_field": "PermitNumber",
    "name_fields": ["ApplicationTypeDescription", "ProposedUseDescription", "PermitNumber"],
    "address_fields": ["PropertyAddress"],
    "value_fields": ["EstimatedValue"],
    "desc_fields": ["ProposedUseDescription", "ApplicationTypeDescription"],
    "city_fields": ["City"],
}

# 7 FL counties confirmed on Accela 2026-07-31 (live curl checks against
# aca-prod.accela.com/{code} -- domain-level only, not the DOM/dropdown
# level accela_provider.py actually needs). permit_type_label below is a
# best-guess placeholder ("Commercial"), NOT yet confirmed against each
# portal's real dropdown option text the way Palmdale/Indianapolis were
# -- every one of these MUST be run with --dry-run first to catch a
# wrong label before a real --merge-state run, same discipline as every
# other Accela config in this file.
# Fort Lauderdale's Accela deployment has no single "Commercial" catch-
# all option -- confirmed live 2026-07-31 by listing the real dropdown
# (200+ options, split by permit subtype: Commercial New Construction/
# Alteration/Addition/Demolition/Miscellaneous/Paving/Pool-Spa-Fountain
# Permit). "Commercial New Construction Permit" was tried first but is
# too narrow -- confirmed live it has zero Broward records newer than
# Dec 2023, so any lookback window returns 0 rows (not a bug, genuinely
# that rare in this specific subtype). "Commercial Alteration Permit"
# has real, current activity (confirmed live: newest record Sept 2025,
# correctly newest-first) -- using that instead. Real remaining scope:
# this single-label approach still misses Addition/Demolition/
# Miscellaneous subtypes, which can also be $5M+ projects.
FL_BROWARD_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    "county": "Broward",
    "endpoint": "https://aca-prod.accela.com/FTL",
    "module": "Permits",
    "permit_type_label": "Commercial Alteration Permit",
    "lookback_days": 579,
}

# Hillsborough (HillsGovHub) uses module=Building, not module=Permits --
# confirmed live 2026-07-31 (module=Permits 404s to an Error.aspx page).
# Real dropdown label used: "Commercial New Construction and Additions"
# (closest broad match among 18 Commercial-prefixed subtypes).
FL_HILLSBOROUGH_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Hillsborough",
    "endpoint": "https://aca-prod.accela.com/HCFL",
    "module": "Building",
    "permit_type_label": "Commercial New Construction and Additions",
    "lookback_days": 579,
}

# Pinellas uses module=Building, not Permits (module=Permits 404s to
# Error.aspx) -- confirmed live 2026-07-31, same pattern as Hillsborough.
# Real dropdown label: "Commercial Remodel/Repair/Renovation" (broadest
# of 19 Commercial-prefixed subtypes).
FL_PINELLAS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Pinellas",
    "endpoint": "https://aca-prod.accela.com/PINELLAS",
    "module": "Building",
    "permit_type_label": "Commercial Remodel/Repair/Renovation",
    "lookback_days": 579,
}

# Polk uses module=Building, not Permits -- confirmed live 2026-07-31.
# Real dropdown label: "Commercial Renovation Permit - Ex: Tenant
# Buildout, Window Changeout, Remodel, Addition, etc." (broadest of 6
# Commercial-prefixed subtypes; note the label includes trailing
# examples text, must match exactly).
FL_POLK_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Polk",
    "endpoint": "https://aca-prod.accela.com/POLKCO",
    "module": "Building",
    "permit_type_label": "Commercial Renovation Permit - Ex: Tenant Buildout, Window Changeout, Remodel, Addition, etc.",
    "lookback_days": 579,
}

FL_SARASOTA_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    "county": "Sarasota",
    "endpoint": "https://aca-prod.accela.com/SARASOTACO",
    "module": "Permits",
    "permit_type_label": "Commercial",
    "lookback_days": 579,
}

# Manatee uses module=Building, not Permits -- confirmed live 2026-07-31.
# Has a real plain "Commercial" option (unlike most other FL Accela
# deployments checked tonight, which split into named subtypes).
FL_MANATEE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    "county": "Manatee",
    "endpoint": "https://aca-prod.accela.com/MANATEE",
    "module": "Building",
    "permit_type_label": "Commercial",
    "lookback_days": 579,
}

# Pasco's module=Permits works (unlike Hillsborough/Pinellas/Polk/
# Manatee/Sarasota, which needed module=Building) -- confirmed live
# 2026-07-31. No single "Commercial" catch-all; uses a "COM - "
# prefix across ~50 granular subtypes (new construction split by wall
# material, additions, interior buildouts, etc.). Using "COM - Interior
# Build Out Including Concrete Slab" as a common, real-activity proxy --
# real remaining scope: misses new-construction subtypes entirely.
# Pasco's "COM - New Structures Constructed of Frame Walls" (tried across 2
# earlier sessions) and "COM - General Minor Repair Interior or Exterior"
# (100+ results but confirmed live 2026-07-31 to be stale, newest record
# 04/18/2024) both returned 0 rows in any recent lookback window. Live
# dropdown probe found "COM - Interior Build Out With no Change to Existing
# Slab-Remodel" instead -- confirmed live 2026-07-31, newest record
# 06/10/2026 (same-day-adjacent), real recent activity.
FL_PASCO_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Pasco",
    "endpoint": "https://aca-prod.accela.com/pasco",
    "module": "Permits",
    "permit_type_label": "COM - Interior Build Out With no Change to Existing Slab-Remodel",
    "lookback_days": 579,
}

# Lee County (FL) -- Fort Myers/Cape Coral area. Verified live 2026-07-31:
# aca-prod.accela.com/LEECO/Cap/CapHome.aspx?module=Permitting (module=
# Building 302-redirects, same recurring symptom as Lancaster CA/Omaha
# NE/Indianapolis IN -- real module name here is "Permitting"). Dropdown
# #ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType has no single
# "Commercial" catch-all; "Commercial New Building" is the broadest real
# new-construction commercial label (value
# "Permitting/Commercial/New Buildings/NA"). Gemini's claimed Fort
# Myers/Cape Coral EnerGov tenant URLs
# (fortmyersfl-energovpub.tylerhost.net, capecoralfl-energovpub.
# tylerhost.net) were both fabricated -- NXDOMAIN on curl, not pursued.
#
# KNOWN LIMITATION, verified live 2026-07-31 via direct Playwright probe
# (not just the pipeline's dry-run): search for "Commercial New Building"
# returns 100+ real rows ("Showing 1-10 of 100+", real permit numbers
# e.g. COM000806366/17050 WILLIAMS RD/STORAGE BLDG) -- the source is
# genuinely live and has real data. But the default results grid columns
# are only Record Number/Address/Description/Status/Action/Related
# Records/Submittal Type -- NO Date column at all, unlike every other
# LEECO-pattern Accela deployment wired so far. accela_provider.py's
# HEADER_ALIASES has no "date" match, so date_idx is always None and
# fetch_delta silently returns 0 rows regardless of lookback_days (same
# silent-0-row failure mode called out in the run brief, but caused here
# by a missing column rather than a wrong permit_type_label). Fixing this
# needs either an Accela "customize columns" UI flow (untested whether
# Date can be added) or per-record detail-page fetches to get a date --
# real remaining scope, not done here given time budget. Config kept
# in place (real source, real label, real module) for whoever picks this
# up next; do not run --merge-state on FL-LEE until the date-column gap
# is closed, it will merge 0 rows.
FL_LEE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    "county": "Lee",
    "endpoint": "https://aca-prod.accela.com/LEECO",
    "module": "Permitting",
    "permit_type_label": "Commercial New Building",
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "lookback_days": 579,
    "feed_id": "fl-lee",
}

# St. Lucie County (FL) -- Tyler EnerGov Citizen Self Service, tenant
# "St. Lucie County". Endpoint confirmed live 2026-07-31 (200 OK):
# stluciecountyfl-energovpub.tylerhost.net/Apps/SelfService/#/home,
# same tylerhost.net pattern as the CA EnerGov configs above.
FL_STLUCIE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "energov",
    "county": "St. Lucie",
    "endpoint": "https://stluciecountyfl-energovpub.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "St. Lucie County",
    "lookback_days": 90,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

# King County (WA) via City of Seattle's Building Permits (Socrata) --
# verified live 2026-07-28: MAX(issueddate) = 2026-07-24 (fresh), 51,673
# total commercial-filtered records.
WA_KING_CONFIG: dict[str, Any] = {
    "state_code": "WA",
    "provider_type": "socrata",
    "county": "King",
    "endpoint": "https://data.seattle.gov/resource/76t5-zqzr.json",
    "watermark_field": "permitnum",
    "hash_fields": ["permitnum"],
    "commercial_where": "permitclassmapped='Non-Residential'",
    "date_field": "issueddate",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "wa-seattle-king",
    "id_field": "permitnum",
    "name_fields": ["originaladdress1", "description", "permitnum"],
    "address_fields": ["originaladdress1"],
    "value_fields": ["estprojectcost"],
    "desc_fields": ["description", "permittypedesc"],
    "source_url": "https://data.seattle.gov/Permitting/Building-Permits/76t5-zqzr",
}

# Tarrant County (Fort Worth) -- verified live 2026-07-28: 66,848 total
# commercial-filtered records, 562 in a bounded 30-day window (exact
# match to the recommendation's estimate), MAX(File_Date) = 2026-07-28.
TX_TARRANT_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Tarrant",
    "endpoint": "https://mapit.fortworthtexas.gov/ags/rest/services/CIVIC/Permits/MapServer",
    "layer": 0,
    "watermark_field": "Unique_ID",
    "hash_fields": ["Permit_No"],
    "commercial_where": "Permit_Type LIKE '%Commercial%'",
    "out_fields": "Permit_No,Permit_Type,Permit_SubType,B1_WORK_DESC,Address,File_Date,JobValue,Current_Status,Unique_ID",
    "date_field": "File_Date",
    "date_literal_style": "timestamp",
    "lookback_days": 30,
    "feed_id": "tx-fortworth-tarrant",
    "id_field": "Permit_No",
    "name_fields": ["Address", "B1_WORK_DESC", "Permit_No"],
    "address_fields": ["Address"],
    "value_fields": ["JobValue"],
    "desc_fields": ["B1_WORK_DESC", "Permit_Type", "Current_Status"],
    "source_url": "https://mapit.fortworthtexas.gov/ags/rest/services/CIVIC/Permits/MapServer/0",
}

# Harris County, TX (Houston metro, unincorporated area -- 3rd most populous
# US county, previously zero coverage). Houston itself has its own permitting
# API (iBUILD/Houston Permitting Center) which is separate; this is the
# county's Office of the County Engineer (OCE) permits layer, not the city.
# Discovered via the county's public "OCE Permit Lookup map" ArcGIS Online
# item (org hcpid.maps.arcgis.com, owner vsalvato, item
# 2156d72fc7984f7aa4e8e23f83f5fe0b) which embeds this FeatureServer as its
# address/permit-number search source. Verified live 2026-07-31: native
# ArcGIS Server (not hosted feature service), 1.2M+ total rows, most recent
# DATECREATED = 2026-07-24 (days-old, actively updating). APPTYPE LIKE
# 'Commercial%' is the real commercial classification (distinct values seen
# include "Commercial Building (Fire Code)" vs residential-flavored types
# like "Tract Home Builders"/"Residential Construction & On-site Sewerage
# System (Septic)"); 27,742 commercial rows all-time, 5,384 since
# 2025-01-01. PERMITNUMBER (e.g. "2607220037-RESB-001") is the real
# per-record unique id, not PROJECTNUMBER (which is shared across a
# project's many permits/inspections).
TX_HARRIS_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Harris",
    "endpoint": "https://www.gis.hctx.net/arcgishcpid/rest/services/Permits/IssuedPermits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMITNUMBER"],
    "commercial_where": "APPTYPE LIKE 'Commercial%'",
    "out_fields": "OBJECTID,PROJECTNUMBER,PROJECTNAME,FULLADDRESS,APPTYPE,PROJECTSUBMITDATE,PROJECTSTATUS,PERMITNUMBER,PERMITNAME,STATUS,ISSUEDDATE,DATECREATED,PERMITCLASSCODE",
    "date_field": "DATECREATED",
    "lookback_days": 30,
    "feed_id": "tx-harris-oce",
    "id_field": "PERMITNUMBER",
    "name_fields": ["PERMITNAME", "PROJECTNAME", "PERMITNUMBER"],
    "address_fields": ["FULLADDRESS"],
    "desc_fields": ["APPTYPE", "STATUS"],
    "source_url": "https://hcpid.maps.arcgis.com/apps/instant/nearby/index.html?appid=2156d72fc7984f7aa4e8e23f83f5fe0b",
}

# Franklin County (Columbus, OH) -- verified live 2026-07-28: 139,182
# total commercial-filtered records, MAX(ISSUED_DT) = 2026-07-26.
OH_FRANKLIN_CONFIG: dict[str, Any] = {
    "state_code": "OH",
    "provider_type": "arcgis",
    "county": "Franklin",
    "endpoint": "https://services1.arcgis.com/9yy6msODkIBzkUXU/arcgis/rest/services/Building_Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["B1_ALT_ID"],
    "commercial_where": "B1_PER_TYPE LIKE '%Commercial%' OR GENERAL_TYPE LIKE '%Commercial%'",
    "out_fields": "*",
    "date_field": "ISSUED_DT",
    "lookback_days": 30,
    "feed_id": "oh-columbus-franklin",
    "id_field": "B1_ALT_ID",
    "name_fields": ["SITE_ADDRESS", "GENERAL_TYPE", "B1_ALT_ID"],
    "address_fields": ["SITE_ADDRESS"],
    "value_fields": ["G3_VALUE_TTL"],
    "desc_fields": ["GENERAL_TYPE", "B1_PER_TYPE", "VALUE_DESC"],
    "source_url": "https://services1.arcgis.com/9yy6msODkIBzkUXU/arcgis/rest/services/Building_Permits/FeatureServer/0",
}

# Cuyahoga County (Cleveland, OH) -- verified live 2026-07-28: 1,676
# total commercial-filtered records, MAX(ISSUE_DATE) = 2026-07-24.
OH_CUYAHOGA_CONFIG: dict[str, Any] = {
    "state_code": "OH",
    "provider_type": "arcgis",
    "county": "Cuyahoga",
    "endpoint": "https://services3.arcgis.com/dty2kHktVXHrqO8i/arcgis/rest/services/Building_Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMIT_ID"],
    "commercial_where": "PERMIT_CATEGORY LIKE 'Commercial%'",
    "out_fields": "*",
    "date_field": "ISSUE_DATE",
    "lookback_days": 30,
    "feed_id": "oh-cleveland-cuyahoga",
    "id_field": "PERMIT_ID",
    "name_fields": ["PRIMARY_ADDRESS", "JOB_DESCRIPTION", "PERMIT_ID"],
    "address_fields": ["PRIMARY_ADDRESS"],
    "value_fields": ["JOB_VALUE"],
    "desc_fields": ["JOB_DESCRIPTION", "PERMIT_CATEGORY", "PERMIT_TYPE"],
    "source_url": "https://services3.arcgis.com/dty2kHktVXHrqO8i/arcgis/rest/services/Building_Permits/FeatureServer/0",
}

# Mecklenburg County (Charlotte, NC) -- verified live 2026-07-28: 156,743
# total commercial-filtered records, MAX(issuedate) = 2026-07-23.
NC_MECKLENBURG_CONFIG: dict[str, Any] = {
    "state_code": "NC",
    "provider_type": "arcgis",
    "county": "Mecklenburg",
    "endpoint": "https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingPermits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["permitnum"],
    "commercial_where": "permittype = 'Commercial'",
    "out_fields": "*",
    "date_field": "issuedate",
    "lookback_days": 30,
    "feed_id": "nc-mecklenburg",
    "id_field": "permitnum",
    "name_fields": ["address", "workclass", "permitnum"],
    "address_fields": ["address"],
    "value_fields": ["estprojectcost", "value"],
    "desc_fields": ["workclass", "permittype"],
    "source_url": "https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingPermits/FeatureServer/0",
}

# Wake County (Raleigh, NC) -- verified live 2026-07-28: 47,660 total
# commercial-filtered records, MAX(issueddate) = 2026-07-24.
NC_GUILFORD_CONFIG: dict[str, Any] = {
    # City of Greensboro (largest city in Guilford County) Building Permits
    # table, published via ArcGIS Hub open data. Live-verified 2026-07-31:
    # MapServer/2 ("BI_Permits") has a clean PermitType='Commercial' value,
    # real cost/sqft/occupancy fields, and MAX(IssuedDate) = 2026-07-30 (1
    # day fresh). Guilford County itself (unincorporated + contract towns)
    # runs Tyler EnerGov Civic Access, not a queryable REST feed -- not
    # wired here, city coverage only.
    "state_code": "NC",
    "provider_type": "arcgis",
    "county": "Guilford",
    "endpoint": "https://gis.greensboro-nc.gov/arcgis/rest/services/OpenGateCity/OpenData_HRES_DS/MapServer",
    "layer": 2,
    "watermark_field": "Sakey",
    "hash_fields": ["PermitNum"],
    "commercial_where": "PermitType = 'Commercial'",
    "out_fields": "*",
    "date_field": "IssuedDate",
    "lookback_days": 90,
    "feed_id": "nc-guilford-greensboro",
    "id_field": "PermitNum",
    "name_fields": ["FullAddress", "Description", "PermitNum"],
    "address_fields": ["FullAddress"],
    "value_fields": ["TotalCost", "GeneralCost"],
    "desc_fields": ["Description", "OccupancyDesc", "TypeConstructionDesc"],
    "source_url": "https://gis.greensboro-nc.gov/arcgis/rest/services/OpenGateCity/OpenData_HRES_DS/MapServer/2",
}

# Buncombe County (Asheville, NC) -- Accela Citizen Access, agency code
# BUNCOMBECONC (confirmed via live web search + curl 2026-07-31; the
# aca-prod.accela.com/BUNCOMBE guess from Gemini's first answer 404s).
# Buncombe's county GIS FeatureServer (gis.buncombecounty.org/.../permits)
# is a dead end -- confirmed live: that MapServer's 38 layers are all
# zoning/districts/sewer/flood, no actual permit records layer. No single
# "Commercial" catch-all option on the ddlGSPermitType dropdown (same
# gotcha as other counties) -- picked "Commercial New Building"
# (Building/Commercial/New Construction/Commercial Building), the
# broadest new-construction commercial label; other Commercial-prefixed
# labels exist (Combo, Addition, Interior Alteration, etc.) if this one
# proves too narrow.
NC_BUNCOMBE_CONFIG: dict[str, Any] = {
    "state_code": "NC",
    "provider_type": "accela",
    "county": "Buncombe",
    "endpoint": "https://aca-prod.accela.com/BUNCOMBECONC",
    "permit_type_label": "Commercial Combo Permit",
    "lookback_days": 579,
}

# Cabarrus County (Concord/Kannapolis, NC) -- Accela Citizen Access,
# agency code CABARRUS. County/Concord/Kannapolis/Harrisburg all share
# this one instance (module=COC/COK/HB/Permits). module=Building 404s
# for this deployment (unlike most others) -- only module=Permits works;
# confirmed live 2026-07-31. The county's own ArcGIS server
# (location.cabarruscounty.us/arcgisservices/rest/services, real live
# host -- gis.cabarruscounty.us just redirects to a web map viewer, not
# a REST root) has a "Permits" MapServer and a "Current_Accela_Permits"
# folder, but both are dead: Permits/MapServer has 0 layers, and
# Current_Accela_Permits only exposes a Plan_Reviews sub-layer, no
# permit-issuance layer. permit_type_label='Building Commercial New',
# broadest label under Permits/Building/Commercial/*.
NC_CABARRUS_CONFIG: dict[str, Any] = {
    "state_code": "NC",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Cabarrus",
    "endpoint": "https://aca-prod.accela.com/CABARRUS",
    "module": "Permits",
    "permit_type_label": "Building Commercial New",
    "lookback_days": 579,
}

NC_WAKE_CONFIG: dict[str, Any] = {
    "state_code": "NC",
    "provider_type": "arcgis",
    "county": "Wake",
    "endpoint": "https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["permitnum"],
    "commercial_where": "permitclassmapped = 'Non-Residential'",
    "out_fields": "*",
    "date_field": "issueddate",
    "lookback_days": 30,
    "feed_id": "nc-wake",
    "id_field": "permitnum",
    "name_fields": ["projectname", "description", "permitnum"],
    "address_fields": ["streetnum", "streetname", "streettype"],
    "value_fields": ["estprojectcost"],
    "desc_fields": ["description", "proposeduse", "permitclassmapped"],
    "source_url": "https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer/0",
}

# Fairfax County (VA) -- verified live 2026-07-28: 3,494 total
# commercial-filtered records, MAX(ISSUED_DATE) = 2026-07-27.
VA_FAIRFAX_CONFIG: dict[str, Any] = {
    "state_code": "VA",
    "provider_type": "arcgis",
    "county": "Fairfax",
    "endpoint": "https://www.fairfaxcounty.gov/lambert/rest/services/LDS/DevelopmentTracker/FeatureServer",
    "layer": 5,
    "watermark_field": "OBJECTID",
    "hash_fields": ["RECORDID"],
    "commercial_where": "APPTYPEALIAS IN ('Commercial New','Commercial Addition/Alteration')",
    "out_fields": "RECORDID,APPTYPEALIAS,PROJECT_NAME,ESTIMATED_COST,ADDRESS_1,CITY,ISSUED_DATE,OBJECTID",
    "date_field": "ISSUED_DATE",
    "date_literal_style": "timestamp",
    "lookback_days": 30,
    "feed_id": "va-fairfax",
    "id_field": "RECORDID",
    "name_fields": ["PROJECT_NAME", "RECORDID"],
    "address_fields": ["ADDRESS_1"],
    "value_fields": ["ESTIMATED_COST"],
    "desc_fields": ["APPTYPEALIAS", "PROJECT_NAME"],
    "city_fields": ["CITY"],
    "source_url": "https://www.fairfaxcounty.gov/lambert/rest/services/LDS/DevelopmentTracker/FeatureServer/5",
}

# Arlington County (VA) -- verified live 2026-07-31: Arlington County GIS
# "Development Tracking Points" layer, 19,930 total records, 1,136 with
# office/retail SF > 0 (non-residential), MAX(site_plan_date) = 2026-06-13.
# Low volume in any 90-day window (only 2 records with a recent
# site_plan_date) -- a genuine curated development tracker, not a
# high-frequency permit feed, same pattern as other low-volume trackers
# already in the corpus (e.g. CA-Torrance).
VA_ARLINGTON_CONFIG: dict[str, Any] = {
    "state_code": "VA",
    "provider_type": "arcgis",
    "county": "Arlington",
    "endpoint": "https://arlgis.arlingtonva.us/arcgis/rest/services/Open_Data/od_Development_Tracking_Points/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["development_project_id"],
    "commercial_where": "(office_square_feet_qty > 0 OR retail_square_feet_qty > 0)",
    "out_fields": "*",
    "date_field": "site_plan_date",
    "date_literal_style": "timestamp",
    "lookback_days": 90,
    "feed_id": "va-arlington",
    "id_field": "development_project_id",
    "name_fields": ["development_project_name", "development_project_address_tex"],
    "address_fields": ["development_project_address_tex", "street_display_name"],
    "value_fields": ["office_square_feet_qty", "retail_square_feet_qty"],
    "desc_fields": ["status_dsc", "general_land_use_plan_dsc", "zoning_type_dsc"],
    "source_url": "https://arlgis.arlingtonva.us/arcgis/rest/services/Open_Data/od_Development_Tracking_Points/FeatureServer/0",
}

# Williamson County (TX) -- a SECOND, different feed from the existing
# TX_WILLIAMSON_CONFIG (Site_Development/FeatureServer layer 47, org
# L0MLvN0Ay0iEjnCT). This one is a different org/dataset entirely
# (Permits/FeatureServer, org 0H6bQdxd9223gQB5) -- verified live
# 2026-07-28: 3,812 total commercial-filtered records, MAX(ApplyDate) =
# 2026-07-28. Kept as a separate state key rather than merged/replaced
# since both are real, live, and cover different record types.
TX_WILLIAMSON_PERMITS_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "arcgis",
    "county": "Williamson",
    "endpoint": "https://services.arcgis.com/0H6bQdxd9223gQB5/arcgis/rest/services/Permits/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PermitNumber"],
    "commercial_where": "PermitWorkClass LIKE 'Commercial%'",
    "out_fields": "*",
    "date_field": "ApplyDate",
    "lookback_days": 30,
    "feed_id": "tx-williamson",
    "id_field": "PermitNumber",
    "name_fields": ["Address", "PermitWorkClass", "PermitNumber"],
    "address_fields": ["Address"],
    "value_fields": ["Valuation"],
    "desc_fields": ["PermitWorkClass", "PermitType"],
    "source_url": "https://services.arcgis.com/0H6bQdxd9223gQB5/arcgis/rest/services/Permits/FeatureServer/0",
}

# Philadelphia County (PA) -- CARTO SQL API (phl.carto.com), a new
# platform type (core/ingestion/carto_provider.py). Verified live
# 2026-07-28: 130 rows in a bounded 30-day window (exact match to the
# recommendation's estimate), MAX(permitissuedate) = 2026-07-27.
# `commercialorresidential` is a known-unreliable field on this dataset
# (asif-test playbook note) -- filters on approvedscopeofwork keywords
# instead, explicitly excluding household-living/dwelling scope text.
PA_PHILADELPHIA_CONFIG: dict[str, Any] = {
    "state_code": "PA",
    "provider_type": "carto",
    "county": "Philadelphia",
    "endpoint": "https://phl.carto.com/api/v2/sql",
    "table": "permits",
    "select_fields": "permitnumber, address, permitissuedate, approvedscopeofwork, typeofwork",
    "where_sql": (
        "(upper(approvedscopeofwork) LIKE '%RETAIL%' OR upper(approvedscopeofwork) LIKE '%OFFICE%' "
        "OR upper(approvedscopeofwork) LIKE '%WAREHOUSE%' OR upper(approvedscopeofwork) LIKE '%HOTEL%' "
        "OR upper(approvedscopeofwork) LIKE '%RESTAURANT%' OR upper(approvedscopeofwork) LIKE '%COMMERCIAL%' "
        "OR upper(approvedscopeofwork) LIKE '%INDUSTRIAL%' OR upper(approvedscopeofwork) LIKE '%MEDICAL%') "
        "AND upper(coalesce(approvedscopeofwork,'')) NOT LIKE '%HOUSEHOLD LIVING%' "
        "AND upper(coalesce(approvedscopeofwork,'')) NOT LIKE '%DWELLING%'"
    ),
    "date_field": "permitissuedate",
    "lookback_days": 30,
    "hash_fields": ["permitnumber"],
    "feed_id": "pa-philadelphia",
    "id_field": "permitnumber",
    "name_fields": ["address", "typeofwork", "permitnumber"],
    "address_fields": ["address"],
    "desc_fields": ["approvedscopeofwork", "typeofwork"],
    "source_url": "https://phl.carto.com/api/v2/sql",
}

# San Diego County/City (CA) -- flat CSV download, new provider type
# (core/ingestion/csv_download_provider.py). The county-level Socrata
# catalog entries (dyzh-7eat, eqjy-uqyj) were both dead ends (stale
# since 2023 / no usable fields) -- this is the CITY of San Diego's
# separate, actively-maintained open-data pipeline instead, found by
# checking data.sandiego.gov/datasets/development-permits/ directly
# (a Gemini/Vertex lead named the URL generically but couldn't browse
# it; the real dataset had to be found and verified live by hand).
# Verified live 2026-07-28: last-modified today, MAX(APPROVAL_ISSUE_DATE)
# = 2026-07-27, 440 commercial-filtered rows in a real 30-day window.
# JOB_BC_CODE_DESCRIPTION is empty on ~74% of rows (residential permit
# types dominate the other 26%) -- filtered via include/exclude keyword
# match on that field rather than a hard exact-match list, since the
# real category text varies (e.g. "Add/Alt Tenant Improvements",
# "ACC STRUCT- NON RES", "Demo of NonRes Buildings").
# NOTE: points at the year-specific 2026 file (15.9MB) rather than the
# all-years file (590MB, too large to re-download every run) --
# needs a URL bump to approvals_issued_2027_datasd.csv in January.
CA_SANDIEGO_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "csv",
    "county": "San Diego",
    "endpoint": "https://seshat.datasd.org/development_permits/approvals_issued_2026_datasd.csv",
    "date_field": "APPROVAL_ISSUE_DATE",
    "filter_field": "JOB_BC_CODE_DESCRIPTION",
    "include_keywords": [
        "tenant improvement", "non res", "nonres", "commercial",
        "office", "retail", "warehouse", "industrial", "hotel", "restaurant",
    ],
    "exclude_keywords": ["1 or 2 fam", "companion unit", "acc apt", "family apt", "pool or spa"],
    "lookback_days": 30,
    "hash_fields": ["APPROVAL_ID"],
    "feed_id": "ca-sandiego",
    "id_field": "APPROVAL_ID",
    "name_fields": ["PROJECT_TITLE", "JOB_BC_CODE_DESCRIPTION", "APPROVAL_ID"],
    "address_fields": ["GIS_ADDRESS"],
    "value_fields": ["APPROVAL_VALUATION"],
    "desc_fields": ["PROJECT_SCOPE", "JOB_BC_CODE_DESCRIPTION"],
    "source_url": "https://data.sandiego.gov/datasets/development-permits/",
}

# San Francisco DataSF Socrata dataset i98e-djp9 -- confirmed live
# 2026-07-29: 1,292,835 total rows, real addresses/lat-lon/estimated_cost.
# No single "Commercial" flag exists (unlike LA's permit_sub_type) --
# proposed_use is a flat freeform category list dominated by residential
# terms ('1 family dwelling', 'apartments', '2 family dwelling' are the
# top 3 by volume), so this excludes the clearly-residential/non-project
# categories rather than trying to enumerate every commercial one.
# Recommended by Gemini search-grounded discovery (data/gemini_sessions/
# ca_coverage_review.json) after confirming CA has no statewide permit
# aggregator (58 counties + 482 cities, all fragmented vendor portals) --
# ranked SF #1 by construction economic volume among CA jurisdictions not
# yet wired.
CA_SANFRANCISCO_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "socrata",
    "county": "San Francisco",
    "endpoint": "https://data.sfgov.org/resource/i98e-djp9.json",
    # NOT permit_number: this dataset mixes two incompatible formats --
    # legacy short IDs like "7804170S" (pre-date-prefix era, no leading
    # digit ordering relationship to the modern scheme) and modern
    # 12-digit date-prefixed ids like "202607275627". Confirmed live
    # 2026-07-29: with permit_number as watermark, the incremental cursor
    # gets permanently stuck -- next_watermark()'s int-cast comparison
    # (socrata_provider.py) picks the numerically-largest *parseable* id
    # seen, but a legacy 7-digit id like "8005502" is numerically smaller
    # than a modern 12-digit one even though Socrata's naive string `>`
    # filter treats it as "greater" (since '8' > '2' lexicographically) --
    # so every subsequent run re-fetches the exact same already-merged
    # batch of legacy rows forever and the watermark never advances again.
    # permit_creation_date is a real timestamp -- genuinely monotonic both
    # for the SoQL `>` filter and for next_watermark()'s comparison logic
    # (which falls back to "always rescan the lookback window" for a
    # non-numeric field, same documented-safe behavior as Cook County's
    # `pin`, not the newer bug this field format triggers).
    "watermark_field": "permit_creation_date",
    "hash_fields": ["permit_number"],
    # proposed_use excludes the residential categories (no clean single
    # "Commercial" flag exists here, unlike LA). permit_type excludes 8
    # ("otc alterations permit", 971,939 of ~1.29M total rows -- same-day
    # minor fixes) and 7/4 (signs). estimated_cost floor of $100K keeps
    # this to real construction-scale work -- unfiltered, this feed's
    # median row is a $1-$900 placeholder-cost filing, confirmed live
    # 2026-07-29. estimated_cost is stored as SoQL text, hence the
    # ::number cast.
    "commercial_where": (
        "proposed_use NOT IN ("
        "'1 family dwelling', '2 family dwelling', 'apartments', "
        "'vacant lot', 'not applicable', 'misc group residns.'"
        ") AND proposed_use IS NOT NULL "
        "AND permit_type NOT IN ('8', '7', '4') "
        "AND estimated_cost::number >= 100000"
    ),
    "date_field": "permit_creation_date",
    "lookback_days": 30,
    "feed_id": "ca-sanfrancisco-dbi",
    "id_field": "permit_number",
    # No pre-combined address column in this feed (street_number/
    # street_name/street_suffix are separate) -- join_address_fields=True
    # makes address_fields concatenate instead of the usual first-match
    # semantics, and "__ADDRESS__" reuses that joined string as the
    # project name too (see generic_mapping.py). Also single-city-scoped
    # with no city column at all, hence default_city.
    "name_fields": ["__ADDRESS__"],
    "address_fields": ["street_number", "street_name", "street_suffix"],
    "join_address_fields": True,
    "default_city": "San Francisco",
    "value_fields": ["estimated_cost"],
    "desc_fields": ["description", "proposed_use", "permit_type_definition"],
    "source_url": "https://data.sfgov.org/Housing-and-Buildings/Building-Permits/i98e-djp9",
}

# Marin County (unincorporated + all cities/towns, county-run building
# permit system) -- Socrata dataset mkbn-caye, verified live 2026-07-31.
# Clean type_permit='COMMERCIAL' flag (only two values: COMMERCIAL/
# RESIDENTIAL). MAX(issued_date)=2026-07-30 (fresh, updated same-day), 85
# real commercial rows with issued_date > 2026-05-01 alone. city_town
# field covers Novato/San Rafael/Mill Valley/Sausalito/etc, so this is
# genuinely countywide, not one city.
# City of Antioch (Contra Costa County's 3rd-largest city, ~115K pop) --
# Tyler EnerGov, same tylerhost.net/apps/selfservice pattern as El Monte.
# Live-verified 2026-07-31: aca-prod.accela.com/CCCOUNTY (county itself)
# 404s (wrong agency code, no working variant found), aca-prod.accela.com/
# CCC redirects to a login-gated instance (dead end, no public access
# without an account), and aca-prod.accela.com/CONCORD (largest city,
# 2nd-largest in county) is a live 200 Accela instance but its Building
# module search UI has no ddlGSPermitType commercial-catchall dropdown at
# all (grep for "commercial"/"ddlGSPermitType" on both the landing page
# and post-search HTML returned zero hits) -- default "Search" returns a
# flat "Building" record-type list mixing residential (water heaters,
# reroofs) and commercial permits with no clean filter, so Concord was not
# wired to avoid the "wrong label -> silent 0-row" and "unfiltered ->
# mostly-residential noise" failure modes this doc warns about. Antioch's
# EnerGov endpoint (https://antiochca-energovweb.tylerhost.net) returned a
# live 200; wired via the existing generic EnerGov provider (same as El
# Monte/Alhambra/Carson) rather than a bespoke Accela integration.
CA_ANTIOCH_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "energov",
    "county": "Contra Costa",
    "endpoint": "https://antiochca-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Antioch",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}

CA_MARIN_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "socrata",
    "county": "Marin",
    "endpoint": "https://data.marincounty.gov/resource/mkbn-caye.json",
    "watermark_field": "permit_tracking_id",
    "hash_fields": ["permit_tracking_id"],
    "commercial_where": "type_permit='COMMERCIAL'",
    "date_field": "issued_date",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "ca-marin-building",
    "id_field": "permit_tracking_id",
    "name_fields": ["address", "description", "construction"],
    "address_fields": ["address"],
    "value_fields": ["construction_value"],
    "desc_fields": ["description", "construction", "permit_category"],
    "source_url": "https://data.marincounty.gov/Property-Land-Management/Building-Permit/mkbn-caye",
}

# City of Pittsburgh (Allegheny County) -- PA's only wired source before
# this was Philadelphia (1,799 total PA records for the 5th-largest US
# state; PA's Uniform Construction Code puts permitting at the municipal
# level, so no county-wide feed exists, same reasoning as CA). Recommended
# by Gemini search-grounded discovery (data/gemini_sessions/
# pa_coverage_review.json) after confirming Pittsburgh is the biggest
# unwired PA jurisdiction. WPRDC (Western PA Regional Data Center) CKAN
# platform, 7th platform type this codebase has used. Verified live
# 2026-07-29: resource_id f4d1177a-f597-4c32-8cbf-7885f56253f6, 63,856
# total rows, clean commercial_or_residential field -- 24,027 real
# commercial rows, MAX(issue_date)=2026-07-28 (fresh, updated daily per
# the portal).
PA_PITTSBURGH_CONFIG: dict[str, Any] = {
    "state_code": "PA",
    "provider_type": "ckan",
    "county": "Allegheny",
    "endpoint": "https://data.wprdc.org",
    "resource_id": "f4d1177a-f597-4c32-8cbf-7885f56253f6",
    "watermark_field": "_id",
    "hash_fields": ["permit_id"],
    "commercial_where": "commercial_or_residential = 'Commercial'",
    "date_field": "issue_date",
    "lookback_days": 180,
    "feed_id": "pa-pittsburgh-pli",
    "id_field": "permit_id",
    "name_fields": ["address", "work_description", "permit_type"],
    "address_fields": ["address"],
    "value_fields": ["total_project_value"],
    "desc_fields": ["work_description", "work_type"],
    "source_url": "https://data.wprdc.org/dataset/pli-permits",
}

# Riverside County (10th most populous US county), TLMA's countywide PLUS
# (Public Land Use System) layer -- discovered 2026-07-31 via
# gisopendata-countyofriverside.opendata.arcgis.com's dcat feed, real
# ArcGIS REST endpoint on gis.countyofriverside.us (copyrightText "RCIT" =
# Riverside County IT, the county's own GIS server, not a third party).
# 2.14M total rows across CODE/PERMIT/PLAN modules; CASE_MODULE='PERMIT'
# plus a CASE_TYPE/CASE_WORK_CLASS filter (COMMERCIAL BUILDINGS (BNR),
# TENANT IMPROVEMENT (BTI), FIRE COMMERCIAL (FPCBP), and any
# CASE_WORK_CLASS containing COMMERCIAL/INDUSTRIAL, e.g. "ACOM - ADDITION
# TO COMMERCIAL BUILDING") is the real commercial split -- verified live,
# 48,850 matching rows with APPLIED_DATE >= 2025-01-01. No street-address
# field exists on this layer -- APN (assessor parcel number) is the only
# per-row location identifier, used as address_fields despite being a
# weaker proxy than other configs' real street addresses.
CA_RIVERSIDE_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Riverside",
    "endpoint": "https://gis.countyofriverside.us/arcgis_mapping/rest/services/OpenData/General/MapServer",
    "layer": 280,
    "watermark_field": "OBJECTID",
    "hash_fields": ["CASE_ID"],
    "commercial_where": (
        "CASE_MODULE='PERMIT' AND ("
        "CASE_TYPE LIKE '%COMMERCIAL%' OR "
        "CASE_TYPE='TENANT IMPROVEMENT (BTI)' OR "
        "CASE_WORK_CLASS LIKE '%COMMERCIAL%' OR "
        "CASE_WORK_CLASS LIKE '%INDUSTRIAL%'"
        ")"
    ),
    "out_fields": (
        "OBJECTID,APN,CASE_ID,CASE_DESCR,CASE_MODULE,CASE_TYPE,"
        "CASE_WORK_CLASS,DEPARTMENT,CASE_STATUS,APPLIED_DATE,"
        "APPROVED_DATE,COMPLETED_DATE,SUBDIVISION_NAME,BUILDING_COUNT,"
        "UNIT_COUNT,FLOOR_COUNT"
    ),
    "date_field": "APPLIED_DATE",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "ca-riverside-tlma",
    "id_field": "CASE_ID",
    "name_fields": ["CASE_DESCR", "CASE_TYPE"],
    "address_fields": ["APN"],
    "value_fields": [],
    "desc_fields": ["CASE_DESCR", "CASE_WORK_CLASS"],
    "source_url": "https://gisopendata-countyofriverside.opendata.arcgis.com/datasets/CountyofRiverside::permits",
}

STATE_CONFIGS: dict[str, dict[str, Any]] = {
    "NJ": NJ_CONFIG,
    "CA-LOSANGELES": CA_LOSANGELES_CONFIG,
    "CA-LACOUNTY": CA_LACOUNTY_CONFIG,
    "CA-RIVERSIDE": CA_RIVERSIDE_CONFIG,
    "CA-TORRANCE": CA_TORRANCE_CONFIG,
    "CA-PASADENA": CA_PASADENA_CONFIG,
    "CA-SANTAMONICA": CA_SANTAMONICA_CONFIG,
    "CA-PALMDALE": CA_PALMDALE_ACCELA_CONFIG,
    "CA-LONGBEACH": CA_LONGBEACH_CONFIG,
    "CA-DOWNEY": CA_DOWNEY_ACCELA_CONFIG,
    "CA-LANCASTER": CA_LANCASTER_ACCELA_CONFIG,
    "CA-ELMONTE": CA_ELMONTE_ENERGOV_CONFIG,
    "CA-GLENDALE": CA_GLENDALE_ENERGOV_CONFIG,
    "CA-ALHAMBRA": CA_ALHAMBRA_ENERGOV_CONFIG,
    "CA-CARSON": CA_CARSON_ENERGOV_CONFIG,
    "CA-VENTURA": CA_VENTURA_CONFIG,
    # "CA-POMONA" intentionally not registered yet -- see
    # _CA_POMONA_ENERGOV_CONFIG comment above.
    "AZ-MARICOPACOUNTY": AZ_MARICOPACOUNTY_CONFIG,
    "AZ-MESA": AZ_MESA_CONFIG,
    "AZ-SCOTTSDALE": AZ_SCOTTSDALE_CONFIG,
    "AZ-PIMACOUNTY": AZ_PIMACOUNTY_ACCELA_CONFIG,
    "TX-JEFFERSON": TX_JEFFERSON_CONFIG,
    "TX-ECTOR": TX_ECTOR_CONFIG,
    "TX-DALLAS-NEW": TX_DALLAS_NEW_ACCELA_CONFIG,
    "TX-DALLAS-ALT": TX_DALLAS_ALT_ACCELA_CONFIG,
    "TX-WILLIAMSON": TX_WILLIAMSON_CONFIG,
    "MI-WAYNE": MI_WAYNE_CONFIG,
    "MI-KENT": MI_KENT_CONFIG,
    "MI-OAKLAND": MI_OAKLAND_TROY_CONFIG,
    "IL-COOK": IL_COOK_CONFIG,
    "IL-DUPAGE": IL_DUPAGE_NAPERVILLE_CONFIG,
    "NY-NYC": NY_NYC_CONFIG,
    "NY-KINGS": NY_KINGS_CONFIG,
    "NY-BRONX": NY_BRONX_CONFIG,
    "NY-RICHMOND": NY_RICHMOND_CONFIG,
    "NY-QUEENS": NY_QUEENS_CONFIG,
    "NY-ERIE-BUFFALO": NY_ERIE_BUFFALO_CONFIG,
    "MA-CAMBRIDGE": MA_CAMBRIDGE_CONFIG,
    "MA-BOSTON": MA_BOSTON_CONFIG,
    "MN-HENNEPIN": MN_HENNEPIN_CONFIG,
    "MN-OLMSTED": MN_OLMSTED_ACCELA_CONFIG,
    "UT-SALTLAKE": UT_SALTLAKE_ACCELA_CONFIG,
    "MD-MONTGOMERY": MD_MONTGOMERY_CONFIG,
    "WI-MILWAUKEE": WI_MILWAUKEE_CONFIG,
    "MO-STLOUIS": MO_STLOUIS_ACCELA_CONFIG,
    "GA-ATLANTA": GA_ATLANTA_ACCELA_CONFIG,
    "KY-JEFFERSON": KY_JEFFERSON_CONFIG,
    "OR-MULTNOMAH": OR_MULTNOMAH_CONFIG,
    "NM-BERNALILLO": NM_BERNALILLO_ACCELA_CONFIG,
    "NE-DOUGLAS": NE_DOUGLAS_ACCELA_CONFIG,
    "LA-EBR": LA_EBR_CONFIG,
    "SC-GREENVILLE": SC_GREENVILLE_CONFIG,
    "SC-RICHLAND": SC_COLUMBIA_ENERGOV_CONFIG,
    "SC-SPARTANBURG": SC_SPARTANBURG_ENERGOV_CONFIG,
    "ID-ADA": ID_ADA_ACCELA_CONFIG,
    "SD-SIOUXFALLS": SD_SIOUXFALLS_CONFIG,
    "IN-INDIANAPOLIS": IN_INDIANAPOLIS_ACCELA_CONFIG,
    "IN-CROWNPOINT": IN_CROWNPOINT_ENERGOV_CONFIG,
    "IN-ALLEN": IN_ALLEN_ACCELA_CONFIG,
    "IN-NOBLESVILLE": IN_NOBLESVILLE_ENERGOV_CONFIG,
    "FL-MIAMIDADE": FL_MIAMIDADE_CONFIG,
    "FL-BROWARD": FL_BROWARD_ACCELA_CONFIG,
    "FL-HILLSBOROUGH": FL_HILLSBOROUGH_ACCELA_CONFIG,
    "FL-PINELLAS": FL_PINELLAS_ACCELA_CONFIG,
    "FL-POLK": FL_POLK_ACCELA_CONFIG,
    "FL-SARASOTA": FL_SARASOTA_ACCELA_CONFIG,
    "FL-MANATEE": FL_MANATEE_ACCELA_CONFIG,
    "FL-PASCO": FL_PASCO_ACCELA_CONFIG,
    "FL-LEE": FL_LEE_ACCELA_CONFIG,
    "FL-STLUCIE": FL_STLUCIE_ENERGOV_CONFIG,
    "WA-KING": WA_KING_CONFIG,
    "TX-TARRANT": TX_TARRANT_CONFIG,
    "TX-HARRIS": TX_HARRIS_CONFIG,
    "OH-FRANKLIN": OH_FRANKLIN_CONFIG,
    "OH-CUYAHOGA": OH_CUYAHOGA_CONFIG,
    "NC-MECKLENBURG": NC_MECKLENBURG_CONFIG,
    "NC-WAKE": NC_WAKE_CONFIG,
    "NC-GUILFORD": NC_GUILFORD_CONFIG,
    "NC-BUNCOMBE": NC_BUNCOMBE_CONFIG,
    "NC-CABARRUS": NC_CABARRUS_CONFIG,
    "VA-FAIRFAX": VA_FAIRFAX_CONFIG,
    # TX-WILLIAMSON-PERMITS removed 2026-08-03: it pointed at the SAME
    # endpoint/layer/filter as TX-MIDLAND (services.arcgis.com/0H6bQdxd.../
    # Permits/FeatureServer/0) with no geographic discriminator, so it
    # pulled Midland's feed and stamped every row "Williamson". The service
    # description says so outright: "permit requests/applications across all
    # of Midland, Texas". Confirmed by tracing corpus row
    # tx-williamson-com26-000002815 back to PermitNumber COM26-000002815 in
    # the Midland service. 110 corpus rows were relabelled to Midland.
    # Williamson County's real source is TX-WILLIAMSON (a different host).
    "VA-ARLINGTON": VA_ARLINGTON_CONFIG,
    "PA-PHILADELPHIA": PA_PHILADELPHIA_CONFIG,
    "PA-PITTSBURGH": PA_PITTSBURGH_CONFIG,
    "CA-SANDIEGO": CA_SANDIEGO_CONFIG,
    "CA-SANFRANCISCO": CA_SANFRANCISCO_CONFIG,
    "CA-MARIN": CA_MARIN_CONFIG,
    "CA-ANTIOCH": CA_ANTIOCH_ENERGOV_CONFIG,
    "OK-OKLAHOMA": OK_OKLAHOMA_ACCELA_CONFIG,
    "TX-BRAZORIA": TX_BRAZORIA_CONFIG,
    "TX-MIDLAND": TX_MIDLAND_CONFIG,
    "TX-HAYS": TX_HAYS_CONFIG,
    "TX-COMAL": TX_COMAL_CONFIG,
    "TX-GUADALUPE": TX_GUADALUPE_CONFIG,
    "TX-SMITH": TX_SMITH_CONFIG,
    "TX-BELL": TX_BELL_CONFIG,
    "TX-MCALLEN": TX_MCALLEN_ACCELA_CONFIG,
    "TX-BROWNSVILLE": TX_BROWNSVILLE_ACCELA_CONFIG,
    "GA-SAM": GA_SAM_CONFIG,
    "GA-USASPENDING": GA_USASPENDING_CONFIG,
    "GA-GWINNETT": GA_GWINNETT_ACCELA_CONFIG,
    "TX-ELPASO": TX_ELPASO_ACCELA_CONFIG,
    "TX-SANANTONIO": TX_SANANTONIO_ACCELA_CONFIG,
}

# City of San Antonio (Bexar County) -- TX_SANANTONIO_ACCELA_CONFIG above
# only ever captured one of 19 real commercial permit-type categories
# ("Commercial New Building Permit"). Found while investigating why a
# Gemini-suggested Bexar County lead turned out to be a dead end (the
# county's own permit process, outside municipal limits, is a manual
# Fire-Marshal paper-form review -- not a digital portal; the real
# activity is in the City of San Antonio, which was already wired but
# thin). Live-probed the other 18 dropdown categories 2026-07-28;
# real 30-day volume: Addition 5, Finish Out 14, Remodel 73, Sitework
# 37, Project Application 221 (likely the umbrella application type
# many projects route through first) -- Shell had 0 and wasn't added.
# Other lower-signal categories (Fence, Monument, Pad Site, Drive-Thru,
# Ice-Teller Machine, etc.) not probed -- narrow/niche categories,
# unlikely to carry meaningful commercial-construction volume.
TX_SANANTONIO_ADDITION_CONFIG: dict[str, Any] = {
    **TX_SANANTONIO_ACCELA_CONFIG,
    "permit_type_label": "Commercial Addition Permit",
}
TX_SANANTONIO_FINISHOUT_CONFIG: dict[str, Any] = {
    **TX_SANANTONIO_ACCELA_CONFIG,
    "permit_type_label": "Commercial Finish Out Permit",
}
TX_SANANTONIO_REMODEL_CONFIG: dict[str, Any] = {
    **TX_SANANTONIO_ACCELA_CONFIG,
    "permit_type_label": "Commercial Remodel Permit",
}
TX_SANANTONIO_SITEWORK_CONFIG: dict[str, Any] = {
    **TX_SANANTONIO_ACCELA_CONFIG,
    "permit_type_label": "Commercial Sitework Permit",
}
TX_SANANTONIO_PROJAPP_CONFIG: dict[str, Any] = {
    **TX_SANANTONIO_ACCELA_CONFIG,
    "permit_type_label": "Commercial Project Application",
}

STATE_CONFIGS["TX-SANANTONIO-ADDITION"] = TX_SANANTONIO_ADDITION_CONFIG
STATE_CONFIGS["TX-SANANTONIO-FINISHOUT"] = TX_SANANTONIO_FINISHOUT_CONFIG
STATE_CONFIGS["TX-SANANTONIO-REMODEL"] = TX_SANANTONIO_REMODEL_CONFIG
STATE_CONFIGS["TX-SANANTONIO-SITEWORK"] = TX_SANANTONIO_SITEWORK_CONFIG
STATE_CONFIGS["TX-SANANTONIO-PROJAPP"] = TX_SANANTONIO_PROJAPP_CONFIG

# TDLR TABS -- statewide Texas commercial-construction registry (>=$50k
# projects, Texas Architectural Barriers requirement), found 2026-07-28
# while chasing Harris County dead ends. Verified live: fully stateless
# (no Playwright needed, unlike every other provider this session),
# 339,076 total records, 66,749 in Harris County alone, 353 in a real
# 30-day statewide-vs-Harris test window. Unlike every other config
# here, this one is NOT scoped to a single county -- county_code is
# omitted so it pulls ALL Texas counties in one run, with each row's
# real county attributed from its own County code via a live-fetched
# lookup table (see tdlr_tabs_provider.py).
TX_TDLR_TABS_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "tdlr_tabs",
    "county_code": None,
    "lookback_days": 30,
    "page_size": 100,
    "max_pages": 200,
}
STATE_CONFIGS["TX-TDLR-TABS"] = TX_TDLR_TABS_CONFIG

# Colorado Springs (El Paso County, CO) -- Accela agency code COSPRINGS,
# confirmed live 2026-07-28. Note: the region's PRIMARY building-permit
# authority is actually the Pikes Peak Regional Building Department
# (PPRBD, pprbd.org, covers both Colorado Springs and unincorporated El
# Paso County) -- its real search form has excellent commercial filters
# (ProjectType: New/Alt/CO Commercial, a built-in "Last 30 Days" range)
# but submission is blocked by a real Cloudflare Turnstile CAPTCHA
# ("Please complete the security check below to verify you are human")
# -- not pursued, same category as this session's earlier Compton
# dead-end (CAPTCHA/anti-bot-evasion tooling is out of scope regardless
# of legitimate purpose). This Accela instance only has ONE permit type
# in its dropdown ("Building Permit Review", no commercial/residential
# split) -- Gemini's own description turned out accurate here: COSPRINGS's
# Accela is for Planning/Public Works/Fire/Stormwater, not the primary
# building-permit channel. Live-verified anyway: 110 rows in 30 days,
# 105 real ("Commercial building permit." descriptions with real
# BLDREV-YY-NNNNN case numbers), 5 administrative noise (re-inspection
# fee records) -- good enough ratio to keep without building new
# content-filtering infrastructure for 5 records.
CO_SPRINGS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "accela",
    "county": "El Paso",
    "endpoint": "https://aca-prod.accela.com/COSPRINGS",
    "permit_type_label": "Building Permit Review",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-SPRINGS"] = CO_SPRINGS_ACCELA_CONFIG

# City and County of Denver, CO (state's #1 county by population) --
# Accela agency code DENVER, confirmed live 2026-07-30 (200 on
# aca-prod.accela.com/DENVER). NOTE: module=Building 404s to Error.aspx
# here (unlike most deployments) -- Denver's real module name is
# "Development" (found via nav-link probe: CapHome.aspx?module=
# Development&TabName=Home). The permit-type dropdown has a genuine
# single catch-all commercial option, "Commercial Construction Permit"
# (distinct from Electrical/Mechanical/Plumbing/Roofing/Residential
# Construction Permit etc. in the same dropdown), so no subtype
# fan-out needed.
CO_DENVER_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "accela",
    "county": "Denver",
    "endpoint": "https://aca-prod.accela.com/DENVER",
    "module": "Development",
    "permit_type_label": "Commercial Construction Permit",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-DENVER"] = CO_DENVER_ACCELA_CONFIG

# Adams County, CO (unincorporated; state's #4 county by population) --
# Accela agency code ADAMSCO, confirmed live 2026-07-31 (200 on
# aca-prod.accela.com/ADAMSCO). Real module/tab is
# module=Building&TabName=Building (found via nav-link probe). Dropdown
# has NO single "Commercial" catch-all label (mostly residential-trade
# subtypes: A/C, Furnace, Reroof, Siding, EV Charger, Solar, etc.) --
# the broadest non-residential-specific option is "Building Permit -
# Plan Review Required" (the generic new-construction/commercial bucket
# that requires full plan review, as opposed to the over-the-counter
# residential trade permits listed alongside it). Also present:
# "Commercial EV Charger" and "Commercial Solar" as narrow commercial
# subtypes, but "Plan Review Required" is the broad catch-all used here.
CO_ADAMS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "accela",
    "county": "Adams",
    "endpoint": "https://aca-prod.accela.com/ADAMSCO",
    "module": "Building",
    "permit_type_label": "Building Permit - Plan Review Required",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-ADAMS"] = CO_ADAMS_ACCELA_CONFIG

# City of Fort Collins, CO (Larimer County, largest city) -- Accela on
# a custom host domain (not aca-prod.accela.com), confirmed live
# 2026-07-31: https://accela-aca.fcgov.com/CitizenAccess/Welcome.aspx
# returns 200. Base path is "/CitizenAccess" (not an agency-code path
# segment like most deployments) -- endpoint here is the full base
# including that segment so accela_provider.py's f"{base_url}/Cap/
# CapHome.aspx" construction resolves correctly. module=Building&
# TabName=HOME dropdown has a genuine broad new-construction-commercial
# label: "Commercial New Com-Ind-Mixed-Use Building" (distinct from
# narrower Commercial Electrical/Mechanical/Plumbing/Roofing/Addition/
# Alteration subtypes also present).
CO_FORTCOLLINS_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "accela",
    "county": "Larimer",
    "endpoint": "https://accela-aca.fcgov.com/CitizenAccess",
    "module": "Building",
    "permit_type_label": "Commercial New Com-Ind-Mixed-Use Building",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-FORTCOLLINS"] = CO_FORTCOLLINS_ACCELA_CONFIG

# City of Longmont, CO (Boulder County, 2nd largest city) -- Accela
# agency code LONGMONT (lowercase /longmont/ also resolves), confirmed
# live 2026-07-31 (200). Real module/tab is module=Building&
# TabName=Building. Dropdown has a clean Commercial/Multifamily/
# Residential split across every permit category -- "New Construction -
# Commercial" is the exact broad catch-all used here. NOTE: unincorporated
# Boulder County itself also runs Accela, but on a dedicated subdomain
# (accelapublic.bouldercounty.org/CitizenAccess, confirmed live) rather
# than aca-prod.accela.com/BOULDERCO (Gemini's first guess, confirmed
# 404 -- fabricated agency code, corrected via GEMINI_FEEDBACK_REPORT
# loop) -- not wired this session, Longmont was prioritized as the
# larger/simpler target.
CO_LONGMONT_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "accela",
    "county": "Boulder",
    "endpoint": "https://aca-prod.accela.com/LONGMONT",
    "module": "Building",
    "permit_type_label": "New Construction - Commercial",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-LONGMONT"] = CO_LONGMONT_ACCELA_CONFIG

# Weld County, CO (unincorporated; state's #8 county by population,
# high oil/gas + residential/commercial growth) -- Accela agency code
# WELD, confirmed live 2026-07-31 (200). module=Building&TabName=Home
# dropdown has a clean, real "Commercial New Construction" catch-all
# label (distinct from Commercial Alteration/Electrical and Oil and Gas
# subtypes).
CO_WELD_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "accela",
    "county": "Weld",
    "endpoint": "https://aca-prod.accela.com/WELD",
    "module": "Building",
    "permit_type_label": "Commercial New Construction",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-WELD"] = CO_WELD_ACCELA_CONFIG

# City of Cleveland, OH (Dept. of Building and Housing) -- Accela agency
# code COC, confirmed live 2026-07-28. Separate system from Cuyahoga
# County's own ArcGIS feed (OH-CUYAHOGA above) -- same LA-City-vs-LA-
# County / San-Antonio-vs-Bexar pattern. 98 total permit-type dropdown
# options, 15 real commercial categories. Live-probed the 3 most likely:
# "Commercial Building Construction Permit" 144/30-days (by far the
# dominant category, kept), "Commercial Combo" 0 (skipped), "COO - New
# Commercial" 2 (small but free to add). Other 12 commercial categories
# (Electrical/HVAC/Plumbing/Storm Water/Pools/Historical/On-line trade
# permits) not probed -- narrower trade-specific permits, unlikely to
# carry meaningful independent project-discovery volume.
OH_CLEVELAND_CONFIG: dict[str, Any] = {
    "state_code": "OH",
    "provider_type": "accela",
    "county": "Cuyahoga",
    "endpoint": "https://aca-prod.accela.com/COC",
    "module": "BuildingHousing",
    "permit_type_label": "Commercial Building Construction Permit",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
OH_CLEVELAND_COO_CONFIG: dict[str, Any] = {
    **OH_CLEVELAND_CONFIG,
    "permit_type_label": "COO - New Commercial",
}
STATE_CONFIGS["OH-CLEVELAND"] = OH_CLEVELAND_CONFIG
STATE_CONFIGS["OH-CLEVELAND-COO"] = OH_CLEVELAND_COO_CONFIG

# Montgomery County, OH (Dayton) -- Accela agency code MONTCOOH, verified
# live 2026-07-31: portal reachable (200), Building module's General
# Search permit-type dropdown has a single broad commercial catch-all
# option, "Commercial Building" (the only Commercial-prefixed label of
# 16 total options; the rest are trade-specific -- Electrical/Gas/
# Mechanical/Sign/Fire Protection/Hood-Paint-Booth -- or residential).
OH_MONTGOMERY_CONFIG: dict[str, Any] = {
    "state_code": "OH",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Montgomery",
    "endpoint": "https://aca-prod.accela.com/MONTCOOH",
    "module": "Building",
    "permit_type_label": "Commercial Building",
    "lookback_days": 579,
    "feed_id": "oh-dayton-montgomery",
}
STATE_CONFIGS["OH-MONTGOMERY"] = OH_MONTGOMERY_CONFIG

# Butler County, OH -- Accela agency code BUTLER, verified live
# 2026-07-31: no single "Commercial" catch-all option exists (46 total
# labels, county names permit types Building/{Commercial|Residential}/
# {subtype}/{detail}). Probed 4 plausible Commercial-prefixed labels
# directly: "Building/Commercial/Alterations/Other" (55 rows/90 days,
# broadest -- used here), "Commercial Tenant Finish" (37 rows),
# "Commercial Footer Foundation, Shell, and TF" (7 rows, new-construction
# shell permits), "Building/Commercial/New/Multi Family" (0 rows, dead).
OH_BUTLER_CONFIG: dict[str, Any] = {
    "state_code": "OH",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Butler",
    "endpoint": "https://aca-prod.accela.com/BUTLER",
    "module": "Building",
    "permit_type_label": "Building/Commercial/Alterations/Other",
    "lookback_days": 579,
    "feed_id": "oh-butler",
}
STATE_CONFIGS["OH-BUTLER"] = OH_BUTLER_CONFIG

# Clermont County, OH -- Tyler EnerGov Self Service. Gemini's first guess
# (clermontoh-energov.tylerhost.net) was a dead DNS name -- real live host
# found via independent web search: clermontcountyoh-energovpub
# .tylerhost.net/apps/selfservice (200 OK, verified 2026-07-31).
# tenant_name unconfirmed via UI probe -- trying "Clermont County" first.
OH_CLERMONT_CONFIG: dict[str, Any] = {
    "state_code": "OH",
    "provider_type": "energov",
    "county": "Clermont",
    "endpoint": "https://clermontcountyoh-energovpub.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Clermont County",
    "lookback_days": 900,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
    "feed_id": "oh-clermont",
}
STATE_CONFIGS["OH-CLERMONT"] = OH_CLERMONT_CONFIG

# City of Hartford, CT (Hartford County's largest city; CT has no
# county government -- towns/cities issue permits directly) -- Accela
# agency code HARTFORD, confirmed live 2026-07-31 (module=Building loads
# cleanly, no Error.aspx redirect). Playwright dropdown probe of
# #ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType shows no
# single "Commercial" catch-all -- real options are split into
# Commercial Accessory Structure/Addition/Alteration/Foundation/New
# Construction/Pool-Spa/Solar-PV Permit. Picked "Commercial Alteration
# Permit" as the broadest, highest-volume real label (same pattern used
# for TX_BROWNSVILLE_ACCELA_CONFIG).
CT_HARTFORD_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "CT",
    "provider_type": "accela",
    "county": "Hartford",
    "endpoint": "https://aca-prod.accela.com/HARTFORD",
    "permit_type_label": "Commercial Alteration Permit",
    "lookback_days": 579,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CT-HARTFORD"] = CT_HARTFORD_ACCELA_CONFIG

# Shelby County, TN (Memphis) -- Accela agency code SHELBYCO, confirmed
# live 2026-07-31 (prior session's SHELBY/MEMPHIS/DEVELOP901 variant
# guesses were all wrong; SHELBYCO is the real code, found via Gemini +
# live curl verification: aca-prod.accela.com/SHELBYCO/Cap/CapHome.aspx?
# module=Building returns 200 with a real permit-type dropdown).
# module=Building has 50 real options; "Commercial New Construction
# Permit" is the broadest non-residential/non-trade-specific catch-all
# (other Commercial-prefixed options are trade-specific: Electrical/
# Mechanical/Plumbing/Accessory/Addition/Alteration). Covers City of
# Memphis + Arlington/Germantown/Lakeland/Millington + unincorporated
# Shelby County under one Accela agency, per Develop901's own coverage
# description.
TN_SHELBY_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TN",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Shelby",
    "endpoint": "https://aca-prod.accela.com/SHELBYCO",
    "permit_type_label": "Commercial New Construction Permit",
    "lookback_days": 579,
}
STATE_CONFIGS["TN-SHELBY"] = TN_SHELBY_ACCELA_CONFIG

# City of Hendersonville, TN (Sumner County) -- Tyler EnerGov Citizen Self
# Service, same tylerhost.net/apps/selfservice pattern as the CA EnerGov
# tenants above. Live-verified 2026-07-31: hendersonvilletn-energovweb.
# tylerhost.net/apps/SelfService resolves 200. tenant_id left at provider
# default "1" (unconfirmed -- El Monte/Glendale/etc. all also used "1";
# no live UI probe done yet to confirm this tenant's actual ID). Search
# still returns a null Result after fixing the blocking modal (see
# energov_provider.py) -- kept registered for future debugging, but see
# jurisdiction_health_matrix.json: Sumner stays FAILED_NEED_ALT.
TN_HENDERSONVILLE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "TN",
    "provider_type": "energov",
    "county": "Sumner",
    "endpoint": "https://hendersonvilletn-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Hendersonville",
    "lookback_days": 90,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}
STATE_CONFIGS["TN-HENDERSONVILLE"] = TN_HENDERSONVILLE_ENERGOV_CONFIG

# City of Naperville, IL (DuPage County) -- Tyler EnerGov Citizen Self
# Service, same tylerhost.net/apps/SelfService pattern as the other
# EnerGov tenants above. Live-verified 2026-07-31 via direct curl (200 OK,
# napervilleil-energovweb.tylerhost.net/apps/SelfService#/home). tenant_id
# left at provider default "1", unconfirmed against a live UI probe (same
# caveat as Hendersonville). DuPage County itself has no county-level
# digital permit system -- Naperville is the largest city and closest
# real candidate. See jurisdiction_health_matrix.json for status.
IL_NAPERVILLE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "IL",
    "provider_type": "energov",
    "county": "DuPage",
    "endpoint": "https://napervilleil-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Naperville",
    "lookback_days": 90,
        # Raised from 5 on 2026-08-03. max_pages 5 was a 30-day-lookback
    # setting; with the server-side ApplyDateFrom filter now applied
    # (see energov_provider.py) a 2025-01-01 backfill needs real depth.
    "max_pages": 250,
}
STATE_CONFIGS["IL-NAPERVILLE"] = IL_NAPERVILLE_ENERGOV_CONFIG

# Prince George's County, MD (DC suburbs -- Bowie, Hyattsville, College
# Park). Verified live 2026-08-02: "Residential and Commercial Permits
# (July 2013 to Present)" on data.princegeorgescountymd.gov (Socrata/Tyler
# Data & Insights), dataset weik-ttee, issued by DPIE. MAX(permit_issuance_
# date) = 2026-07-24 at verification time -- actively updating, not stale.
# No boolean commercial/residential flag field; the real split is the
# permit_type prefix convention (confirmed by spot-checking case_name
# values): R*/RGU/RGW/RUW/RZW = residential, C*/CI/CIW/CU/CUW/CG/CGU/CGW/CE/
# CEW = commercial/industrial (fit-outs, assisted-living facility, data
# enclosure, clubhouse all confirmed in the CG/CGU/CGW slice). 127 rows
# matched the commercial_where filter since 2025-01-01 at verification.
MD_PRINCEGEORGES_CONFIG: dict[str, Any] = {
    "state_code": "MD",
    "provider_type": "socrata",
    "county": "Prince George's",
    "endpoint": "https://data.princegeorgescountymd.gov/resource/weik-ttee.json",
    "watermark_field": "permit_case_id",
    "hash_fields": ["permit_case_id"],
    "commercial_where": (
        "permit_type in ("
        "'CI','CIW','CU','CUW','CG','CGU','CGW','CE','CEW',"
        "'DPIE CG','DPIE CGU','DPIE CGW'"
        ")"
    ),
    "date_field": "permit_issuance_date",
    "lookback_days": 578,
    "feed_id": "md-princegeorges-dpie",
    "id_field": "permit_case_id",
    "name_fields": ["case_name", "permit_type", "street_address"],
    "address_fields": ["street_address", "city", "zip_code"],
}
STATE_CONFIGS["MD-PRINCEGEORGES"] = MD_PRINCEGEORGES_CONFIG

# Snohomish County, WA (Everett/Lynnwood/Marysville, Seattle metro; rank
# 72 by population) -- Snohomish County Planning & Development Services
# publishes its live AMANDA permit tables as ArcGIS FeatureServers under
# the county's SCDLCS AGOL org. Verified live 2026-08-02:
#   Building_Permits_Under_Construction/0 -> 2,576 rows, 348 foldertype='CBP'
#   Building_Applications_Under_Review/0  ->   893 rows, 215 foldertype='CBP'
# foldertype is the commercial/residential discriminator: CBP = Commercial
# Building Permit, RBP = Residential (other values: SIGN, DEMO, ROOF,
# KM/KP mechanical-plumbing, EVNT). PFN ("25 103203 CBP") is the county's
# real permit file number and is the join key into the PDS document
# repository (see source_url note below).
#
# Two caveats, both verified rather than assumed:
#  1. There is NO valuation field on either layer -- Snohomish PDS does not
#     publish job cost via GIS. value_fields is intentionally empty.
#  2. InDate/IssueDate are esriFieldTypeString in MM/DD/YYYY, so no
#     server-side date filter works (DATE/TIMESTAMP literals 400, and a
#     plain string compare against an ISO cutoff returns zero rows because
#     '04/07/2025' < '2025-01-01' lexically). Hence date_literal_style
#     "none": pull the whole commercial-filtered layer (a few hundred rows,
#     these are live snapshots of in-flight work, not a historical archive)
#     and use the date for mapping only. lookback_days is still recorded
#     for the standing 2025-01-01 anchor policy.
#
# DOCUMENT PATH (verified end-to-end 2026-08-02): PDS Online Records at
# https://snoco.org/pdspublicrecords/ is an OpenText Content Server
# repository fronted by an unauthenticated SOAP proxy at
# https://snoco.org/pdspublicrecords/otws/otlinkerws.asmx.
#   search:   GetData(hostUrl="recordsportal/search/100/2847417/<OT query>")
#             where the permit-number attribute is Attr_296923_2, so
#             'Attr_296923_2 : "25 103203 CBP"' returns that permit's
#             document set (18 docs for that PFN: Approved Building Plan
#             Set, Architectural Plan, Civil Plan, Geotechnical Report,
#             Structural Calcs, Project Narrative, Fire Approval Letter...).
#   download: SaveFile(hostUrl="recordsportal/getnode/<objectId>",
#             docType="application%20pdf", fileName=<lowercased name>)
#             then GET https://snoco.org/pdspublicrecords/tDocs/<lowercased
#             name> -- confirmed by pulling a 17.8 MB approved plan-set PDF.
SNOHOMISH_PDS_FIELDS = (
    "PFN,folderrsn,foldertype,Sub,Work_,foldername,Status,InDate,IssueDate,"
    "Expiry,Kind_of_Building,Site_Address1,Site_Address2,PARCEL_ID,OBJECTID"
)
WA_SNOHOMISH_CONFIG: dict[str, Any] = {
    "state_code": "WA",
    "provider_type": "arcgis",
    "county": "Snohomish",
    "endpoint": "https://services6.arcgis.com/z6WYi9VRHfgwgtyW/arcgis/rest/services/Building_Permits_Under_Construction/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PFN"],
    "commercial_where": "foldertype='CBP'",
    "out_fields": SNOHOMISH_PDS_FIELDS,
    "date_field": "IssueDate",
    "date_literal_style": "none",
    "lookback_days": 578,  # (date.today() - date(2025,1,1)).days as of 2026-08-02
    "feed_id": "wa-snohomish-pds",
    "id_field": "PFN",
    "name_fields": ["foldername", "Site_Address1", "PFN"],
    "address_fields": ["Site_Address1"],
    "value_fields": [],
    "desc_fields": ["Sub", "Work_", "Kind_of_Building", "Status"],
    "city_fields": ["Site_Address2"],
    "source_url": "https://snoco.org/pdspublicrecords/",
}
# Same layer family, earlier stage: applications still in review. Highest
# value for SpecIndex's "early spec window" framing -- these are projects
# whose plan sets are already in the PDS document repository but which
# have not broken ground.
WA_SNOHOMISH_REVIEW_CONFIG: dict[str, Any] = {
    **WA_SNOHOMISH_CONFIG,
    "endpoint": "https://services6.arcgis.com/z6WYi9VRHfgwgtyW/arcgis/rest/services/Building_Applications_Under_Review/FeatureServer",
    "date_field": "InDate",
    "feed_id": "wa-snohomish-pds-review",
}
STATE_CONFIGS["WA-SNOHOMISH"] = WA_SNOHOMISH_CONFIG
STATE_CONFIGS["WA-SNOHOMISH-REVIEW"] = WA_SNOHOMISH_REVIEW_CONFIG

# City of Orlando (Orange County, FL) -- wired 2026-08-03 during the
# rank-21-30 completeness audit. Orange County had exactly ONE project in
# the whole corpus despite being a top-30 county: no structured source had
# ever been wired, only a stray web-research row.
#
# Orange County's own portal (Fast Track, fasttrack.ocfl.net) is a session
# -based ASP app with no open API; the county GIS hub (ocgis-datahub-ocfl)
# publishes parcels, not permits. The City of Orlando's Socrata portal is
# the real structured channel for the metro and is excellent -- it carries
# project_name, estimated_cost, contractor, and square_footage as first-
# class columns, which most permit feeds do not.
#
# Commercial split: `worktype` is NOT the right filter here -- live-checked
# 2026-08-03, worktype='Comm' AND application_type='Building Permit'
# returns 0 rows (worktype carries trade/scope codes like New/Alteration/
# Roof, and 'Comm' only ever co-occurs with the trade application types).
# The real commercial flag is `plan_review_type`, whose live distribution
# since 2025-01-01 is Residential 1/2=33,608, Commercial=17,844,
# Residential 3 or more=5,400, No Plan Review Type=490.
FL_ORLANDO_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "socrata",
    "county": "Orange",
    "endpoint": "https://data.cityoforlando.net/resource/ryhf-m453.json",
    "watermark_field": "permit_number",
    "hash_fields": ["permit_number"],
    "commercial_where": "plan_review_type='Commercial'",
    "date_field": "processed_date",
    "lookback_days": 30,
    "feed_id": "fl-orlando",
    "id_field": "permit_number",
    "name_fields": ["project_name", "permit_address", "permit_number"],
    "address_fields": ["permit_address"],
    "value_fields": ["estimated_cost"],
    "desc_fields": ["worktype", "application_type", "application_status"],
    "default_city": "Orlando",
    "source_url": "https://data.cityoforlando.net/d/ryhf-m453",
}
STATE_CONFIGS["FL-ORLANDO"] = FL_ORLANDO_CONFIG

# SAM.gov + USAspending for all 50 states (2026-07-28, Asif: "pull all
# data from USAspending and sam.gov"). Both providers are already
# architecturally per-state -- GA_SAM_CONFIG/GA_USASPENDING_CONFIG above
# were just the only ones registered. SamGovProvider filters a single
# shared, cached (20h) national CSV client-side (no per-state download
# cost); USASpendingProvider genuinely queries server-side per state, no
# API key or quota. Generated here rather than 98 manual blocks -- GA
# excluded (already has its own dedicated config/history above).
_ALL_US_STATE_CODES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY",
]
for _sc in _ALL_US_STATE_CODES:
    if _sc == "GA":
        continue
    STATE_CONFIGS[f"{_sc}-SAM"] = {"state_code": _sc, "provider_type": "sam_gov"}
    STATE_CONFIGS[f"{_sc}-USASPENDING"] = {
        "state_code": _sc,
        "provider_type": "usaspending",
        "lookback_days": 730,
    }

# Clark County, NV -- state's #1 county by population (Las Vegas metro),
# #11 nationally, previously zero coverage. Clark County's own government
# (unincorporated area) only exposes an Accela Citizen Access search UI
# (aca-prod.accela.com/clarkco) with no public bulk/REST export found.
# City of Las Vegas (largest incorporated city within the county) runs
# its own ArcGIS-based open data portal instead -- verified live
# 2026-07-31: layer is a standalone Table (no geometry) named
# "Building_Permits_MV" on
# https://services1.arcgis.com/F1v0ufATbBQScMtY/arcgis/rest/services/OpenData_Building_Permits_/FeatureServer/0
# 435,686 total rows, COMM/RES flag field (COMM='Y' for 99,635 commercial
# rows), MAX(ISSDTTM)=2026-07-24 (1 week fresh, actively updating --
# dataset's own "modified" metadata is 2026-07-29). 5,571 commercial rows
# since 2025-01-01. ObjectId is Esri's standard autoincrement watermark
# field; APNO is the real permit number/application ID field.
NV_CLARK_LASVEGAS_CONFIG: dict[str, Any] = {
    "state_code": "NV",
    "provider_type": "arcgis",
    "county": "Clark",
    "endpoint": "https://services1.arcgis.com/F1v0ufATbBQScMtY/arcgis/rest/services/OpenData_Building_Permits_/FeatureServer",
    "layer": 0,
    "watermark_field": "ObjectId",
    "hash_fields": ["APNO"],
    "commercial_where": "COMM = 'Y'",
    "out_fields": "*",
    "date_field": "ISSDTTM",
    "lookback_days": 576,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "nv-clark-lasvegas",
    "id_field": "APNO",
    "name_fields": ["APL_ADDRESS", "WORKTYPE", "APNO"],
    "address_fields": ["APL_ADDRESS", "CITY", "STATE", "ZIP"],
    "value_fields": ["DECLVLTN", "CALCVLTN"],
    "desc_fields": ["WORKTYPE", "APTYPE", "BLDGAPPLSTATUS"],
    "source_url": "https://opendataportal-lasvegas.opendata.arcgis.com/datasets/lasvegas::building-permits-",
}
STATE_CONFIGS["NV-CLARK"] = NV_CLARK_LASVEGAS_CONFIG

# City of Sacramento -- the population/commercial-activity center of
# Sacramento County; the county government itself does not publish a
# commercial-permit dataset, but the City's ArcGIS-hosted "Automated
# Permitting System" export does, split across two layers (Current Year
# + Archive). Status_Date is esriFieldTypeString in "MM/DD/YYYY" form,
# not a real Esri date field, so DATE/TIMESTAMP literal comparison (and
# the provider's date_field_is_string YYYY-MM-DD fallback) both break --
# lexicographic order on MM/DD/YYYY doesn't match chronological order.
# Worked around by baking the year restriction directly into
# commercial_where via LIKE '%/2025' on the Archive layer instead of
# using date_field at all; the Current Year layer is inherently already
# scoped to 2026 YTD by the source so needs no extra filter. Verified via
# direct FeatureServer query: Type='Commercial' AND Status_Date LIKE
# '%/2025' -> 2,815 rows (Archive); Type='Commercial' -> 1,519 rows
# (Current Year, 2026 YTD).
CA_SACRAMENTO_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Sacramento",
    "endpoint": "https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/BldgPermitIssued_CurrentYear/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["Application"],
    "commercial_where": "Type='Commercial'",
    # Status_Date is a STRING column (MM/DD/YYYY), so it cannot be used as an
    # ArcGIS `date_field` -- a DATE comparison against it errors, and it sorts
    # wrong lexicographically. But it is still the only real date this layer
    # carries, and output_date_field is read ONLY when building output rows,
    # never injected into the WHERE clause, so it is safe here.
    #
    # Leaving it unset is what made 4,332 of Sacramento's 4,333 rows carry a
    # null date and drop out of every windowed query -- a top-25 county reading
    # as 1 in-window project. generic_mapping._iso_date already parses
    # MM/DD/YYYY correctly (verified live 2026-08-03).
    "output_date_field": "Status_Date",
    "out_fields": (
        "OBJECTID,Type,Sub_Type,Category,Application,Status_Date,"
        "Current_Status,Parcel_No,Address,Site_Location,ZIP,Valuation,"
        "Work_Desc,Project_Name"
    ),
    "feed_id": "ca-sacramento-city-permits",
    "id_field": "Application",
    "name_fields": ["Project_Name", "Category"],
    "address_fields": ["Address", "Site_Location"],
    "value_fields": ["Valuation"],
    "desc_fields": ["Work_Desc", "Category", "Sub_Type"],
    "source_url": "https://data.cityofsacramento.org/datasets/issued-building-permits-current-year/about",
}

CA_SACRAMENTO_ARCHIVE_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "arcgis",
    "county": "Sacramento",
    "endpoint": "https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/BldgPermitIssued_Archive/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["Application"],
    # Year restricted directly in the WHERE clause (see comment above) --
    # date_field deliberately left unset since Status_Date is a string
    # column whose MM/DD/YYYY format sorts wrong lexicographically.
    # The archive spans 2016+ and Status_Date is a string, so the year is
    # filtered with LIKE rather than a date comparison. This previously matched
    # ONLY '%/2025' -- which silently excluded every 2026 archive record even
    # though the pull window is 2025-01-01 onward. Both years now included.
    "commercial_where": (
        "Type='Commercial' AND "
        "(Status_Date LIKE '%/2025' OR Status_Date LIKE '%/2026')"
    ),
    # See the note on CA_SACRAMENTO_CONFIG: output-only, never used in a WHERE.
    "output_date_field": "Status_Date",
    "out_fields": (
        "OBJECTID,Type,Sub_Type,Category,Application,Status_Date,"
        "Current_Status,Parcel_No,Address,Site_Location,ZIP,Valuation,"
        "Work_Desc,Project_Name"
    ),
    "feed_id": "ca-sacramento-city-permits-archive",
    "id_field": "Application",
    "name_fields": ["Project_Name", "Category"],
    "address_fields": ["Address", "Site_Location"],
    "value_fields": ["Valuation"],
    "desc_fields": ["Work_Desc", "Category", "Sub_Type"],
    "source_url": "https://data.cityofsacramento.org/datasets/issued-building-permits-archive-1/about",
}

STATE_CONFIGS["CA-SACRAMENTO"] = CA_SACRAMENTO_CONFIG
STATE_CONFIGS["CA-SACRAMENTO-ARCHIVE"] = CA_SACRAMENTO_ARCHIVE_CONFIG

# Santa Clara County, CA (San Jose) -- CA's #6 county by population, major
# commercial construction market (Silicon Valley), previously zero
# coverage. County government itself has no centralized permit API (its
# Planning Hub ArcGIS site is parcel/zoning GIS layers only, no permit
# feed). City of San Jose, the county's dominant jurisdiction, runs a
# CKAN open-data portal (data.sanjoseca.gov) -- verified live 2026-08-01
# via datastore_search_sql. "Active Building Permits" resource
# (761b7ae8-3be1-4ad6-923d-c7af6404a904) has FOLDERDESC='Commercial/
# Industrial' as the real commercial filter (real fields: gx_location for
# address, ISSUEDATE, PERMITVALUATION, WORKDESCRIPTION/SUBTYPEDESCRIPTION/
# FOLDERNAME for description). 1,142 commercial/industrial rows with a
# 2025-/2026- FOLDERNUMBER prefix at research time.
#
# Known data-format gotcha: ISSUEDATE is stored as free-text "M/D/YYYY
# H:MM:SS AM" (not ISO), so CkanProvider's lexicographic initial-cutoff
# comparison (date_field >= cutoff) is unreliable on this field -- verified
# live it silently drops ~23% of true matches on a fresh backfill (880 of
# 1142) by systematically excluding Jan/Oct/Nov/Dec-dated rows. Real
# precision instead comes from FOLDERNUMBER's "YYYY-NNNNNN-XX" format
# (year prefix matches ISSUEDATE's year in every row sampled), folded into
# commercial_where as an explicit LIKE restriction so the query is correct
# regardless of the broken date-field AND clause layered on top by the
# provider on a watermark-less first run. Net effect: initial backfill is
# real, verified, correctly-scoped data, just short by an estimated ~20%
# of true 2025-2026 volume -- a supplemental catch-up pull (widening the
# FOLDERNUMBER LIKE list) would close the gap; not done here to stay
# within this session's scope.
CA_SANTACLARA_CONFIG: dict[str, Any] = {
    "state_code": "CA",
    "provider_type": "ckan",
    "county": "Santa Clara",
    "endpoint": "https://data.sanjoseca.gov",
    "resource_id": "761b7ae8-3be1-4ad6-923d-c7af6404a904",
    "watermark_field": "_id",
    "hash_fields": ["FOLDERNUMBER"],
    "commercial_where": (
        "\"FOLDERDESC\"='Commercial/Industrial' AND "
        "(\"FOLDERNUMBER\" LIKE '2025%' OR \"FOLDERNUMBER\" LIKE '2026%')"
    ),
    # date_field deliberately set to "" (not omitted -- factory.py defaults a
    # missing key to "date_entered"): CkanProvider appends the field unquoted
    # to the SQL, and Postgres lowercases unquoted identifiers, so it fails to
    # match the actual case-sensitive "ISSUEDATE" column (confirmed live:
    # causes a psycopg2.errors.UndefinedColumn wrapped in a 409 by the CKAN
    # API). Year scoping is already handled correctly via the FOLDERNUMBER
    # LIKE filter above, so no date_field is needed for correctness; the
    # provider now skips the date clause entirely when date_field is falsy.
    "date_field": "",
    # ...but suppressing the FILTER must not also blank out every row's
    # opened_or_announced_date (it did: 1,142 of 1,143 Santa Clara rows had
    # a null date). output_date_field is read only when building output
    # rows, never injected into SQL, so the case-sensitive column name is
    # safe here. Verified live 2026-08-03: all 1,141 matching rows have a
    # real ISSUEDATE ("3/8/2026 12:00:00 AM" style).
    "output_date_field": "ISSUEDATE",
    "lookback_days": 580,  # anchored to 2025-01-01 per Asif (recompute: (today - 2025-01-01).days)
    "feed_id": "ca-sanjose-santaclara",
    "id_field": "FOLDERNUMBER",
    "name_fields": ["WORKDESCRIPTION", "SUBTYPEDESCRIPTION", "FOLDERNAME"],
    "address_fields": ["gx_location"],
    "value_fields": ["PERMITVALUATION"],
    "desc_fields": ["WORKDESCRIPTION", "FOLDERNAME", "SUBTYPEDESCRIPTION"],
    "source_url": "https://data.sanjoseca.gov/dataset/active-building-permits",
}
STATE_CONFIGS["CA-SANTACLARA"] = CA_SANTACLARA_CONFIG


# ---------------------------------------------------------------------------
# Batch wired 2026-08-03: sources that were sitting in
# data/jurisdiction_health_matrix.json as VERIFIED_WORKING with a null
# state_agent_pipeline_key -- i.e. discovery had already confirmed them live
# and nobody ever wired them. All 26 such Accela/EnerGov entries were
# re-verified live before writing anything here; 12 turned out to be already
# covered (the matrix's null key is stale metadata, not a real gap), and
# Midland TX could not be resolved (its portal 403s a bot-check and every
# candidate tylerhost hostname DNS-fails -- left unwired rather than guessed).
#
# Accela and EnerGov are deliberately preferred over bulk metadata feeds:
# both expose per-record document paths, which is the differentiator. See
# the "Documents are the moat" section in CLAUDE.md.
#
# lookback_days is 579 = (2026-08-03 - 2025-01-01).days, the fixed pull
# anchor. RECOMPUTE this each session -- it drifts by a day every day, and
# the pipeline still has no absolute --since-date flag.
# ---------------------------------------------------------------------------

# --- Accela (3 counties with no prior config) ------------------------------

TX_GALVESTON_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Galveston",
    # Self-hosted Accela, not the aca-prod multitenant host. Verified live
    # 2026-08-03: /Cap/CapHome.aspx?module=Building returns 200 with real ACA markup.
    "endpoint": "https://eportal.galvestontx.gov/CitizenAccess",
    "permit_type_label": "Commercial Permit",
    "lookback_days": 579,
}
STATE_CONFIGS["TX-GALVESTON"] = TX_GALVESTON_CONFIG

FL_BREVARD_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    "county": "Brevard",
    "endpoint": "https://acaweb.brevardcounty.us/CitizenAccess",
    "permit_type_label": "Commercial Permit",
    "lookback_days": 579,
}
STATE_CONFIGS["FL-BREVARD"] = FL_BREVARD_CONFIG

FL_OSCEOLA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    # Standard ACA general-search date-range inputs, confirmed present in this
    # tenant's live HTML 2026-08-03. Without them the search is UNFILTERED and
    # returns the tenant's whole history in no date order, so a 2025+ backfill
    # only catches whatever recent rows happen to surface early -- Broward kept
    # 2 of 20 rows on page 1. 21 configs already set these; these did not.
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
    "county": "Osceola",
    # permits.osceola.org bare root 200s but the ACA app lives under
    # /CitizenAccess -- /portal/ 404s. The aca-prod.accela.com/OSCEOLA tenant
    # also resolves but bounces to Error.aspx, so the county's own host is
    # the real path. Both checked live 2026-08-03.
    "endpoint": "https://permits.osceola.org/CitizenAccess",
    "permit_type_label": "Commercial Permit",
    "lookback_days": 579,
}
STATE_CONFIGS["FL-OSCEOLA"] = FL_OSCEOLA_CONFIG

# --- EnerGov (Tyler Citizen Self Service) ----------------------------------
# selfservice_path defaults to "apps/selfservice", which is right for every
# *.tylerhost.net tenant. Self-hosted tenants vary and each value below was
# read off the live redirect, not assumed.

TX_SUGARLAND_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "energov",
    "county": "Fort Bend",
    "endpoint": "https://energovweb.sugarlandtx.gov",
    "selfservice_path": "EnerGov_prod/SelfService",
    "tenant_id": "1",
    "tenant_name": "Sugar Land",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["TX-SUGARLAND"] = TX_SUGARLAND_ENERGOV_CONFIG

TX_WACO_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "energov",
    "county": "McLennan",
    "endpoint": "https://selfservice.wacotx.gov",
    "selfservice_path": "EnerGov/SelfService",
    "tenant_id": "1",
    "tenant_name": "Waco",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["TX-WACO"] = TX_WACO_ENERGOV_CONFIG

TX_LUBBOCK_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "energov",
    "county": "Lubbock",
    "endpoint": "https://egovaccess.ci.lubbock.tx.us",
    "selfservice_path": "EnerGov_Prod/SelfService",
    "tenant_id": "1",
    "tenant_name": "Lubbock",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["TX-LUBBOCK"] = TX_LUBBOCK_ENERGOV_CONFIG

TX_WAXAHACHIE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "energov",
    "county": "Ellis",
    "endpoint": "https://waxahachietx-energovpub.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Waxahachie",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["TX-WAXAHACHIE"] = TX_WAXAHACHIE_ENERGOV_CONFIG

FL_WESTPALMBEACH_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "energov",
    "county": "Palm Beach",
    # The matrix recorded only the wpb.org/epl landing page, which 403s a
    # bot-check. The real CSS tenant is this tylerhost host (verified 200
    # live 2026-08-03). Palm Beach is rank 24 by population and had no config.
    "endpoint": "https://westpalmbeachfl-energovpub.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "West Palm Beach",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["FL-WESTPALMBEACH"] = FL_WESTPALMBEACH_ENERGOV_CONFIG

FL_MARION_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "energov",
    "county": "Marion",
    # permits.marionfl.org redirects to selfservice.marionfl.org with an
    # energov_prod path; both captured live rather than assumed.
    "endpoint": "https://selfservice.marionfl.org",
    "selfservice_path": "energov_prod/selfservice",
    "tenant_id": "1",
    "tenant_name": "Marion County",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["FL-MARION"] = FL_MARION_ENERGOV_CONFIG

AZ_YUMA_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "AZ",
    "provider_type": "energov",
    "county": "Yuma",
    "endpoint": "https://yumaaz-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Yuma",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["AZ-YUMA"] = AZ_YUMA_ENERGOV_CONFIG

AR_FAYETTEVILLE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "AR",
    "provider_type": "energov",
    "county": "Washington",
    "endpoint": "https://egov.fayetteville-ar.gov",
    "selfservice_path": "energov_prod/selfservice",
    "tenant_id": "1",
    "tenant_name": "Fayetteville",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["AR-FAYETTEVILLE"] = AR_FAYETTEVILLE_ENERGOV_CONFIG

AR_CONWAY_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "AR",
    "provider_type": "energov",
    "county": "Faulkner",
    "endpoint": "https://conwayar-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Conway",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["AR-CONWAY"] = AR_CONWAY_ENERGOV_CONFIG

CO_LARIMER_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "energov",
    "county": "Larimer",
    # Additive, not a duplicate: CO-FORTCOLLINS already covers the city on
    # Accela; this is the COUNTY's own portal (unincorporated + other towns).
    # Same relationship as the several LA-area city configs sharing a county.
    "endpoint": "https://onlineportal.larimer.org",
    "selfservice_path": "EnerGov_Prod/selfservice",
    "tenant_id": "1",
    "tenant_name": "Larimer County",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["CO-LARIMER"] = CO_LARIMER_ENERGOV_CONFIG

CO_GRANDJUNCTION_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "energov",
    "county": "Mesa",
    # Caveat from the discovery note: this tenant is scoped to planning/zoning
    # clearances; Grand Junction's actual building permits go through a
    # MaintStar portal we have no provider for. Expect low commercial yield.
    "endpoint": "https://grandjunctionco-energovweb.tylerhost.net",
    "tenant_id": "1",
    "tenant_name": "Grand Junction",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["CO-GRANDJUNCTION"] = CO_GRANDJUNCTION_ENERGOV_CONFIG

AL_MOBILE_ENERGOV_CONFIG: dict[str, Any] = {
    "state_code": "AL",
    "provider_type": "energov",
    "county": "Mobile",
    "endpoint": "https://urban.cityofmobile.org",
    "selfservice_path": "portal",
    "tenant_id": "1",
    "tenant_name": "Mobile",
    "lookback_days": 579,
    "max_pages": 250,
}
STATE_CONFIGS["AL-MOBILE"] = AL_MOBILE_ENERGOV_CONFIG
