# Connecticut Commercial Source Playbook

Read this file before refreshing `data/states/ct.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** CT (Connecticut)  
**Corpus file:** `data/states/ct.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 8  
**Counties:** 4 · **Cities:** 7  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Web research — New Haven Independent, Hartford Courant, CT Insider, CT.gov, Construction Review Online  
**Status mix:** under_construction 5, planning 3
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. Hartford Building Permits ArcGIS table (Tier 1, county/city) — verified live, built.
2. State economic development announcements and press releases
3. Trade press and owner or developer announcements

## What works

- **Hartford Building Permits ArcGIS Table** —
  `https://utility.arcgis.com/usrsvcs/servers/d595ae995fb049d3ac54919ebf24b1ac/rest/services/HartfordOpenDataTables/FeatureServer/0`.
  Verified live 2026-07-26: 35,691 total records, fresh to within the last
  month (`DateIssued` max ~2026-06-29). `RECORD_TYPE_TYPE='Commercial'`
  cleanly separates commercial from residential/temporary-structure
  records — no keyword filtering needed on top of it. Real fields:
  `RECORD_ID`, `DESCRIPTION`, `B1_APP_TYPE_ALIAS`, `PROPERTY_ADDRESS`,
  `PROPERTY_CITY`, `Total_Construction_Cost`, `DateIssued` (epoch ms). It's
  a Table, not a Feature Layer — **no geometry, no lat/lon** (only a text
  address), so projects land with `latitude`/`longitude` null until a
  geocoding pass exists (see `docs/ROADMAP.md` item 54). Built into
  `scripts/pull-county-arcgis.py` (`pull_hartford`, `--only hartford`):
  6,037 commercial projects on first pull (24-month window).
- Two more Hartford tables at the same host/schema family found but not
  yet pulled: Planning Permits (`FeatureServer/3`) and Public Works
  Permits (`FeatureServer/4`) — same live host, worth adding later.

## What failed last time

- New Haven open data: no working DCAT catalog at either guessed host
  (`opendata-newhavenct.hub.arcgis.com`, `data-newhavenct.opendata.arcgis.com`
  both 404 as of 2026-07-26). New Haven's public GIS presence looks like
  individual embedded web apps, not a discoverable open-data hub — would
  need a more targeted search, not confirmed to not exist.
- CT DECD Business Assistance Portfolio (Socrata `data.ct.gov` resource
  `xnw3-nytd`) — live and real, but it's a small-business working-capital
  grant/loan program (landscaping, restaurants, ticket resale in the
  sample), not construction-project data. Rejected for relevance, not
  liveness.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only hartford --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Connecticut.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 8 projects |
| 2026-07-26 | Hartford Building Permits ArcGIS (`RECORD_TYPE_TYPE='Commercial'`) | +6,037 projects, 6,127 total |
