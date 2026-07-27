# Michigan Commercial Source Playbook

Read this file before refreshing `data/states/mi.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** MI (Michigan)  
**Corpus file:** `data/states/mi.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — ENR, industry news.  
**Status mix:** under_construction 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Detroit BSEED Building Permits** (ArcGIS FeatureServer) —
  `https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/bseed_building_permits/FeatureServer/0`.
  Verified live 2026-07-27: 46,148 total records, max `issued_date` =
  today. Real IBC `use_group` field (M/B/A/E/U vs R-2/R-3) is the clean
  categorical signal but frequently null (497 records/24mo with the
  strict filter alone) — combined with a positive text match on
  `proposed_use_type` as a backstop (1,257 records/24mo combined).
  **`record_id` prefix (BLD/RES) is NOT a reliable filter** — sampled
  BLD* records include single-family alterations. Built into
  `scripts/pull-county-arcgis.py` (`pull_detroit`, `--only detroit`).
- **Michigan Business Development Program (MBDP) + Community
  Revitalization Program (CRP) project lists** (michiganbusiness.org) —
  verified live, real paginated HTML (~460 + ~240 real projects,
  city-level location, investment amount, approval date). No API/CSV —
  would need an HTML scrape, not yet built. Not every grant funds new
  construction; needs a positive construction-signal filter before use.

## What failed last time

- `services6.arcgis.com/ONZht79c8QWuX759/.../Building_Permits/FeatureServer`
  — same generic wrong-jurisdiction decoy already flagged for NC/TX/WA
  searches (Year/Quarter aggregate stats table, not per-project records).
- Wayne County and Washtenaw County ArcGIS Hubs — full DCAT feeds
  checked, zero permit/building datasets in either (imagery, census, tax
  maps only). Permitting is issued at the city level (Detroit/Ann Arbor),
  not county.
- Grand Rapids GRData — 22 datasets checked, none permit-related; city's
  real system is Accela (`aca-prod.accela.com/GRANDRAPIDS`, confirmed
  live but needs Playwright, not yet attempted).
- Ann Arbor STREAM (Tyler EnerGov) and MiEnviro/MPSC E-Dockets — real
  platforms confirmed to exist (help-guide PDF, docket number matching an
  existing corpus record) but blocked/unverifiable via direct HTTP (403s)
  in this pass; would need a real browser session.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only detroit --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Michigan.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
| 2026-07-27 | Detroit BSEED (use_group + positive-text backstop) | +1,257 projects, 1,437 total |
