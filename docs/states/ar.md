# Arkansas Commercial Source Playbook

Read this file before refreshing `data/states/ar.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** AR (Arkansas)  
**Corpus file:** `data/states/ar.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 6  
**Counties:** 6 · **Cities:** 6  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Web research — Cypress Creek Energy, ENR, Arkansas Business, Arkansas Advocate, Serverfarm, AVAIO Digital  
**Status mix:** under_construction 3, planning 2, completed 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Bentonville Building Permits** — `https://gis.bentonvillear.com/arcgis/rest/services/Planning/Community_Development23/MapServer/188`.
  Verified live 2026-07-26: 50,456 total historical records, max `ISSUED`
  2026-07-17 (9 days old). `PERMIT_TYPE LIKE '%COM%'` separates
  commercial. **CAVEAT — real data-quality trap**: some records have bad
  future-dated `ISSUED` values (unfiltered max = 2026-12-06) — the pull
  script clamps `ISSUED <= today`, don't trust the raw max blindly.
  Direct `LAT`/`LON` fields, no geometry query needed. Built into
  `scripts/pull-county-arcgis.py` (`pull_bentonville`, `--only bentonville`).
  This is Bentonville-only (unincorporated-city-level) — same platform
  likely exists for Rogers/Fayetteville/Springdale but their GIS
  hostnames weren't found (DNS failures on guessed URLs).

## What failed last time

- Rogers (Cityworks PLL) and Fayetteville (Tyler EnerGov) — both real,
  live portals but surface as login-required Citizen Self Service SPAs;
  no public JSON search endpoint found via direct HTTP probing. Would
  need headless-browser network interception to confirm either way.
- Little Rock (`data.littlerock.gov`, `maps.littlerock.gov`) — every
  guessed endpoint 404'd. Could not locate a working URL at all; needs
  fresh discovery, not confirmed dead.
- Arkansas Economic Development Commission — only narrative program pages
  and periodic grant-award press releases, no structured/API-backed
  project database found.

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

- Generic ArcGIS Hub search without verifying the layer covers Arkansas.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 6 projects |
