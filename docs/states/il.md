# Illinois Commercial Source Playbook

Read this file before refreshing `data/states/il.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** IL (Illinois)  
**Corpus file:** `data/states/il.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 3  
**Counties:** 3 · **Cities:** 3  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — REBusinessOnline, DC BLOX filings.  
**Status mix:** under_construction 1, planning 1, permitting 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Cook County Assessor's Permits** (Socrata) — `datacatalog.cookcountyil.gov`,
  resource `6yjf-dfxs`. Verified live 2026-07-27: 711,162 total records
  across **124 municipalities** (all of Cook County, including Chicago —
  `municipality='CITY OF CHICAGO'` rows already cover it, so this one
  source avoids a Chicago-city-portal/Cook-County-portal overlap-dedup
  problem entirely). Real categorical field: `job_code_primary='COMMERCIAL PERMIT'`
  — no text-keyword guessing needed. 25,203 commercial records in a
  24-month window (unfiltered upper bound). **Real data-quality trap**:
  `property_address` is populated on almost none of the rows (88 of
  25,203) — most records only carry `municipality`/`township`, not a
  street address; still fixes the city-field gap (city-level, not
  address-level). `amount`/`work_description`/`applicant_name` ARE
  populated on ~99.7% of rows. Also: 18 records across the full dataset
  have garbage far-future `date_issued` values (up to year 2210) — clamp
  the upper date bound, don't trust an unfiltered max(). Built into
  `scripts/pull-il-cook-county.py`.
- City of Chicago's own permit portal (`data.cityofchicago.org`, resource
  `ydr8-5enu`, 842,269 records) was researched and verified live too, but
  deliberately NOT used — same data already exists in the Cook County
  Assessor feed above, and using both would require a real address/date/
  amount-proximity dedup pass (different ID schemes) rather than a clean
  ID match. Worth revisiting if a project-name/description field ends up
  mattering more than the Cook County source provides.

## What failed last time

- Illinois DCEO — checked `dceo.illinois.gov` and Socrata catalog search
  against `data.illinois.gov`; zero structured incentive/project
  datasets. Press releases and static program pages only, no Tier-0
  equivalent to Georgia's DRI.
- Illinois EPA large-facility permitting — the URL surfaced by search
  404'd; the real page links to an "AFIIS" lookup tool not tested for an
  API in this pass (not confirmed dead, just not verified usable).
- Illinois Commerce Commission large-load/data-center filings — live
  page, but a date-picker search form with no visible API; would need
  Playwright network-interception (same as this repo's Gwinnett
  precedent) to find a hidden endpoint, if one exists.

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-il-cook-county.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Illinois.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 3 projects |
| 2026-07-27 | Cook County Assessor's Permits (`job_code_primary='COMMERCIAL PERMIT'`) | +22,191 projects, 22,461 total |
