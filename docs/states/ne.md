# Nebraska Commercial Source Playbook

Read this file before refreshing `data/states/ne.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** NE (Nebraska)  
**Corpus file:** `data/states/ne.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 1  
**Counties:** 1 · **Cities:** 1  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — Meta/Google pipeline, state announcements.  
**Status mix:** under_construction 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Omaha Accela** (slug `OMAHA`) —
  `https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx?module=Permits&TabName=Permits`.
  Verified live 2026-07-26: HTTP 200, real search form (same markers as
  GA's Atlanta Accela). Case-type dropdown has a clean `COMMERCIAL`
  category with real construction types: `NEW CONSTRUCTION PROJECT`,
  `NEW BUILDING`, `NEW TENANT FINISH (First Tenant)`,
  `SHELL ONLY or SUPERSTRUCTURE`, `MULTI-FAMILY PROJECT`,
  `REMODEL EXISTING SPACE` (path pattern `Permits/BUILDING/COMMERCIAL/<TYPE>`).
  Best-verified Accela instance found across the NE/IA/CT/IN/WV research
  pass. **Not yet built** — reuse `scripts/pull-ga-accela-commercial.py`'s
  raw-HTTP-form-POST approach rather than starting from scratch.
- Lincoln building permit search (`app.lincoln.ne.gov/aspx/city/buildperm/default.aspx`)
  — confirmed live (HTTP 200, real ASP.NET postback form), but the
  commercial/residential-distinguishing field hasn't been inspected yet.
  Verify actual form fields before writing a scraper against it.

## What failed last time

- Omaha/Douglas County ArcGIS open data (`data-dogis.opendata.arcgis.com`)
  — full DCAT catalog checked: only building-footprint snapshot layers
  (2007-2022, no permit attributes) and a "Public Buildings" layer. No
  permit/project dataset.
- Nebraska DED (`opportunity.nebraska.gov`) — no structured/downloadable
  incentive-award or project-announcement database found; program
  description pages only, not a Tier-0 database like GA's DRI or IN's
  IEDC portal (even though IN's is currently down, see `docs/states/in.md`).

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

- Generic ArcGIS Hub search without verifying the layer covers Nebraska.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 1 projects |
