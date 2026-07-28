# Florida Commercial Source Playbook

Read this file before refreshing `data/states/fl.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** FL (Florida)  
**Corpus file:** `data/states/fl.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 11  
**Counties:** 8 · **Cities:** 11  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Web research — Florida Construction News, REBusinessOnline, Florida YIMBY, WLRN, GrowthSpotter, MCD Magazine  
**Status mix:** under_construction 6, planning 5
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Miami-Dade County commercial permits** (ArcGIS Table) —
  `https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/miamidade_permit_data/FeatureServer/0`.
  Verified live 2026-07-27: 139,870 total records, max `PermitIssuedDate`
  = today. `ResidentialCommercial='C'` (55,728 of total) is real but
  buckets 5+-unit multifamily as "commercial" for permitting purposes —
  excluded via `ProposedUseDescription NOT LIKE '%RESIDENTIAL%'`. Has a
  real `City` field (fixes this state's city-field gap directly). A
  Table, no geometry — no lat/lon. **Perf lesson**: filtering
  `CAST(EstimatedValue AS FLOAT) > 25000` server-side, combined with deep
  OFFSET pagination, reliably timed out (computed predicate can't use an
  index) — fixed by pulling the cheap categorical/date filter only and
  applying the $25K value floor client-side in Python instead. Built into
  `scripts/pull-county-arcgis.py` (`pull_miamidade`, `--only miamidade`).
- **Hillsborough County (Tampa) Accela** (slug `HCFL`) — verified live
  (real search-form markers), same platform as
  `scripts/pull-ga-accela-commercial.py`. Not yet built — port that
  script's pattern with the new slug.
- **PA RACP**-style statewide Tier-0 lead not found for FL yet; Florida
  DEP Environmental Resource Permits (`ca.dep.state.fl.us/arcgis/rest/services/OpenData/ERP/MapServer/1`,
  68,042 records, fresh to yesterday) verified live but is water/wetland
  permitting only — no building type/valuation/sqft field, low relevance,
  treat as a text-filtered supplementary signal at most, not a primary
  driver.

## What failed last time

- Broward County GeoHub — only stormwater/SWM licensing datasets found,
  no building-permit dataset. Broward's real permit lookup
  (`dpepp.broward.org/BCS`) is a legacy ASP.NET webforms app (403 without
  a browser UA) — unresolved, not confirmed dead.
- Orange County (Orlando) — no county-level building-permit dataset in
  933 open-data catalog entries; one real FeatureServer found
  (`OC_Construction/Construction_Management_CIP_Projects`) but only 51
  records of county-owned capital projects, not private development. City
  of Orlando's own permit lookup is Cloudflare-blocked (403).
- Duval County/Jacksonville — no public ArcGIS/Socrata dataset found;
  real system (JaxEPICS, Tyler EnerGov-based) has no verified public API.
- FloridaCommerce economic-development portal — HTTP 403 (bot-protected),
  could not verify whether it's a real database or static PDFs.
- Florida PSC large-load/data-center dockets — filings exist only as
  individual PDFs, no structured docket-search API found.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only miamidade --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Florida.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 11 projects |
| 2026-07-27 | Miami-Dade County commercial permits (`ResidentialCommercial='C'`, value>$25K) | +20,366 projects, 21,152 total |
