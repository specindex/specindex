# Indiana Commercial Source Playbook

Read this file before refreshing `data/states/in.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** IN (Indiana)  
**Corpus file:** `data/states/in.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — WNDU, local news.  
**Status mix:** under_construction 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Indianapolis/Marion County Accela** (slug `INDY`) —
  `https://aca-prod.accela.com/INDY/Cap/CapHome.aspx?module=Permits&TabName=HOME`.
  Verified live 2026-07-26: HTTP 200, real search form present (same
  markers used to confirm GA's Atlanta/Concord Accela — `ddlGSPermitType`,
  `generalSearchForm`, date-range fields). Commercial signal is the 3rd
  path segment `Non-Residential`, e.g. `Permits/Structural/Non-Residential/NA`,
  `Permits/Improvement Location Permit/Non-Residential/NA`,
  `Permits/Electrical/Non-Residential/NA`. **Not yet built** — same
  raw-HTTP-form-POST approach as `scripts/pull-ga-accela-commercial.py`
  should work, but that script is a real lift (cookie jar, ASP.NET
  viewstate parsing, date-window pagination); reuse its pattern rather
  than starting from scratch.

## What failed last time

- Indiana IEDC Transparency Portal (`transparencyportal.iedc.in.gov`) —
  this is exactly the Tier-0 statewide structured incentive/project
  database (real per-project contract PDFs found via leaked search-result
  URLs), but every `/api/*` path tested returned HTTP 500 with a genuine
  ASP.NET `ConfigurationErrorsException` (server misconfiguration, not a
  bad request — tested GET, empty POST, and a plausible payload against
  both the canonical and `secure.in.gov` hosts, all identical error).
  Worth a retry later; do not build against it until it's confirmed live.
- Indianapolis/Marion County open data (`data.indy.gov`, IndyGIS ArcGIS
  org) — full DCAT catalog checked, zero building-permit or
  commercial-construction datasets (only zoning text, building footprints
  with no attributes, boundaries). IndyGIS's own ArcGIS REST endpoint
  (`xmaps.indy.gov/arcgis/rest/services/OpenData`) requires an auth token.

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

- Generic ArcGIS Hub search without verifying the layer covers Indiana.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
