# Vermont Commercial Source Playbook

Read this file before refreshing `data/states/vt.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** VT (Vermont)  
**Corpus file:** `data/states/vt.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — state permits, local news.  
**Status mix:** under_construction 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. Act 250 (statewide land-use review, VT's real DRI equivalent) — verified live, built.
2. Burlington OpenGov Building Permits (largest city) — verified live, built.
3. Other municipal permit open data (Rutland, Montpelier, etc.) — not yet researched.

## What works

- **Act 250** — `http://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASBASEMAPLITE_WM_NOCACHE/MapServer/2`.
  Verified live 2026-07-26: 8,278 total records, statewide. No date field
  on the layer (freshness can't be checked directly; treat as a rolling
  full-history register). Fields: `AppNum`, `AppType`, `ProjectName`,
  `ProjectTown`, `District`, `Status`, `Description`, `GisLatitude`,
  `GisLongitude`, `LINK` (real per-application detail page).
  **Important filter lesson**: Act 250 covers everything from commercial
  buildings to gravel pits, farms, solid-waste sites, and utility poles —
  the usual "keep unless residential hint fires" rule let 6,934 of 8,278
  records through (spot-checked, mostly noise). Fixed by requiring a
  **positive** commercial/building signal (`COMMERCIAL_HINTS` must match,
  not just absence of `RESIDENTIAL_HINTS`) — cut to 1,457 real
  commercial/institutional records (hotels, bank branches, retail,
  restaurants, school additions). Built into
  `scripts/pull-county-arcgis.py` (`pull_act250`, `--only act250`).
- **Burlington OpenGov Building Permits** — `https://services1.arcgis.com/1bO0c7PxQdsGidPK/arcgis/rest/services/OpenGov_Building/FeatureServer/0`.
  Verified live 2026-07-26: Feature Layer with **direct Latitude/Longitude
  fields** (no geometry query needed), fresh to ~April 2026.
  `PrimaryLUC IN ('C - Commercial','I - Industrial','CC - Comm Condo','CR - Com/Resident')`
  is a real categorical filter. Filtered to `EstimatedConstructionCost > $25,000`
  to drop trivial sign-repair/drywall-patch permits. Built into
  `scripts/pull-county-arcgis.py` (`pull_burlington`, `--only burlington`).
  Companion `OpenGov_Zoning`/`OpenGov_Fire_Marshal` FeatureServers exist at
  the same org, not yet pulled.

## What failed last time

- `navburl-burlington.opendata.arcgis.com` "Building Permits" (top web
  search hit for "Burlington VT building permits") — **wrong-jurisdiction
  trap**: its DCAT feed resolves to `mapping.burlington.ca`, which is
  Burlington, Ontario, Canada, not Burlington, Vermont. Confirmed via the
  DCAT `accessURL` field before use, not after.
- No county-level permit API exists — Chittenden County/CCRPC is a
  planning body, not a permit issuer; VT permits are issued at the town
  level with no county aggregation layer.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.
- For Act 250 specifically: require a positive `COMMERCIAL_HINTS` match, don't just rely on absence of a residential hint (see above).

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only act250,burlington --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Vermont (see the Ontario/Burlington trap above).
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
| 2026-07-26 | Act 250 (positive-commercial-signal filter) + Burlington OpenGov (`PrimaryLUC`, >$25K) | +1,580 projects, 1,650 total |
