# Ohio Commercial Source Playbook

Read this file before refreshing `data/states/oh.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** OH (Ohio)  
**Corpus file:** `data/states/oh.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 2  
**Counties:** 2 · **Cities:** 2  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — REBusinessOnline, Columbus Business First, local news.  
**Status mix:** under_construction 2
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Columbus Building Permits** (ArcGIS FeatureServer, 675,280 total,
  fresh to yesterday) — `B1_PER_TYPE='Commercial'` is clean, but most
  commercial rows are $0-value trade sub-permits (Plumbing/Electrical/
  Mechanical) — filtered with a `G3_VALUE_TTL > $25,000` floor. Built
  into `scripts/pull-county-arcgis.py` (`pull_columbus`, `--only columbus`).
- **Cleveland Issued Building Permits** (ArcGIS FeatureServer, 198,276
  total, fresh to yesterday) — `PERMIT_CATEGORY='Commercial...'` is a
  trap (~1,675 records only); real filter is `USE_GROUP_1` (IBC classes
  with descriptive suffixes: "B Business", "M Mercantile...", "A-2
  Assembly...", vs "One Family"/"R-2 Residential..."). Direct `LAT`/`LON`.
  **Two real bugs found and fixed while building this one**: (1) the
  address field is `PRIMARY_ADDRESS`, not `SITE_ADDRESS` (mixed up with
  Columbus's field name — a 400 error, not silently wrong data, so it was
  caught immediately); (2) this ArcGIS server rejects `+`-encoded spaces
  inside a quoted `LIKE` string literal — `urllib.parse.urlencode()`'s
  default space-as-`+` encoding 400'd, fixed by switching the *shared*
  `query_layer()` helper in `pull-county-arcgis.py` to
  `quote_via=urllib.parse.quote` (`%20`), which is safe for every other
  puller too since `%20` is universally valid. Built into
  `scripts/pull-county-arcgis.py` (`pull_cleveland`, `--only cleveland`).
- **Cincinnati Building Permits** (Socrata/Tyler Data & Insights, 178,428
  total, fresh to 3 days) — `permitclass='OBC'` (Ohio Building Code) vs
  `'RCO'` (Residential Code) is the real split. Covers the City of
  Cincinnati only, not Hamilton County's townships (`jurisdiction` is
  100% "CINCINNATI" despite CAGIS branding suggesting county-wide).
  `proposeduse` values come back with literal embedded quote characters
  (`'"B"'`) — stripped when used. Built into `scripts/pull-oh-cincinnati.py`.
- Ohio Tax Credit Authority (JCTC) meeting-minutes PDFs — Ohio's real
  Tier-0 equivalent to GA's DRI (real company/city/county/investment/jobs
  per project, ~monthly), but only individually-dated PDFs, no master
  index found. Not yet built.

## What failed last time

- Cuyahoga County "DeltaTrack" and "Catalyst Sites" ArcGIS layers — real
  and live but parcel-level tax-assessment/marketed-site inventories, not
  project records.
- Franklin County Auditor "Building Footprints" — geometry-only, no
  permit attributes.
- No county-level (unincorporated) permitting feed found for Franklin,
  Cuyahoga, or Hamilton counties — only the three anchor-city feeds above
  resolved to real project-level services.
- Ohio Power Siting Board (OPSB) and Ohio EPA — both real (data-center
  megaproject dockets confirmed via news coverage) but sit behind a WAF
  that blocks direct `curl`/WebFetch requests; would need a real browser
  session to verify a structured docket list exists.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-county-arcgis.py --only columbus,cleveland --months 24 --merge
python3 scripts/pull-oh-cincinnati.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Ohio.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 2 projects |
| 2026-07-27 | Columbus (value floor) + Cleveland (`USE_GROUP_1`) + Cincinnati (`permitclass='OBC'`) | +12,884 projects, 13,257 total |
