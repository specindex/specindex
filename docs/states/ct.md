# Connecticut Commercial Source Playbook

Read this file before refreshing `data/states/ct.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** CT (Connecticut)  
**Corpus file:** `data/states/ct.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 8  
**Counties:** 4 · **Cities:** 7  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Web research — New Haven Independent, Hartford Courant, CT Insider, CT.gov, Construction Review Online  
**Status mix:** under_construction 5, planning 3
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- Update after each pull with endpoints, scripts, and filters that produced clean records.

## What failed last time

- Update after each pull with dead links, wrong layers, residential noise, and dedupe traps.

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

- Generic ArcGIS Hub search without verifying the layer covers Connecticut.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 8 projects |
