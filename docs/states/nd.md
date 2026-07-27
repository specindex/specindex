# North Dakota Commercial Source Playbook

Read this file before refreshing `data/states/nd.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** ND (North Dakota)  
**Corpus file:** `data/states/nd.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — DCD, local economic development.  
**Status mix:** planning 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Fargo Site Plans** — `https://gis.cityoffargo.com/arcgis/rest/services/General/SitePlans/MapServer/0`.
  Verified live 2026-07-26: 3,279 total records, max `DATE` 2026-06-26.
  This is a pre-construction site-plan review layer, not a permit feed —
  minimal schema (`ADDRESS`, `SECTION`, `NAME`, `DATE`), **no
  commercial/residential categorical field, no valuation**. Fargo doesn't
  require site-plan review for single-family homes, so the layer skews
  commercial/institutional by construction, but still needs text
  classification (`RESIDENTIAL_HINTS`/`COMMERCIAL_HINTS`) since there's
  no field to filter on directly. Built into
  `scripts/pull-county-arcgis.py` (`pull_fargo`, `--only fargo`).

## What failed last time

- West Fargo "Permit Lookup" ArcGIS app — real and live, but confirmed
  (via Esri's own case study) to track right-of-way excavation permits,
  not building/commercial construction. Not relevant.
- Bismarck — a "Building_Permits_gdb" ArcGIS item surfaced in search but
  is actually owned by a Montgomery, Alabama account — wrong-jurisdiction
  false positive. No real Bismarck permit dataset found.
- ND Public Service Commission Energy Conversion/Transmission Facility
  Siting (50MW+ threshold) — real statutory process confirmed, but no
  structured docket list/API found on the pages checked; would need to
  dig into meeting-minutes pages for an actual filing list.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only fargo --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers North Dakota.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
| 2026-07-26 | Fargo Site Plans (text-classified) | +1,148 projects, 1,301 total |
