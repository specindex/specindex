# Washington Commercial Source Playbook

Read this file before refreshing `data/states/wa.json`. Keep it current so the next pull starts from what already worked.

<!-- AUTO:HEADER START -->
**State:** WA (Washington)  
**Corpus file:** `data/states/wa.json`  
**Last corpus update:** 2026-07-24  
**Projects in corpus:** 3  
**Counties:** 3 · **Cities:** 3  
**Date range:** 2026-04-26 to 2026-07-24 (last 90 days)  
**Capture method:** Public sources — Industrial Briefs, Covington Reporter, Wenatchee World, municipal planning filings.  
**Status mix:** permitting 2, under_construction 1
<!-- AUTO:HEADER END -->
## Source order (fill in as you learn)

1. State economic development announcements and press releases
2. Municipal permit open data (verify the endpoint serves this state before bulk pull)
3. Trade press and owner or developer announcements

## What works

- **Seattle Building Permits** (Socrata) — `data.seattle.gov`, resource
  `76t5-zqzr`. Verified live 2026-07-27: 191,801 total, max `issueddate`
  2 days old. `permitclassmapped='Non-Residential'` (51,673 records)
  cleanly separates commercial; combined with a `permittypedesc` filter
  to drop non-construction noise (Shoreline/ECA Exemption records).
  Direct `latitude`/`longitude` fields, no geocoding needed. Built into
  `scripts/pull-wa-seattle.py`.
- **Tacoma Accela permit data mirror** (ArcGIS FeatureServer, 109,988
  total, fresh to 3 days) — `permit_type='Building' AND
  permit_subtype='Commercial'` (17,016 records) is a clean binary field.
  Not yet built.
- **Pierce County PALS Permits** (ArcGIS FeatureServer, 680,409 total,
  fresh to 5 days) — `applicationType='Construction Commercial'` (22,242
  records). **Does not cover the City of Tacoma proper** (confirmed via
  address sampling — all recent commercial hits are unincorporated
  pockets: Puyallup, Eatonville, Frederickson) — use alongside Tacoma's
  own source above, not instead of it. Not yet built.
- **Bellevue Permit Data** (ArcGIS FeatureServer, 32,112 total, fresh to
  2 days) — no clean categorical field; needs a positive-signal
  `PERMITTYPEDESCRIPTION` match (`LIKE '%Commercial Project%'` OR
  `LIKE '%Tenant Improvement%'` OR `='ROW Commercial Development'`), same
  lesson as VT's Act 250 — the layer is dominated by trade permits with
  no residential/commercial marker at all. Not yet built.

## What failed last time

- King County (unincorporated) — full DCAT catalog (536 datasets)
  checked, no permit-level dataset exists. King County runs Accela
  (`aca-prod.accela.com/kingco`, confirmed live) — Tier 2 candidate for a
  future Playwright build, not yet attempted.
- Two wrong-jurisdiction ArcGIS org IDs resurfaced here too:
  `ONZht79c8QWuX759` (Peel Region, Ontario, Canada — already flagged for
  NC/TX searches) and `v400IkDOw1ad7Yad` (City of Raleigh, NC — same org
  legitimately used for NC's real Wake County source, but a false hit
  when searching for WA). Both appear generic enough to false-hit
  regardless of the city actually searched.
- Spokane "Permit" FeatureServer — real schema, real commercial field,
  but confirmed stale (no records in the last 60 days as of query time).

## Commercial-only filters

- Drop residential, single-family, townhome, and subdivision filings unless clearly commercial multifamily.
- Every record needs a `sources` URL. Null values use "Not reported", never a dash.
- Never merge on shared ArcGIS layer catalog URLs. Only record-specific source URLs count.

## Pull commands

```bash
python3 scripts/pull-wa-seattle.py --months 24 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

## Do not use

- Generic ArcGIS Hub search without verifying the layer covers Washington.
- Zip-code aggregate datasets with no project-level records.

## Pull log

| Date | Source tried | Outcome |
|------|--------------|---------|
| 2026-07-24 | Stub synced from corpus | 3 projects |
| 2026-07-27 | Seattle Building Permits (`permitclassmapped='Non-Residential'`) | +2,514 projects, 2,953 total |
