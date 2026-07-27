# Delaware Commercial Source Playbook

Read this file before refreshing `data/states/de.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** DE (Delaware)  
**Corpus file:** `data/states/de.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 4  
**Counties:** 2 · **Cities:** 4  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Web research — Delaware Business Times, ENR, St. John Properties, Delaware Online  
**Status mix:** under_construction 3, planning 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Statewide Building Permits layer** — `https://enterprise.firstmap.delaware.gov/arcgis/rest/services/PlanningCadastre/DE_Planning_Development/MapServer/3`.
  Verified live 2026-07-26: 79,000 total records, all 3 counties
  (`COUNTY` field). Real `R_NR` flag (`R`/`NR`/`Mixed`) — filtered to
  `NR`/`Mixed` for non-residential. Fields: `NR_SF`, `NOTES` (address
  text, no project name), `RECTYPE`, `P_YEAR`, `JURISDICTION`.
  **CAVEAT — confirmed stale**: max `P_YEAR` = 2024; `P_YEAR=2025`
  returns 0 records. Real, but not current — still a substantial one-time
  depth addition. Built into `scripts/pull-county-arcgis.py`
  (`pull_delaware`, `--only delaware`). No lat/lon (Table-only fields, no
  geometry query attempted — should double check whether the layer
  actually has geometry, since this was pulled with the standard
  `query_layer()` helper which requests it).

## What failed last time

- New Castle County ArcGIS Hub "Development Activity- Download" —
  resolves to a static zip export, not a queryable REST endpoint;
  catalog metadata last modified 2022-11-03.
- Wilmington OpenGov "Transparency Portal" — confirmed to exist but is a
  financial/budget transparency tool, not a permit database; the actual
  permit lookup wasn't reached.
- No municipal-level ArcGIS permit layers found for New Castle
  County/Wilmington/Dover — only parcels/zoning/addressing in their open
  data catalogs, no permits.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Delaware.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 4 projects |
