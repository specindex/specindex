# Kansas Commercial Source Playbook

Read this file before refreshing `data/states/ks.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** KS (Kansas)  
**Corpus file:** `data/states/ks.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — Johnson County Post, local news.  
**Status mix:** planning 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Overland Park Building Permit Report** — `https://maps.opkansas.org/mapping/rest/services/MixedInfo/Building_Permit_Report/MapServer/0`
  (Johnson County, KC metro). Verified live 2026-07-26: max `IssueDate`
  2026-07-23 (3 days old). `ReportPermitType` cleanly separates
  commercial (`New Commercial`, `Other Commercial`,
  `New Institutional, Churches, and Schools`) from residential types.
  **CAVEAT**: the service's own metadata description says it was
  "specifically created for Teri in IT... for school lookup" — an
  unofficial/ad-hoc extract, not a documented open-data product. Could be
  renamed or pulled without notice; re-check liveness before relying on
  it long-term. Built into `scripts/pull-county-arcgis.py`
  (`pull_overland_park`, `--only overland_park`).

## What failed last time

- Wichita city ArcGIS Hub (143 datasets checked via DCAT) and Sedgwick
  County GIS Hub (43 datasets) — no permit/building/commercial dataset in
  either. "Wichita Zoning Cases" layer exists but is zoning-case
  tracking, not permits.
- Johnson County AIMS open-data portal (89 datasets) — no permit dataset;
  only boundary/district layers.
- Unified Government of Wyandotte County (KCK) "Building Permits" page
  exists but no underlying REST/FeatureServer URL was resolved — needs a
  headless-browser check, not confirmed dead.
- Kansas Commerce "Transparency Database Explorer" (BASE) — real
  incentive-award database described on the page, but loads via JS into
  a blank iframe with no static endpoint found in raw HTML.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only overland_park --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Kansas.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
| 2026-07-26 | Overland Park Building Permit Report (`ReportPermitType` commercial set) | +1,047 projects, 1,192 total |
