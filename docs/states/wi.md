# Wisconsin Commercial Source Playbook

Read this file before refreshing `data/states/wi.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** WI (Wisconsin)  
**Corpus file:** `data/states/wi.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 5  
**Counties:** 5 · **Cities:** 5  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — DCD, Innovatrix, HNG News, GMToday, industrial news.  
**Status mix:** under_construction 4, planning 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Milwaukee Residential and Commercial Permit Work Data**, CKAN
  datastore SQL API — `data.milwaukee.gov`, resource id
  `828e9630-d7cb-42e4-960e-964eae916397`. Verified live 2026-07-26:
  `metadata_modified` = today, 8,257 total commercial records, max
  `Date Issued` 2026-06-15. `"Permit Type" LIKE 'Commercial%'` separates
  `Commercial New Construction Permit`/`Commercial Alteration Permit`
  from residential types. Address-stub only (no project-name field, same
  limitation as Hartford/Bentonville). CKAN is a different platform than
  ArcGIS/Socrata — no shared adapter in this repo, so this is a one-off
  script: `scripts/pull-wi-milwaukee.py`.

## What failed last time

- Madison — full ArcGIS Open Data Hub checked (144 datasets via DCAT); no
  building-permit dataset exists.
- Milwaukee's own ArcGIS REST server has an "Accela" folder, but its two
  layers (`AccelaApo`, `AccelaDistrict`) are address/parcel geocoding
  support layers for the internal Accela system, not permit records.
- WEDC "Awards Data" searchable database — real per its page copy, but
  the embedding iframe has an empty `src` in raw HTML; couldn't trace to
  a static endpoint.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-wi-milwaukee.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Wisconsin.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 5 projects |
| 2026-07-26 | Milwaukee CKAN commercial permits | +1,297 projects, 1,444 total |
