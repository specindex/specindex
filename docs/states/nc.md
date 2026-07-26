<!-- AUTO:HEADER START -->
**State:** NC (North Carolina)  
**Corpus file:** `data/states/nc.json`  
**Last corpus update:** 2026-07-26  
**Projects in corpus:** 5126  
**Counties:** 3 · **Cities:** 13  
**Date range:** Last 24 months commercial  
**Capture method:** Mecklenburg County (Charlotte) and Wake County (Raleigh) ArcGIS commercial permits, SAM.gov federal solicitations (bulk CSV extract), plus prior public research  
**Status mix:** permitting 4087, planning 997, bidding 38, under_construction 4
<!-- AUTO:HEADER END -->

# North Carolina Commercial Project Sources Playbook

**Canonical reference for all North Carolina pulls.** Read this file before adding or refreshing `data/states/nc.json`. Mirrors the structure and discipline of `docs/states/ga.md` — read that file first for the general methodology (verify liveness before building, test at 1 month before scaling to 24, prefer direct API over Playwright, etc.); this file only covers what's specific to North Carolina.

**Standing goal (2026-07-26): improving data coverage — more counties, deeper per-county detail — is the main, ongoing objective for specindex.ai.** Check `specindex.ai/coverage/` (backed by the `county_coverage` Cloud SQL table, roadmap item 26) to see which NC counties are still thin or uncovered (currently only 2: Mecklenburg, Wake), and proactively recommend/verify new sources for them, not just when asked. **Known trap:** `geo.forsythco.com` is Forsyth County GA, not NC — confirmed by real coordinates 2026-07-26 (roadmap item 27). Do not use it for NC's Forsyth County (Winston-Salem).

**Prepared:** 2026-07-25/26  
**Scope:** Commercial construction only. Residential/single-family/subdivision permits excluded at ingestion.  
**Window:** Last 24 months.

## Executive summary

NC went from 195 projects (SAM.gov bulk CSV only, plus one hand-researched entry) to **5,126** after adding Mecklenburg County and Wake County ArcGIS commercial permits. Two structural differences from Georgia shaped the approach:

1. **No DRI equivalent.** Confirmed via research: NC's closest analogues are SEPA (State Environmental Policy Act — only triggered by $10M+ *state-funded* projects, not general private commercial development) and CAMA (Coastal Area Management Act — coastal counties only). Neither matches Georgia DRI's broad, statewide, pre-permit filing role for private commercial development. This is a real gap in NC's data landscape, not a research failure — don't force a substitute.
2. **Accela is not the dominant permitting platform for NC's major metros**, unlike Georgia. A sweep of 17 candidate Accela slugs against the major cities found only 1 working (`CONCORD`, a smaller Charlotte-metro suburb) — Charlotte, Raleigh, Durham, Greensboro, Winston-Salem, and the rest all 404. NC's big counties run their own ArcGIS-based open-data portals instead, which turned out both more reliable and higher-yield.

## Sources wired

| Source | Script | 24mo raw yield | Access method |
|---|---|---:|---|
| Mecklenburg County (Charlotte) | `scripts/pull-nc-arcgis.py` (`pull_mecklenburg`) | 4,381 | ArcGIS FeatureServer, `permittype='Commercial'` + text exclusion (see bug below) |
| Wake County (Raleigh + county-wide) | same file, `pull_wake` | 2,475 | ArcGIS FeatureServer, `permitclassmapped='Non-Residential'` + text exclusion (see bug below) |
| SAM.gov bulk CSV | `scripts/pull-sam-gov-bulk-national.py` (or `--states NC`) | ~194 | Same national bulk CSV as Georgia — no key/quota |

Raw combined 6,856 → **5,126** after fuzzy dedup (`scripts/dedupe-state-corpus.py NC`, 1,925 merges). Unlike Georgia, NC's two ArcGIS sources are geographically disjoint (Mecklenburg and Wake don't overlap), so the large merge count is almost entirely *within-source* duplication — most likely permits that got touched/re-indexed across the 90-day test pull and the later 24-month full pull, or genuinely repeated permit rows for phased work at the same address, not cross-source duplicates.

### Endpoints (verified live before building, not just found via search)

**Mecklenburg County — Building Permits**
- FeatureServer: `https://meckgis.mecklenburgcountync.gov/server/rest/services/BuildingPermits/FeatureServer/0`
- Resolved via `arcgis.com/sharing/rest/search` (title "Building Permit Locations"), NOT the generic Hub search result which suggested the wrong host (`services.arcgis.com` under a guessed AGOL org — that guess was wrong)
- Verified live 2026-07-25: max `issuedate` = 2026-07-24, 482,293 total historical records
- Key fields: `permitnum`, `permittype`, `usdcdesc` (US Census Bureau permit classification — richer than `permittype` alone), `projname`, `projadd`, `issuedate`, `bldgcost`, `totalsqft`, `ownname`
- Commercial filter: `permittype = 'Commercial'`

**Wake County — Building Permits** (covers Raleigh + unincorporated Wake + other Wake municipalities in one feed)
- FeatureServer: `https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Building_Permits/FeatureServer/0`
- Same underlying AGOL org serves both `data-wake.opendata.arcgis.com` and `data-ral.opendata.arcgis.com` — resolved via the shared "Building Permits" item, not either county-branded portal directly
- Verified live 2026-07-25: max `issueddate` = 2026-07-24, 183,192 total historical records
- Exceptionally rich schema: `contractorcompanyname`, `contractorlicnum`, `estprojectcost`, `totalsqft`, `projectname`, `proposeduse`, `landusedescription`, `permitclass`/`permitclassmapped`, `parcelownername` — best contractor/owner data of any source built for this corpus so far
- Commercial filter: `permitclassmapped = 'Non-Residential'`

## Bugs found and fixed

1. **Mecklenburg's "Commercial" permittype includes temporary event permits.** Live sample under `permittype='Commercial'` alone: ~67% (20 of 30 in a one-month sample) were "SPT"-prefixed temporary event structures — concert stages, food trailers — coded identically to real small commercial permits under the same `usdcdesc` value `"437 - Commercial - No plan review (small CTAC projects)"`. There is no clean categorical field to separate them; the only reliable signal found was the literal `"SPT"` prefix and `"No Review Bldg Permit"` suffix in the permit description. Fixed with a `TEMP_EVENT_HINTS` regex exclusion in `pull_mecklenburg()`.
2. **Wake's `permitclassmapped='Non-Residential'` isn't fully reliable alone.** A live sample under that filter still included a permit whose `proposeduse` was literally `"DETACHED SINGLE FAMILY DWELLING"` (a condo project apparently routed through the non-residential review track). Fixed by layering the same `RESIDENTIAL_HINTS`/`COMMERCIAL_HINTS` text-based exclusion used throughout the Georgia scripts on top of the categorical filter.
3. **Wrong-jurisdiction FeatureServer trap, caught before building.** A generic-looking FeatureServer URL (`services6.arcgis.com/ONZht79c8QWuX759/.../Building_Permits/FeatureServer`) appeared in *both* Dallas TX and Austin TX web searches. Checked its actual field list before trusting either: it's an aggregate Year/Quarter/Geography statistics table (`Single_Units`, `Commercial_Value`, etc.), not per-project records, and unrelated to either city specifically. Never built anything against it.

## Accela sweep (all tested live, HTTP status + page-content verification)

Tested `aca-prod.accela.com/<SLUG>/Cap/CapHome.aspx?module=Building` for:

```
CHARLOTTENC, RALEIGH, DURHAM, GUILFORDCO, GREENSBORO, WINSTONSALEM, CARY,
FAYETTEVILLE, HIGHPOINT, CONCORD, GASTONIA, ASHEVILLE, WILMINGTON, APEXNC,
MOORESVILLE, CORNELIUS, HUNTERSVILLE
```

Only `CONCORD` returned HTTP 200 with a real, verified search form (confirmed via the presence of `ddlGSPermitType`/`generalSearchForm` markers in the page HTML, not just a 200 status — a generic error page could also return 200). Not yet built into a pull script; Concord is a smaller suburb, lower priority than the two counties already wired.

## What's still open

- **Concord** — confirmed working Accela portal, not yet built (lower priority — small suburb)
- **Durham, Guilford/Greensboro, Cumberland/Fayetteville** — mentioned as candidates in secondhand research, not yet researched or verified at all. Follow the same discipline: find candidate → verify liveness via `outStatistics` max-date → verify schema/commercial field → build → test 1 month → scale to 24
- **Georgia Procurement Registry equivalent for NC** — not researched. NC almost certainly has *some* statewide bid-posting system for public contracts even without a DRI-style pre-construction filing system; worth a research pass
- The performance fix in `scripts/project_identity.py::dedupe_projects()` (see `docs/ROADMAP.md` and the commit that introduced it) was discovered and fixed *because of* this NC pull — Georgia's smaller, already-curated corpus never hit the old algorithm's worst case. Keep this in mind if any future state's raw pull is large (thousands of records): dedup should now be fast, but if it isn't, that's a regression worth investigating immediately rather than waiting it out.

## Rebuild sequence

```bash
python3 scripts/pull-nc-arcgis.py --months 24 --merge
python3 scripts/dedupe-state-corpus.py NC
python3 scripts/merge-national-corpus.py
```

No dedicated multi-source rebuild script exists for NC the way `rebuild-ga-corpus.py` combines Georgia's tiered raw sources — with only two ArcGIS sources (which merge directly into `nc.json` by ID) plus the national SAM.gov bulk script, there isn't yet a strong case for that extra layer. Revisit if NC gains more sources (Concord, Durham, a state bid registry) that would benefit from the same raw-file-then-rebuild pattern Georgia uses.
