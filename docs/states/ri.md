# Rhode Island Commercial Source Playbook

Read this file before refreshing `data/states/ri.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** RI (Rhode Island)  
**Corpus file:** `data/states/ri.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 5  
**Counties:** 5 · **Cities:** 5  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — Providence Business News, local news, permits, trade journals.  
**Status mix:** under_construction 4, planning 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Providence Development Project Mapper** — two ArcGIS FeatureServers:
  `Pipeline_Development_Projects/FeatureServer/0` (85 records, in-progress)
  and `Completed_Development_Projects/FeatureServer/0` (97 records).
  `https://services6.arcgis.com/wv9mHoqblhTsnqdG/arcgis/rest/services/`.
  Verified live 2026-07-26: actively maintained (parent item modified
  2026-07-15). Direct `Latitude`/`Longitude` fields. This is a
  hand-curated planning-department tracker, not a permit feed — no
  date/value/sqft fields, small volume, needs text classification
  (mixes commercial/institutional/some residential). Built into
  `scripts/pull-county-arcgis.py` (`pull_providence`, `--only providence`).

## What failed last time

- Providence's own Socrata portal (`data.providenceri.gov`) — only
  permit-shaped dataset is explicitly titled "...Permits 2009-2018," last
  updated 2020-01-24. Closed historical range, not live.
- RI Statewide E-Permitting Portal (`ribcc.ri.gov`) — real, but confirmed
  to be an application-*submission* system (login required), not a public
  read/search API. Routes to per-municipality OpenGov instances
  (`rhodeisland.portal.opengov.com`) not individually tested yet.
- RIGIS (`rigis-edc.opendata.arcgis.com`) — full DCAT feed checked (387
  datasets), zero contain "permit" in the title. No statewide GIS permit
  layer exists for RI.
- **Socrata catalog API gotcha**: `api.us.socrata.com/api/catalog/v1`
  searches the entire nationwide Socrata network by default — an
  unscoped RI query returned Chicago/Orlando/Calgary/NYC results that
  look like RI hits unless `domains=data.providenceri.gov` is added.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only providence --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Rhode Island.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 5 projects |
| 2026-07-26 | Providence Development Project Mapper (Pipeline + Completed) | +128 projects, 204 total |
