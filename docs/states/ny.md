# New York Commercial Source Playbook

Read this file before refreshing `data/states/ny.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** NY (New York)  
**Corpus file:** `data/states/ny.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 3  
**Counties:** 3 · **Cities:** 3  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — ENR, Construction Dive, press releases, ConstructConnect public news. No plan-room scraping.  
**Status mix:** under_construction 3
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. NYC Capital Projects Database (CPDB), Socrata (Tier 0 statewide-ish — NYC is most of the state's activity) — verified live, built.
2. Municipal permit open data for other NY metros (Buffalo, Rochester, Albany, Syracuse) — not yet researched.
3. Trade press and owner or developer announcements

## What works

- **NYC Capital Projects Database (CPDB)**, Socrata, `data.cityofnewyork.us`:
  - Projects/budget dataset `fi59-268w` — verified live 2026-07-26, 12,587
    total rows. `typecategory='Fixed Asset'` (7,222 rows) isolates real
    physical construction, excluding `Lump Sum` and `ITT, Vehicles, and
    Equipment` line items. Filtered to `totalplannedcommit > $1,000,000`:
    2,959 meaningfully-sized rows.
  - Geospatial companion `h2ic-zdws` (Points, joined by `projectid`) —
    verified live, real lat/lon via `the_geom` (MultiPoint). Only ~28% of
    projects have a matching point (844 of 2,957 pulled) — budget-stage
    line items often don't have a physical footprint assigned yet; the
    rest land with null coordinates (handled by the "Regional location
    pending" UI fallback, not a bug).
  - This is **city capital construction** (libraries, schools, hospitals,
    parks, public buildings), not private commercial development — same
    category as the SAM.gov/USAspending federal-contract records already
    in the corpus. Classified by agency name (Library/Parks/Fire/etc. →
    `civic`, Education/CUNY → `education`, Health and Hospitals → `healthcare`)
    since CPDB rows are budget-line descriptions, not permit narratives.
  - Built into `scripts/pull-ny-nyc-capital-projects.py`: 2,957 projects
    on first pull (>= $1M threshold).

## What failed last time

- Update after each pull with dead links, wrong layers, residential noise, and dedupe traps.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-ny-nyc-capital-projects.py --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers New York.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 3 projects |
| 2026-07-26 | NYC Capital Projects Database (CPDB), `typecategory='Fixed Asset'`, >=$1M | +2,957 projects, 3,497 total |
