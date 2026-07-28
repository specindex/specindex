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

STATE_CONFIGS: dict[str, dict[str, Any]] = {
    "NJ": NJ_CONFIG,
    "NC": NC_CONFIG,
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
    "AZ-MARICOPACOUNTY": AZ_MARICOPACOUNTY_CONFIG,
    "AZ-MESA": AZ_MESA_CONFIG,
    "AZ-SCOTTSDALE": AZ_SCOTTSDALE_CONFIG,
    "TX-JEFFERSON": TX_JEFFERSON_CONFIG,
    "TX-ECTOR": TX_ECTOR_CONFIG,
    "TX-WILLIAMSON": TX_WILLIAMSON_CONFIG,
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
