# Arkansas Spec Pull — Summary (run 2026-08-06)

## Sources attempted (both Tier 1, both live — link_verified_aug2026 holds)

| Source | Type | Status | Projects |
|---|---|---|---|
| DBA Bid Announcements (sas.arkansas.gov) | Vertical | Live, free, no login | 1 active |
| ARDOT Currently Advertised Projects (ardot.gov) | DOT | Live, free, no login | 7 active (Aug 12 + Nov 4, 2026 lettings) |

sources.csv estimated ~25 Vertical and ~300 DOT projects/year since Jan 2025; the point-in-time active counts (1 and 7) are consistent with those annual rates given ARDOT's letting cycle.

## Funnel

- Projects found: **8** (1 Vertical + 7 DOT)
- Projects with any documents: **8 / 8 (100%)**
- Projects with confirmed spec docs (content-verified): **7 / 8 (87.5%)** — all 7 ARDOT proposals verified by reading content (ARDOT Standard Specs Ed. 2014 SS/SP structure, FHWA-1273). The 1 Vertical project has only an ad (.doc, binary) and a scanned bid tab; no spec book posted.
- Recovered by Stage 4 search: **0 / 1** attempted (3 candidate URLs found, all 404).

Storage note: this environment cannot store binary PDFs fetched over the web, so per the skill's fallback no `specs/` folder was produced; each confirmed document is represented by TOC/section evidence in `evidence.md` plus its direct URL in `pull_log.csv`, and the log status says so.

## Dead links

Portal URLs from sources.csv: **none dead** — both resolved and matched their descriptions.

Document-level dead links found during gap-fill (stale search-index entries for the pre-rebid project 9002418):

- https://ardot.gov/wp-content/uploads/Addendum-02-9002418.pdf — 404; no replacement found. Current addenda, if any, would come via the design professional.
- https://www.olympusgc.com/wp-content/uploads/2024/11/add_1_spec_plan.pdf — 404 (contractor mirror, removed).
- https://www.olympusgc.com/wp-content/uploads/2024/11/add_2_specs.pdf — 404 (contractor mirror, removed).

## Registrations / follow-ups that would unlock more

- **None required for Arkansas** — both sources are genuinely Tier 1. Every ARDOT letting document (notice, proposal, plans, Q&A, EBS) is a direct free PDF/zip on media.ark.org.
- The one gap is Vertical spec books: DBA posts only the ad and bid tab; the spec book for 9002418R is distributed by the project design professional (named in the ad .doc, which needs a real download/parse, not a fetch-to-text tool). A human step — opening the .doc or calling the design professional — is the only way to that document.
- The 9002418R bid due date (07/28/2026) has passed and an unofficial bid tab is posted, so this project is post-bid; the next DBA solicitation cycle is the better collection target.

## Notes for the source table

- ARDOT document URLs follow a stable pattern: `https://media.ark.org/ardot/{JOB}_notice.pdf`, `{JOB}_proposal.pdf` (sometimes `{JOB}_1-proposal.pdf` after re-issue), `{JOB}_plans.pdf`, `{JOB}_qa.pdf`, `{JOB}_ebs.zip`. Worth recording in sources.csv notes — it enables direct enumeration without scraping the listing page.
- ARDOT "(S)" suffix on project names and the biweekly-to-monthly letting cadence match the execution plan's guidance to record the letting date with every document.
