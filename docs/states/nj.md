# New Jersey Commercial Source Playbook

Read this file before refreshing `data/states/nj.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** NJ (New Jersey)  
**Corpus file:** `data/states/nj.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — BeOne Medicines IR, Business Facilities, local news.  
**Status mix:** planning 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. **NJDCA statewide construction permit data (Socrata, `data.nj.gov`)** — Tier 0/1 statewide register covering every NJ municipality including Newark, Jersey City, and all Bergen/Middlesex towns in one feed. Verified live 2026-07-26, built 2026-07-27 (`scripts/pull-nj-dca.py`).
2. State economic development announcements and press releases (NJEDA — see below, not yet automatable)
3. Municipal/county open data (verify the endpoint serves this state before bulk pull — Jersey City and Middlesex County portals checked, neither publishes permit-level data; see "What failed" below)
4. Trade press and owner or developer announcements

## What works

- **NJDCA "NJ Construction Permit Data"** (New Jersey Department of Community
  Affairs, Division of Codes & Standards) —
  `https://data.nj.gov/resource/w9se-dmra.json` (Socrata SODA API; dataset
  page: `https://data.nj.gov/Reference-Data/NJ-Construction-Permit-Data/w9se-dmra`).
  **This is the real NJ equivalent of Georgia's DRI / a statewide
  pre-existing register — it directly fixes the "7.1% have a city field"
  problem** because `muniname`+`county` are populated on every row.
  Verified live 2026-07-26:
  - **2,755,796 total records**, all 21 NJ counties present. Municipalities
    report monthly per N.J.A.C. 5:23-4.5(d); dataset description states
    "Data received as of 07/07/2026." Live sample rows for Newark (Essex)
    showed `permitdate` up to 2026-06-30 with `processdate` 2026-07-07 —
    genuinely fresh, not a stale export.
  - **Caveat found directly:** an unfiltered `MAX(permitdate)` query returns
    a garbage value (`2925-08-15`, clearly a fat-fingered year) — don't
    trust a raw max-date query on this field without a sanity ceiling
    (e.g. `permitdate < '{today}+30d'`); even then it still returned a
    suspicious `2026-12-31` (likely another handful of bad-year rows, not
    fully explored). Filter defensively, don't assume clean data.
  - **County coverage confirmed live** (row counts, all permit types,
    unfiltered): Bergen 304,237 · Monmouth 268,215 · Middlesex 259,475 ·
    Essex 162,829 · Hudson 67,972 (Jersey City alone = 20,484). Confirmed
    real per-town breakdown too: Bergen — Fair Lawn 25,230, Englewood
    15,894, Teaneck 13,557, Paramus 11,360, Fort Lee 7,665; Middlesex —
    Edison 33,628, East Brunswick 32,086, Woodbridge 23,077, Piscataway
    17,804.
  - **Schema (44 fields, real, pulled from the live column list):**
    `muniname`, `county`, `block`, `lot`, `permitno`, `status`/
    `permitstatusdesc` (`Permit` vs `Certificate`), `permitdate`,
    `certdate`, `permittype`/`permittypedesc` (`New`, `Addition`,
    `Alteration`, `Demolition`), `usegroup`/`usegroupdesc` (IBC-style use
    group — **this is the commercial-signal field**), `squarefeet`,
    `constcost`, `censusdesc`.
  - **Commercial filter (real distinct values with live counts):** keep
    `usegroupdesc` in `{"Business Uses" (159,157), "Mercantile buildings"
    (20,199), "Restaurants, Night Clubs, Dance Halls, and similar"
    (17,314), "Educational" (15,445), "Lecture halls, Art Galleries,
    Churches, etc." (13,765), "Storage building, moderate hazard"
    (13,994), "Hotels, motels, boarding houses, etc." (8,931), "Storage
    building, low hazard" (5,197), "Factory and industrial, moderate
    hazard" (4,254), "Indoor Sporting Venues, Arenas, Swimming Pools"
    (3,422), "Institutional Adult/Child Day Care for 6+ Occupants"
    (1,456), "Factory and industrial, low hazard" (1,420), "Theatres"
    (833)}` plus the High Hazard variants (~600 combined). **Drop**
    `"International Residential Code"` (1.95M), `"One and two family
    units..."` (156,621), and treat `"Multiple family dwellings,
    dormitories, etc."` (142,836) per the repo's `KEEP_MULTIFAMILY` policy.
    `"Accessory buildings and miscellaneous structures"` (220,793) is
    ambiguous (sheds/garages vs. small commercial outbuildings) — needs a
    size/cost floor, not a clean include.
  - **Real limitation, not yet solved:** no street address field — only
    `muniname` + `block` + `lot`, no lat/lon, no project name, no
    owner/contractor, no description text. This dataset fixes
    *jurisdiction*-level granularity (the stated NJ problem) but not
    street-level detail; a block/lot-to-parcel join against each county's
    MOD-IV/parcel GIS layer (e.g. `njogis-newjersey.opendata.arcgis.com`)
    would be a real follow-up cost, not yet attempted.
  - `permittypedesc` is dominated by `Alteration` (2.46M of 2.75M rows) —
    filtering to `permittypedesc IN ('New','Addition')` is the
    higher-signal cut for genuinely new commercial construction, though
    high-`constcost` `Alteration` rows also capture real tenant fit-outs.
  - Dataset purges rows after 60 months — compatible with this repo's
    24-month pull window convention.
  - **Built 2026-07-27**: `scripts/pull-nj-dca.py`, using the
    `usegroupdesc` allowlist above (minus the ambiguous "Accessory
    buildings" category) and a clamped `permitdate` upper bound. First
    24-month pull: 53,543 real commercial permits.

## What failed last time

- **"Newark Building_Permits" FeatureServer** —
  `https://services6.arcgis.com/ONZht79c8QWuX759/arcgis/rest/services/Building_Permits/FeatureServer/0`
  — top web-search hit for "Newark NJ building permits ArcGIS." **Same
  wrong-jurisdiction trap already documented in `docs/states/nc.md`**
  (that doc flagged this exact account ID, `ONZht79c8QWuX759`, surfacing
  in both Dallas TX and Austin TX searches as a generic aggregate stats
  table). Confirmed again here: fetched the live schema (`Year`,
  `Quarter`, `Geography`, `Single_Units`, `Commercial_Value`, etc. — a
  Year/Quarter aggregate table, not per-project records) and a live
  sample — `Geography` values are `"Brampton"`, `"Caledon"`,
  `"Mississauga"`, which are **Peel Region, Ontario, CANADA**
  municipalities, not Newark NJ. Never use this host's `Building_Permits`
  layer for any US jurisdiction search; it appears to surface for many
  different city-name queries regardless of relevance.
- **Jersey City Open Data** (`data.jerseycitynj.gov`) — real, live portal
  (API responsive, ~370 datasets). Catalog search for
  permit/construction/development returned only "Permit Requirements and
  Restrictions" (zoning reference text, not issuance records) and
  "Development Maps" (2020–2023, static map layers) — **no permit-issuance
  dataset exists on this portal**. The city's actual permitting system is
  a separate transactional portal (`jcnj.org/permitportal`) with no open-data
  export found. Not usable; the NJDCA statewide dataset above already
  covers Jersey City (20,484 records under Hudson County).
- **Middlesex County Open Data**
  (`data-middlesex.opendata.arcgis.com/api/feed/dcat-us/1.1.json`) — live
  catalog, only 19 datasets total, checked every title: no
  permit/construction/development/building dataset exists. Same
  conclusion as Jersey City — the NJDCA statewide dataset is the real
  source for Middlesex's towns (Edison, East Brunswick, Woodbridge,
  Piscataway all confirmed present there).
- **Essex County / Bergen County GIS portals** — both only publish
  parcels/MOD-IV tax-assessment data (`njogis-newjersey.opendata.arcgis.com`,
  `bergencountynj.gov/.../geographic-information-system-gis/`), not
  permits. Consistent with the framework note: NJ permits are issued at
  the municipal level with no county-level permit-issuing authority; the
  state DCA aggregation is the only place they roll up.
- **NJDEP Open Data** (`gisdata-njdep.opendata.arcgis.com`, 574 datasets,
  confirmed live) — has "Air Quality Permitted Facilities," "NJPDES
  Regulated Facility Locations," "Site Remediation" datasets, but these
  are **existing-facility environmental permits** (post-construction
  compliance), not pre-construction/new-project records — not a leading
  indicator the way GA's DRI is. Not built against; would only ever be a
  thin secondary cross-reference for industrial projects, not verified
  further given low expected relevance.
- **NJEDA** — no bulk CSV/API found. Real approved-incentive-project data
  lives behind **Power BI Government embeds**
  (`app.powerbigov.us/view?r=...`) for ERG (current/legacy), Grow NJ
  (current/legacy), Emerge/Aspire, and the Manufacturing Voucher Program,
  plus static PDF/Excel reports (e.g. "2023 Project List" PDF, "Active
  BEIP Grants" `.xlsx`, quarterly SBIG/SBLG award `.xlsx`/PDF files) at
  `njeda.gov/public_information/`. **Did not verify these load or export**
  — Power BI gov embeds are JS-rendered and typically resist simple HTTP
  scraping (would need Playwright, similar tier to GA's unautomated GPR).
  Also lower expected relevance even if scraped: these are tax-credit/grant
  *recipients*, not permit-level construction projects, so a project may
  appear here months before or without ever having a matching permit
  record. Flag as a Tier 3 exploratory lead, not a verified source — do
  not claim it works without actually loading a dashboard and reading
  real rows.
- **NJ BPU large-load filings** — named in the research framework but
  **not investigated this pass** (deprioritized once the NJDCA statewide
  dataset turned out to be the much larger find). Explicitly unresearched,
  not rejected — next session should check `njbpu.gov` docket search.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-nj-dca.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers New Jersey.
- Zip-code aggregate datasets with no project-level records.
- `services6.arcgis.com/ONZht79c8QWuX759/.../Building_Permits/FeatureServer` — confirmed Ontario, Canada aggregate stats table, not any NJ jurisdiction (see "What failed last time").

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
| 2026-07-26 | Research pass: verified NJDCA statewide Socrata dataset live (2.76M records, all counties); rejected Newark ArcGIS trap (Ontario data), Jersey City open data, Middlesex County open data, NJDEP facility permits as either non-existent or non-project-level; NJEDA flagged unverified (Power BI, not scraped) | No pull run yet — research only, no script written |
| 2026-07-27 | NJDCA statewide (`pull-nj-dca.py`, commercial `usegroupdesc` allowlist) | +53,543 projects, 53,750 total |
