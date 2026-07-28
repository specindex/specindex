# Pennsylvania Commercial Source Playbook

Read this file before refreshing `data/states/pa.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** PA (Pennsylvania)  
**Corpus file:** `data/states/pa.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 5  
**Counties:** 5 · **Cities:** 5  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — local news, PR Newswire, REBusinessOnline, state economic development.  
**Status mix:** under_construction 5
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Philadelphia L&I Building & Zoning Permits** (Carto SQL API) —
  `https://phl.carto.com/api/v2/sql`. Verified live 2026-07-26/27:
  928,254 total rows, fresh to same-day.
  **Real, important filter lesson (inverted from the usual case)**:
  `commercialorresidential='Commercial'` does **not** mean commercial
  *use* — Philadelphia's field is an administrative bucket (3+ units
  routes to "Commercial"), and a sample of "Commercial" + "New
  Construction" records was at least 68% actual apartment buildings.
  Fixed by ignoring that field entirely and requiring a positive
  non-residential keyword (RETAIL/OFFICE/WAREHOUSE/HOTEL/RESTAURANT/
  COMMERCIAL/MEDICAL/INDUSTRIAL/STORE/BANK/SCHOOL/CHURCH) in
  `approvedscopeofwork`, excluding "household living"/"dwelling"
  language. No cost/valuation field exists on this dataset at all (a
  real gap vs. most other states). Coordinates (`geocode_x`/`geocode_y`)
  are in PA State Plane South feet (EPSG:2272), not lat/lon — left null
  rather than doing a projection conversion. Built into
  `scripts/pull-pa-philadelphia.py`.
- **Pittsburgh PLI Permits** (WPRDC CKAN datastore) — verified live by
  the research pass (63,776 rows, fresh to 2026-07-24, real
  `total_project_value` field unlike Philadelphia). Not yet built into a
  pull script — same "Commercial" field caveat likely applies at smaller
  scale (one sampled "Commercial" new-construction record was an 8-unit
  apartment building).
- **PA RACP (Redevelopment Assistance Capital Program) 2025 round** —
  statewide XLSX, verified live (`Last-Modified` days old), 840 real
  project rows with County/Municipality/Amount Requested/Amount
  Awarded/Description. PA's real equivalent of Georgia's DRI. Not yet
  built (needs XLSX parsing, a different code path than the JSON/SODA
  sources used elsewhere) — good next step given it's small, clean, and
  statewide.

## What failed last time

- Allegheny County-wide building permits (distinct from City of
  Pittsburgh) — confirmed via WPRDC catalog search not to exist; county
  only publishes asbestos permits/plumber licenses/property data.
  Pennsylvania permits are municipality-level, same structural finding as
  Vermont's town-level-only permitting.
- Montgomery County, PA and Bucks County, PA ArcGIS permit layers — top
  search hits for "Montgomery County permits" were **Montgomery County,
  MARYLAND** (same wrong-jurisdiction trap as Burlington VT/ON). No real
  PA Montgomery/Bucks County permit dataset found.
- PA DEP eFACTS/ArcGIS "Air Emissions Plants" layers — real and live, but
  these are existing-facility inventories, not a plan-approval/new-permit
  register; wrong shape of data (no construction-pipeline signal).
- PA DCED cumulative RACP "Past and Present Grantee List" (`.xls`) —
  `Last-Modified: 2024-07-11`, stale; superseded by the per-round file above.
- PA PUC large-load dockets — real and relevant (data centers/heavy
  industrial), but the PUC only exposes a web-search UI, no REST/bulk
  API found; would need Playwright-style docket scraping, not yet
  attempted.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.
- Philadelphia specifically: never trust `commercialorresidential` alone — require a positive keyword match on `approvedscopeofwork` (see above).

## Pull commands

```bash
python3 scripts/pull-pa-philadelphia.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Pennsylvania.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 5 projects |
| 2026-07-27 | Philadelphia L&I permits (positive-keyword commercial filter) | +738 projects, 1,088 total |
