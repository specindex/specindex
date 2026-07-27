# Virginia Commercial Source Playbook

Read this file before refreshing `data/states/va.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** VA (Virginia)  
**Corpus file:** `data/states/va.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 6  
**Counties:** 6 · **Cities:** 6  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — Commercial Observer, Data Center Knowledge, press releases, state economic development.  
**Status mix:** planning 3, under_construction 2, permitting 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Fairfax County "Recent Building Permits - Parcels"** (ArcGIS
  FeatureServer) — `https://www.fairfaxcounty.gov/lambert/rest/services/LDS/DevelopmentTracker/FeatureServer/5`.
  Verified live 2026-07-27: 10,746 total records, max `ISSUED_DATE` = 4
  days old. `APPTYPEALIAS` is a clean categorical field (`Commercial New`,
  `Commercial Addition/Alteration`). **Bonus: a real `DATA_CENTER`
  Yes/No field** — direct hit on "Data Center Alley" (Reston/Herndon/
  Chantilly): CoreSite VA3-2A Phase 2A ($90M), H5 Data Centers, EDS/Amazon
  Bldg A/B/C, Renaissance Tech Park all confirmed live. Polygon (parcel)
  geometry, not point — left lat/lon null rather than risk a bad centroid
  extraction. Built into `scripts/pull-county-arcgis.py` (`pull_fairfax`,
  `--only fairfax`).
- **Virginia Beach "Building Permits Applications"** (ArcGIS
  FeatureServer, 103,116 total, fresh to 3 days) — verified live,
  `ConstructionType='Commercial'` (17,622 records) is the real filter
  (`PermitType` is a trade category, not commercial/residential — don't
  filter on it). `IssueDate` is a **string** field (`"YYYY/MM/DD"`), not
  epoch — needs string parsing, not a `DATE` SQL literal. Not yet built.
- **Richmond "Development Tracker"** (ArcGIS FeatureServer, 370 total,
  hand-curated, ~4.5mo stale but actively maintained) — clean
  `LandUse_Type` categorical field, only "projects over $1.5M" tracker
  found for any VA city. Not yet built.
- Prince William County "Use Permits" — real but small-scale zoning-case
  layer (SUPs/NCUs like car washes, cell towers), not general commercial
  building permits; PWC's real Data-Center-Alley volume runs through a
  Tyler EnerGov ePortal with no public feed found. Low priority add.

## What failed last time

- Loudoun County ArcGIS building-permit layers — confirmed 100%
  residential categories (zero commercial values exist in the schema) and
  stale (max date 2018). Loudoun's real commercial permitting runs on
  Tyler EnerGov/LandMARC with no public open-data feed found.
- Loudoun "Major Development Projects" — real but only 19 total records,
  negligible volume.
- VEDP incentives reporting — real, current, structured company/
  investment/jobs data, but PDF-only (no CSV/API); would need a PDF-table
  extraction pipeline like `scripts/extract-spec-book.py`.
- VA DEQ "Issued Air Permits for Data Centers" — page exists but 403s to
  both WebFetch and curl; not verified live.
- VA Permit Transparency (DEQ) — embedded Power BI report, no REST API.
- VA SCC large-load-connection-queue filing — real and confirms Dominion
  has ~70,000 MW aggregate data-center connection requests pending, but
  it's a policy/process filing, not a named-project registry — no
  addresses or per-project MW figures.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only fairfax --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Virginia.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 6 projects |
| 2026-07-27 | Fairfax County (`APPTYPEALIAS` commercial set, `DATA_CENTER` flag) | +1,771 projects, 2,563 total |
