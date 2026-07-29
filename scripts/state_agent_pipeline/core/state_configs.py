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
    "lookback_days": 30,
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
    "county": "Los Angeles",
    "endpoint": "https://aca-prod.accela.com/PALMDALE",
    "permit_type_label": "Commercial Permit",
    "lookback_days": 30,
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
    "county": "Los Angeles",
    "endpoint": "https://aca-prod.accela.com/DOWNEY",
    "permit_type_label": "Commercial Addition-Alteration",
    "lookback_days": 30,
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
    "lookback_days": 30,
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
    "max_pages": 5,
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
    "max_pages": 5,
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
    "max_pages": 5,
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
    "max_pages": 5,
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
    "lookback_days": 30,
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
    "lookback_days": 30,
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
    "county": "Marion",
    "endpoint": "https://aca-prod.accela.com/INDY",
    "module": "Permits",
    "permit_type_label": "Improvement Location Permit-Non-Residential",
    "lookback_days": 180,
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
    "county": "Ada",
    "endpoint": "https://permits.cityofboise.org/CitizenAccess",
    "permit_type_label": "502-New or Added Commercial",
    "lookback_days": 180,
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
    "lookback_days": 180,
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
    "county": "Douglas",
    "endpoint": "https://aca-prod.accela.com/OMAHA",
    "module": "Permits",
    "permit_type_label": "New Building",
    "lookback_days": 180,
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
    "county": "Bernalillo",
    "endpoint": "https://aca-prod.accela.com/bernco",
    "permit_type_label": "Commercial Building",
    "lookback_days": 180,
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
    "county": "Fulton",
    "endpoint": "https://aca-prod.accela.com/ATLANTA_GA",
    "permit_type_label": "Commercial New",
    "lookback_days": 180,
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
    "county": "St. Louis",
    "endpoint": "https://aca-prod.accela.com/SLC",
    "module": "PublicWorks",
    "permit_type_label": "BUILDING COMMERCIAL NEW BUILDING",
    "lookback_days": 180,
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
    "county": "Salt Lake",
    "endpoint": "https://aca-prod.accela.com/SLCREF",
    "permit_type_label": "Commercial Building Permit",
    "lookback_days": 180,
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
    "lookback_days": 30,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}

TX_DALLAS_ALT_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Dallas",
    "endpoint": "https://aca-prod.accela.com/DALLASTX",
    "permit_type_label": "Commercial Alteration Addition Permit",
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
    "county": "Hidalgo",
    "endpoint": "https://onlinepermits.mcallen.net/Portal",
    "permit_type_label": "Commercial New or Addition",
    "lookback_days": 30,
}

# City of Brownsville (Cameron County). Accela, lowercase agency code.
TX_BROWNSVILLE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "TX",
    "provider_type": "accela",
    "county": "Cameron",
    "endpoint": "https://aca-prod.accela.com/BROWNSVILLE",
    "permit_type_label": "Commercial Alteration Permit",
    "lookback_days": 30,
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

# Cook County (IL) Assessor's Permits (Socrata) -- verified live
# 2026-07-28: real, but date_issued has a data-quality bug (4 rows out
# of 92,437 total have a garbage future date, MAX() = year 2210). Bounded
# the commercial_where with a sanity upper bound to exclude those rather
# than trusting an unbounded date filter -- same "bad future timestamp"
# trap as TX Collin County. Real 30-day count with the bound: 17 (close
# to the ~21 estimate; small variance expected on a live dataset).
IL_COOK_CONFIG: dict[str, Any] = {
    "state_code": "IL",
    "provider_type": "socrata",
    "county": "Cook",
    "endpoint": "https://datacatalog.cookcountyil.gov/resource/6yjf-dfxs.json",
    "watermark_field": "pin",
    "hash_fields": ["local_permit_number", "permit_number", "pin"],
    "commercial_where": "job_code_primary='COMMERCIAL PERMIT' AND date_issued <= '2030-01-01T00:00:00'",
    "date_field": "date_issued",
    "lookback_days": 30,
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
NY_NYC_CONFIG: dict[str, Any] = {
    "state_code": "NY",
    "provider_type": "socrata",
    "county": "New York",
    "endpoint": "https://data.cityofnewyork.us/resource/w9ak-ipjd.json",
    "watermark_field": "job_filing_number",
    "hash_fields": ["job_filing_number"],
    "commercial_where": "building_type='Other'",
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
    "lookback_days": 30,
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

# Fort Lauderdale, FL (Broward County's top jurisdiction -- FL's 2nd most
# populous county after Miami-Dade). County-level itself uses proprietary
# Computronix POSSE with no public API. Fort Lauderdale's own ArcGIS
# permit layer (gis.fortlauderdale.gov, layer 27) is real but confirmed
# STALE (MAX(APPROVEDT)=2021-01-05, USECLASS entirely NULL) -- ruled out.
# Accela agency "FTL" verified live and reachable (200s, real module list
# is Permits, real dropdown options including "Commercial New
# Construction Permit" and "Commercial Alteration Permit"), but the
# search itself returns 0 rows for every permit type tried, unlike every
# other Accela agency wired this session -- a real, NOT YET RESOLVED
# mechanical issue (not the known El Paso-style missing-Start/End-Date
# problem; FTL's search page has no matching Start/End Date field pair,
# just one unrelated hidden date field). Registered but NOT merged --
# 0 real rows captured. Needs further debugging (e.g. checking whether
# the results table itself uses a different structure/pagination for
# this specific agency) before this source is usable.
FL_FORTLAUDERDALE_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "FL",
    "provider_type": "accela",
    "county": "Broward",
    "endpoint": "https://aca-prod.accela.com/FTL",
    "module": "Permits",
    "permit_type_label": "Commercial New Construction Permit",
    "lookback_days": 180,
}

# Pittsburgh, PA (Allegheny County's top jurisdiction -- PA's 2nd most
# populous county after Philadelphia). County-level has no unified permit
# system (130 independent municipalities under PA's UCC framework);
# Pittsburgh's own PLI department publishes to WPRDC (Western PA Regional
# Data Center), a CKAN portal. Verified live 2026-07-29: resource
# f4d1177a-f597-4c32-8cbf-7885f56253f6 ("PLI Permits"),
# commercial_or_residential='Commercial' is real (24,024/63,853 total),
# MAX(issue_date)=2026-07-28 (today).
PA_PITTSBURGH_CONFIG: dict[str, Any] = {
    "state_code": "PA",
    "provider_type": "ckan",
    "county": "Allegheny",
    "endpoint": "https://data.wprdc.org",
    "resource_id": "f4d1177a-f597-4c32-8cbf-7885f56253f6",
    "watermark_field": "_id",
    "hash_fields": ["permit_id"],
    "commercial_where": "commercial_or_residential='Commercial'",
    "date_field": "issue_date",
    "lookback_days": 180,
    "feed_id": "pa-pittsburgh",
    "id_field": "permit_id",
    "name_fields": ["work_description", "permit_type", "address"],
    "address_fields": ["address"],
    "value_fields": ["total_project_value"],
    "desc_fields": ["work_description", "work_type"],
    "source_url": "https://data.wprdc.org/dataset/pli-permits",
}

# Pierce County, WA (WA's 2nd most populous county after King). Genuine
# countywide source (unlike WA-KING, which is Seattle-city-scoped) --
# Pierce County's own PALS Plus system publishes directly to ArcGIS.
# Gemini's org ID was wrong (Invalid URL), real one found via an ArcGIS
# Online item search (owner PCWA_OpenData). No binary commercial/
# residential flag -- buildingType is a granular occupancy-type field
# (Bank/Restaurant/Office/Warehouse/Hospital/etc vs Apartment/House-plex/
# Townhouse/Adult Family Home) -- used an explicit IN-list of clearly-
# commercial types rather than an unreliable single boolean.
WA_PIERCE_CONFIG: dict[str, Any] = {
    "state_code": "WA",
    "provider_type": "arcgis",
    "county": "Pierce",
    "endpoint": "https://services2.arcgis.com/1UvBaQ5y1ubjUPmd/arcgis/rest/services/Permits_Pierce_County/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["applicationNumber"],
    "commercial_where": (
        "buildingType IN ('Bank','Restaurant','Office','Warehouse','Hospital',"
        "'Store - Grocery','Store - Retail/Personal Services','Medical Office',"
        "'Industrial Plant','Hotel/motel','Auditorium','Bowling Alley',"
        "'Convalescent Hospital','Fire Station','Jail','Library',"
        "'Nursing/Rest Home','Public Parking Garage','School Higher Education',"
        "'School K-12','Service Station/Repair Garage',"
        "'Theaters/Recreational Building','Water Systems-Commercial','Church')"
    ),
    "out_fields": "applicationNumber,applicationType,applicationStatus,workType,buildingType,buildingValuation,projectValue,workDescription,siteAddress,projectName,applicationDate,issuedDate",
    "date_field": "issuedDate",
    "lookback_days": 180,
    "feed_id": "wa-pierce",
    "id_field": "applicationNumber",
    "name_fields": ["workDescription", "buildingType", "siteAddress"],
    "address_fields": ["siteAddress"],
    "value_fields": ["projectValue", "buildingValuation"],
    "desc_fields": ["workDescription", "buildingType", "workType"],
    "source_url": "https://gisdata.piercecowa.opendata.arcgis.com/",
}

# City of Virginia Beach, VA (an independent city -- Virginia's most
# populous locality after Fairfax County; VA counties don't contain
# independent cities). Real ArcGIS item found via search (Gemini's
# Accela agency code "VB" 404'd). MAX(IssueDate)=2026-07-24, real field
# is ConstructionType='Commercial' (PermitType is trade category --
# Building/Electrical/Plumbing/etc, not occupancy). IssueDate is stored
# as text (sqlTypeNVarchar), not a true date field.
VA_VIRGINIABEACH_CONFIG: dict[str, Any] = {
    "state_code": "VA",
    "provider_type": "arcgis",
    "county": "Virginia Beach",
    "endpoint": "https://services2.arcgis.com/CyVvlIiUfRBmMQuu/arcgis/rest/services/Building_Permits_Applications_view/FeatureServer",
    "layer": 0,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PermitNumber"],
    "commercial_where": "ConstructionType='Commercial'",
    "out_fields": "PermitNumber,PermitType,ConstructionType,WorkType,Status,WorkDesc,StreetAddress,City,State,Zip,ApplicationDate,IssueDate",
    "date_field": "IssueDate",
    "date_literal_style": "string_slash",
    "lookback_days": 180,
    "feed_id": "va-virginiabeach",
    "id_field": "PermitNumber",
    "name_fields": ["WorkDesc", "PermitType", "StreetAddress"],
    "address_fields": ["StreetAddress", "City", "State", "Zip"],
    "value_fields": [],
    "desc_fields": ["WorkDesc", "WorkType", "ConstructionType"],
    "source_url": "https://data.virginiabeach.gov/",
}

# City and County of Denver, CO (Colorado's most populous county/city --
# effectively the state's #1, though CO-SPRINGS/El Paso was wired first
# this session; keeping both since they're genuinely different metros).
# Real dataset name (ODC_DEV_COMMERCIALCONSTPERMIT_P) confirms it's
# already commercial-only, no where-clause guesswork needed (same
# pattern as MD-MONTGOMERY/OR-MULTNOMAH). Real layer ID is 317, not the
# default 0 -- found via the FeatureServer's own layer listing.
# MAX(DATE_ISSUED)=2026-07-28 (yesterday relative to today), 42,829
# total rows.
CO_DENVER_CONFIG: dict[str, Any] = {
    "state_code": "CO",
    "provider_type": "arcgis",
    "county": "Denver",
    "endpoint": "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_DEV_COMMERCIALCONSTPERMIT_P/FeatureServer",
    "layer": 317,
    "watermark_field": "OBJECTID",
    "hash_fields": ["PERMIT_NUM"],
    "commercial_where": None,
    "out_fields": "PERMIT_NUM,ADDRESS,LOCATION,CLASS,VALUATION,CONTRACTOR_NAME,DATE_ISSUED,DATE_RECEIVED,NEIGHBORHOOD",
    "date_field": "DATE_ISSUED",
    "lookback_days": 180,
    "feed_id": "co-denver",
    "id_field": "PERMIT_NUM",
    "name_fields": ["LOCATION", "CLASS", "ADDRESS"],
    "address_fields": ["ADDRESS"],
    "value_fields": ["VALUATION"],
    "desc_fields": ["CLASS", "LOCATION"],
    "source_url": "https://www.denvergov.org/opendata",
}

# Lexington-Fayette, KY (Fayette County's top jurisdiction -- KY's 2nd
# most populous county after Jefferson/Louisville; LFUCG is a
# consolidated city-county government, genuine full-county coverage).
# Gemini's module name ("Building Inspection") was wrong -- real module
# list (via Welcome.aspx) is just Building/NewDevelopment/Planning/
# WasteManagement. Real dropdown option "Commercial New Construction"
# confirmed live.
KY_LEXINGTON_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "KY",
    "provider_type": "accela",
    "county": "Fayette",
    "endpoint": "https://aca-prod.accela.com/LEXKY",
    "module": "Building",
    "permit_type_label": "Commercial New Construction",
    "lookback_days": 180,
}

# Washington County, OR (Beaverton/Hillsboro -- OR's 2nd most populous
# county after Multnomah). Genuine countywide source (unlike OR-
# MULTNOMAH which is Portland-city-scoped) -- unincorporated Washington
# County runs its own Accela instance on a branded domain
# (permits.washingtoncountyor.gov), same non-standard-domain pattern as
# Boise ID. Real dropdown option "Commercial New" confirmed live.
OR_WASHINGTON_ACCELA_CONFIG: dict[str, Any] = {
    "state_code": "OR",
    "provider_type": "accela",
    "county": "Washington",
    "endpoint": "https://permits.washingtoncountyor.gov/CitizenAccess",
    "module": "Building",
    "permit_type_label": "Commercial New",
    "lookback_days": 180,
}

# New Orleans, LA (Orleans Parish). LA's actual #2-by-population parish,
# Jefferson Parish, is a confirmed dead end (MyGovernmentOnline, no
# public API) -- New Orleans is a real, high-value alternative found via
# Gemini's own cross-reference. Real Socrata dataset "Permits"
# (rcm3-fn58), updated today. landuseshort='COMM' is real (66,106 of
# 344,000+ total rows; RSFD/RSF2/RMF/etc are residential variants).
LA_NEWORLEANS_CONFIG: dict[str, Any] = {
    "state_code": "LA",
    "provider_type": "socrata",
    "county": "Orleans",
    "endpoint": "https://data.nola.gov/resource/rcm3-fn58.json",
    "watermark_field": "pin",
    "hash_fields": ["numstring", "pin"],
    "commercial_where": "landuseshort='COMM'",
    "date_field": "issuedate",
    "lookback_days": 180,
    "feed_id": "la-neworleans",
    "id_field": "numstring",
    "name_fields": ["description", "projectname", "address"],
    "address_fields": ["address"],
    "value_fields": ["constrval"],
    "desc_fields": ["description", "type"],
    "source_url": "https://data.nola.gov/Building-and-Housing/Permits/rcm3-fn58",
}

STATE_CONFIGS: dict[str, dict[str, Any]] = {
    "NJ": NJ_CONFIG,
    "CA-LOSANGELES": CA_LOSANGELES_CONFIG,
    "CA-LACOUNTY": CA_LACOUNTY_CONFIG,
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
    # "CA-POMONA" intentionally not registered yet -- see
    # _CA_POMONA_ENERGOV_CONFIG comment above.
    "AZ-MARICOPACOUNTY": AZ_MARICOPACOUNTY_CONFIG,
    "AZ-MESA": AZ_MESA_CONFIG,
    "AZ-SCOTTSDALE": AZ_SCOTTSDALE_CONFIG,
    "TX-JEFFERSON": TX_JEFFERSON_CONFIG,
    "TX-ECTOR": TX_ECTOR_CONFIG,
    "TX-DALLAS-NEW": TX_DALLAS_NEW_ACCELA_CONFIG,
    "TX-DALLAS-ALT": TX_DALLAS_ALT_ACCELA_CONFIG,
    "TX-WILLIAMSON": TX_WILLIAMSON_CONFIG,
    "MI-WAYNE": MI_WAYNE_CONFIG,
    "IL-COOK": IL_COOK_CONFIG,
    "NY-NYC": NY_NYC_CONFIG,
    "MA-CAMBRIDGE": MA_CAMBRIDGE_CONFIG,
    "MN-HENNEPIN": MN_HENNEPIN_CONFIG,
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
    "ID-ADA": ID_ADA_ACCELA_CONFIG,
    "SD-SIOUXFALLS": SD_SIOUXFALLS_CONFIG,
    "FL-FORTLAUDERDALE": FL_FORTLAUDERDALE_ACCELA_CONFIG,
    "PA-PITTSBURGH": PA_PITTSBURGH_CONFIG,
    "WA-PIERCE": WA_PIERCE_CONFIG,
    "VA-VIRGINIABEACH": VA_VIRGINIABEACH_CONFIG,
    "CO-DENVER": CO_DENVER_CONFIG,
    "KY-LEXINGTON": KY_LEXINGTON_ACCELA_CONFIG,
    "OR-WASHINGTON": OR_WASHINGTON_ACCELA_CONFIG,
    "LA-NEWORLEANS": LA_NEWORLEANS_CONFIG,
    "IN-INDIANAPOLIS": IN_INDIANAPOLIS_ACCELA_CONFIG,
    "FL-MIAMIDADE": FL_MIAMIDADE_CONFIG,
    "WA-KING": WA_KING_CONFIG,
    "TX-TARRANT": TX_TARRANT_CONFIG,
    "OH-FRANKLIN": OH_FRANKLIN_CONFIG,
    "OH-CUYAHOGA": OH_CUYAHOGA_CONFIG,
    "NC-MECKLENBURG": NC_MECKLENBURG_CONFIG,
    "NC-WAKE": NC_WAKE_CONFIG,
    "VA-FAIRFAX": VA_FAIRFAX_CONFIG,
    "TX-WILLIAMSON-PERMITS": TX_WILLIAMSON_PERMITS_CONFIG,
    "PA-PHILADELPHIA": PA_PHILADELPHIA_CONFIG,
    "CA-SANDIEGO": CA_SANDIEGO_CONFIG,
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
    "lookback_days": 30,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
STATE_CONFIGS["CO-SPRINGS"] = CO_SPRINGS_ACCELA_CONFIG

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
    "lookback_days": 30,
    "start_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate",
    "end_date_field_id": "ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate",
}
OH_CLEVELAND_COO_CONFIG: dict[str, Any] = {
    **OH_CLEVELAND_CONFIG,
    "permit_type_label": "COO - New Commercial",
}
STATE_CONFIGS["OH-CLEVELAND"] = OH_CLEVELAND_CONFIG
STATE_CONFIGS["OH-CLEVELAND-COO"] = OH_CLEVELAND_COO_CONFIG

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
