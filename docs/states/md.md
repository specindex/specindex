# Maryland Commercial Source Playbook

Read this file before refreshing `data/states/md.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** MD (Maryland)  
**Corpus file:** `data/states/md.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 3  
**Counties:** 3 · **Cities:** 3  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — Data Center Dynamics, Southern Maryland Chronicle.  
**Status mix:** planning 2, under_construction 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. Montgomery County commercial permits (Socrata) — verified live, not yet built.
2. Baltimore City DHCD building permits (ArcGIS) — verified live, not yet built.
3. Baltimore County Cityworks permits (ArcGIS) — verified live, not yet built.
4. Prince George's County DPIE permits (Socrata) — verified live, low commercial yield, not yet built.
5. Anne Arundel County — real per-record data lives in Accela (Land Use Navigator), not yet automated; only an aggregate ArcGIS table found, rejected (see below).
6. State economic development announcements and press releases
7. Trade press and owner or developer announcements

**2026-07-27 research session (no pull script written yet — this is source verification only, done ahead of `scripts/pull-md-*.py`; every URL/count/date below was fetched live, not taken from search results):**

## What works

- **Montgomery County commercial permits (Socrata)** —
  `https://data.montgomerycountymd.gov/resource/i26v-w6bd.json` (dataset
  `i26v-w6bd`, catalog page: `catalog.data.gov/dataset/commercial-permits`).
  Verified live 2026-07-27: `max(issueddate)` = 2026-07-24, 41,668 total
  records, **all already scoped to `applicationtype='COMMERCIAL BUILDING'`**
  (this is a commercial-only extract, not a mixed feed — no filter needed
  beyond that). 3,198 in the last 24 months. Has a real, populated **`city`
  field** (40,198 of 41,668 non-null, 96.5% fill rate) — this is the single
  biggest fix available for MD's near-zero city-field problem. Also has
  `usecode` (e.g. `RESTAURANT`, `BUSINESS BUILDING`, `RETAINING WALL`,
  `MULTIFAMILY DWELLING LOW RISE`), `worktype` (`CONSTRUCT`/`ALTER`),
  `declaredvaluation`, `buildingarea`, and a real `location` point
  (lat/lon) — no geocoding pass needed. `usecode='MULTIFAMILY DWELLING LOW
  RISE'` shows up under the commercial extract (condo/apartment permits
  routed through commercial review, same pattern NC hit with Wake County) —
  decide whether to keep per the corpus's multifamily policy.
  **Do not use** the ArcGIS layer `Commercial_Permits_since_2010`
  (`services2.arcgis.com/j80Jz20at6Bi0thr/.../FeatureServer/0`) that turns
  up first in web search for "Montgomery County commercial permits ArcGIS" —
  verified via `outStatistics` max-date query: despite the "since 2010"
  name and a schema-edit timestamp in 2023, its actual `Issue_Date` field
  maxes out at **2017-04-17** (11,224 total records). Frozen/abandoned;
  the live Socrata dataset above is the same underlying county data,
  current.

- **Baltimore City DHCD Building Permits (ArcGIS)** —
  `https://egisdata.baltimorecity.gov/egis/rest/services/Housing/DHCD_Open_Baltimore_Datasets/FeatureServer/3`
  (layer name "Building Permits"; the dataset page is
  `data.baltimorecity.gov/datasets/baltimore::housing-and-building-permits-2019-present`,
  which now redirects through ArcGIS Hub — the old `data.baltimorecity.gov`
  Socrata resource endpoint for this dataset (`fesm-tgxf`) is dead, only
  the Hub/FeatureServer route works now).
  Verified live 2026-07-27: `max(IssuedDate)` = 2026-07-26, 288,005 total
  records. Owner confirmed `baltimore_city` (real org, not a lookalike).
  `ProposedUse` is a clean categorical field but the dataset is
  residential-dominated (rowhouse/single-family trade permits); a
  **positive-signal exclusion list** works well: exclude
  `ProposedUse LIKE '%Dwelling%'/'%Family%'/'%Rowhouse%'/'%Duplex%'/'%Apartment%'/'%Townhouse%'`
  — real commercial values that survive include `Office`, `Retail Goods
  Establishment...`, `Restaurant`, `Warehouse`, `Hospital`, `Place of
  Worship`, `Financial Institution`, `Gas Station`, `Educational Facility`.
  25,584 non-residential-ish records in the last 24 months this way. No
  city field (Baltimore City only, one jurisdiction — `Neighborhood` and
  `Council_District` fields exist instead). No geometry-free issue — this
  layer has point geometry, unlike CT's Hartford table.

- **Baltimore County Cityworks Permits (ArcGIS)** —
  `https://bcgisdata.baltimorecountymd.gov/arcgis/rest/services/DevelopmentManagement/ActiveDevelopment/MapServer/4`
  (layer name "Cityworks Permits" — confirms Baltimore County runs
  Cityworks, the Tier-2 platform named in the research framework).
  Verified live 2026-07-27: `max(ISSDATE)` = 2026-07-25, 163,765 total
  records. `LANDUSE_TYPE` is a clean categorical field:
  `LANDUSE_TYPE IN ('COMMERCIAL','INDUSTRIAL','OFFICE','MIXED OFFICE/RETAIL','MIXED OFFICE/INDUSTRIAL','MIXED OFFICE/INDUSTRIAL/RETAIL')`
  → 3,661 in the last 24 months (4,995 `COMMERCIAL` all-time alone, plus
  1,524 `INDUSTRIAL`, 1,061 `OFFICE`). Rich schema: `OWNER_NAME`,
  `CONTRACTOR`, `ENGINEER_ARCHITECT`, `EST_COST`, `FLOOR_AREA`,
  `TENANT`, `LATITUDE`/`LONGITUDE` fields (not geometry-only), `ZIP`.
  Same host/service also has a companion "Active Development" layer at
  `MapServer/1` (title "Active Development") — not yet inspected in
  detail, worth checking next as a possible pre-permit pipeline source.

- **Prince George's County DPIE permits (Socrata)** —
  `https://data.princegeorgescountymd.gov/resource/weik-ttee.json`.
  Verified live 2026-07-27: `max(permit_issuance_date)` = 2026-07-19
  overall, 461,504 total records, real `city`/`zip_code` fields with
  genuine PG County MD towns (Laurel, Hyattsville, Brandywine, Capitol
  Heights, Upper Marlboro — not a lookalike). Commercial signal is a set
  of `permit_type` codes: `'DPIE CG'`, `'DPIE CGU'`, `'DPIE CGW'` (prefixed)
  plus `'CI'`, `'CIW'`, `'CU'`, `'CUW'`, `'CE'`, `'CEW'` (same commercial
  family, unprefixed — confirmed via sample records: `CU` = commercial-use
  interior renovations at named LLCs/shopping centers, `CE` = commercial
  exterior work, `CI` = commercial interior). **Real but low yield**: only
  ~199 records in the last 24 months across all these codes combined
  (18,457 all-time — this permit_type family was much higher-volume
  historically and has slowed sharply in recent years; not stale, since
  `max` among these codes is 2026-07-06, just genuinely lower current
  volume through this specific code family). Do not rely on this as the
  primary PG County source; treat as a supplementary/lower-priority add.
  **Do not use** the "Building Permit - Momentum (DPIE)" ArcGIS layer
  (`gisdata.pgplanning.org/arcgis/rest/services/Applications/Momentum_DPIE/MapServer/0`)
  despite its much richer schema (`PERMIT_OCCUPANCYTYPE_DESCRIPT`,
  `FLOORAREA`, `APPRVDCONSTRCOST`, `CITY`/`CORRECTED_CITY`) — verified via
  `outStatistics` max-date query: `max(ISSUANCE_DATE)` is **2024-06-28**,
  stale for over a year, and total count (15,669) is far below the live
  Socrata dataset's 461,504. This looks like an abandoned/frozen mirror,
  not the current DPIE feed.

## What failed last time

- **`data-cityofpg.opendata.arcgis.com` "Building Permit Applications"** —
  **wrong-jurisdiction trap**, same pattern as VT's Ontario/Burlington
  case. Top web-search hit for "Prince George's County building permits
  ArcGIS", named exactly like a Prince George's County MD dataset. Verified
  via the ArcGIS org's `portals/self` response: `urlKey: "CityofPG"`,
  `name: "City of Prince George"`, description references
  `princegeorge.ca` and `opendata.princegeorge.ca`, extent
  `[[-122.888,53.794],[-122.523,54.016]]` (northern British Columbia,
  Canada) and `culture: "en-ca"`. This is **City of Prince George, British
  Columbia, Canada** — completely unrelated to Prince George's County,
  Maryland. Confirmed before writing any pull code.
- **`aca-prod.accela.com/MONTCOOH`** — a plausible-looking Accela slug
  guess for "Montgomery County" that showed up in web search; the `OH`
  suffix is Montgomery County, **Ohio**, not Maryland. Not tested further
  once the slug's state suffix was noticed — same discipline as NC's
  Forsyth-County-GA trap: check the suffix/slug meaning before touching
  the portal.
- **`data-montcopa.opendata.arcgis.com`** — "montcopa" is Montgomery
  County, **Pennsylvania** ("MontCo PA"), confirmed via the portal's own
  page text ("Montgomery County Geospatial Data Portal" + "Pennsylvania").
  Not Montgomery County, MD.
- **Anne Arundel County "Permits Applied and Issued"**
  (`services2.arcgis.com/nUoGCkM6W8Wqdvvh/.../Permits_Applied_and_Issued/FeatureServer/0`) —
  live and real, but confirmed via field inspection to be a **monthly
  aggregate table** (`Fiscal_Year`, `Month`, `Permit_Type`, `Applied`,
  `Issued` counts — only 162 rows total, one per month/type), not
  project-level records. Same rejection pattern as Georgia's Fulton County
  Socrata `p3f6-ug7s`. Anne Arundel's real per-permit system is **Accela
  Citizen Access** (`aca-prod.accela.com/aaco/Default.aspx`, confirmed live
  2026-07-27, page title/content references "Anne Arundel"), branded
  publicly as "Land Use Navigator" — not yet automated (would need the
  Playwright/network-interception approach from the GA/NC playbooks, not
  a direct API).
- Old `data.baltimorecity.gov` Socrata resource endpoint for building
  permits (`/resource/fesm-tgxf.json`) — returns an HTTP redirect to
  `hub.arcgis.com/legacy` instead of data; Baltimore City has migrated this
  dataset fully to the ArcGIS Hub/FeatureServer route documented above.
  Don't use the old Socrata resource ID.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.
- Montgomery County: no filter needed — dataset is pre-scoped to `applicationtype='COMMERCIAL BUILDING'`. Decide on `usecode='MULTIFAMILY DWELLING LOW RISE'` per the corpus's multifamily policy.
- Baltimore City: require `ProposedUse` to **not** match `Dwelling|Family|Rowhouse|Duplex|Apartment|Townhouse` (positive-exclusion, not a positive-commercial-signal requirement — the VT lesson doesn't fully apply here since `ProposedUse` values are specific enough that exclusion alone is clean).
- Baltimore County: `LANDUSE_TYPE IN ('COMMERCIAL','INDUSTRIAL','OFFICE','MIXED OFFICE/RETAIL','MIXED OFFICE/INDUSTRIAL','MIXED OFFICE/INDUSTRIAL/RETAIL')`.
- Prince George's County: `permit_type IN ('DPIE CG','DPIE CGU','DPIE CGW','CI','CIW','CU','CUW','CE','CEW')`.

## Pull commands

**Built 2026-07-27**: `scripts/pull-md-montgomery.py` (Montgomery County
Socrata, `applicationtype='COMMERCIAL BUILDING'` — pre-scoped to
commercial by construction, no extra filter needed). First 24-month
pull: 3,198 real commercial permits.

Baltimore City, Baltimore County, and Prince George's County are
verified live (see "What works" above) but not yet built — next step is
`scripts/pull-md-baltimore.py` (ArcGIS, both city and county) following
the same pattern.

```bash
python3 scripts/pull-md-montgomery.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Maryland — two confirmed wrong-jurisdiction traps this session: `data-cityofpg.opendata.arcgis.com` (Prince George, **British Columbia, Canada**) and `data-montcopa.opendata.arcgis.com` (Montgomery County, **Pennsylvania**). Also `aca-prod.accela.com/MONTCOOH` (Montgomery County, **Ohio**).
- Zip-code aggregate datasets with no project-level records — Anne Arundel's "Permits Applied and Issued" ArcGIS layer is a monthly Fiscal_Year/Month/Permit_Type count table, not permit records.
- `Commercial_Permits_since_2010` ArcGIS layer for Montgomery County (`services2.arcgis.com/j80Jz20at6Bi0thr/...`) — stale since 2017-04-17 despite the name; use the live Socrata dataset (`i26v-w6bd`) instead.
- `Momentum_DPIE` ArcGIS layer for Prince George's County (`gisdata.pgplanning.org/.../Momentum_DPIE/MapServer/0`) — stale since 2024-06-28; use the live Socrata dataset (`weik-ttee`) instead.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 3 projects |
| 2026-07-27 | Montgomery County Socrata (`applicationtype='COMMERCIAL BUILDING'`) | +3,198 projects, 4,392 total |
| 2026-07-27 | Research/verification pass only (no pull script run, corpus unchanged): Montgomery County (Socrata), Baltimore City DHCD (ArcGIS), Baltimore County Cityworks (ArcGIS), PG County DPIE (Socrata) confirmed live; PG Momentum ArcGIS, Montgomery `Commercial_Permits_since_2010` ArcGIS, AA County aggregate table, and two wrong-jurisdiction traps (Prince George BC Canada, Montgomery Co PA) rejected | 0 projects added — see "What works"/"What failed" above for exact endpoints ready to build against |
