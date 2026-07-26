<!-- AUTO:HEADER START -->
**State:** GA (Georgia)  
**Corpus file:** `data/states/ga.json`  
**Last corpus update:** 2026-07-25  
**Projects in corpus:** 1377  
**Counties:** 69 · **Cities:** 128  
**Date range:** Last 24 months commercial  
**Capture method:** Georgia DRI filings, Alpharetta/Fulton County/Savannah/Johns Creek/Marietta commercial permits, Accela commercial permits (Atlanta/Gwinnett/Cobb, when available), USAspending.gov federal construction awards, plus prior public research  
**Status mix:** permitting 519, planning 451, completed 287, under_construction 120
<!-- AUTO:HEADER END -->

# Georgia Commercial Project Sources Playbook

**Canonical reference for all Georgia pulls.** Read this file before adding or refreshing `data/states/ga.json`.

**Prepared:** July 24, 2026  
**Scope:** Commercial construction only. Residential housing, townhome subdivisions, and low-signal permit noise excluded.  
**Window:** Last 12 months where a date field exists; undated mapped developments kept when type is clearly commercial or industrial.

## How to use this document

On every Georgia capture or refresh:

1. Read this playbook first. Do not invent new source order or skip tiers.
2. Run sources in tier order: **DRI → ArcGIS open data → prior research merge → Accela (when wired)**.
3. Apply commercial-only filters at ingestion, not after merge.
4. Write raw output to `data/raw/`, merge into `data/states/ga.json`, then `merge-national-corpus.py`.
5. Update the "Georgia results" counts in this file if the corpus size changes materially.

**Standard pull sequence:**
```bash
python3 scripts/pull-ga-dri.py --months 12
python3 scripts/pull-ga-municipal-commercial.py --months 12 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

Also saved to Google Drive: `My Drive/GEORGIA-COMMERCIAL-SOURCE-PLAYBOOK.md`

This document captures what worked in Georgia, what did not, and how the major incumbents (Dodge, Shovels, PermitStack) pull the same class of data. Use it as a template for other states.

---

## Executive summary

Georgia went from **54 projects across 21 counties** to **489 commercial projects across 58 counties and 93 cities** after DRI, municipal ArcGIS, and research merge (July 2026). The gain did not come from one magic national API. It came from stacking sources in the right order:

1. **Statewide pre-construction filings** (Georgia DRI) for large commercial work before permits exist.
2. **City ArcGIS open-data layers** where they publish commercial permits or development polygons.
3. **Prior press and announcement research** for marquee projects the permit feeds miss or mislabel.
4. **Accela Citizen Access portals** (Atlanta, Gwinnett, Cobb) as the next unlock, not yet bulk-ingested here.

Residential was excluded at ingestion time, not filtered out later. That matters because most municipal feeds are dominated by interior remodel permits and single-family work.

---

## Georgia results after the scrub

| Metric | Before | After |
|---|---:|---:|
| Total commercial projects | 54 | 489 |
| Counties covered | 21 | 58 |
| Cities covered | ~21 | 93 |
| National corpus GA share | 54 / 270 | 469 / 685 |

### Where the new records came from

| Source tier | Projects | What it is |
|---|---:|---|
| Prior public research | 54 | Groundbreakings, trade press, owner announcements |
| Georgia DCA DRI (12 mo, commercial types) | 108 | Statewide Developments of Regional Impact |
| Alpharetta commercial permits (ArcGIS) | 274 | Cityworks/EnerGov-style commercial permit cases |
| Johns Creek active developments (ArcGIS) | 7 | Active non-residential development polygons |
| Marietta developments layer (ArcGIS) | 26 | Industrial / commercial / mixed-use parcels |

Scripts: `scripts/pull-ga-dri.py`, `scripts/pull-ga-municipal-commercial.py`

### County coverage (top 15)

| County | Projects | Notes |
|---|---:|---|
| Fulton | 307 | Dominated by Alpharetta commercial permits (274). Atlanta proper still thin. |
| Cobb | 27 | Marietta mapped developments + 1 prior research record |
| Chatham | 13 | Savannah / Pooler corridor; DRI + prior research |
| Bryan | 9 | Hyundai corridor logistics |
| Bibb | 8 | Macon arena, Costco, Prince Service |
| Coweta | 7 | Bridgeport, Trinity Station |
| Columbia | 7 | Wellstar, White Oak tech park |
| Effingham | 5 | OpenAI Project Camellia, logistics |
| Barrow | 5 | Data center and industrial DRI filings |
| DeKalb | 4 | Campus 244; Accela portal not yet bulk-pulled |
| Henry | 4 | Hampton Technology Park, Watermark |

### Zip-level signal (where address data exists)

Most Georgia sources do not publish zip codes in a consistent field. Where location text exists, Alpharetta permits cluster in North Fulton zips:

| Zip | Projects (from location text) |
|---|---:|
| 30009 (Alpharetta) | 194 |
| 30022 (Johns Creek / Alpharetta edge) | 150 |
| 30005 (Alpharetta) | 86 |
| 30076 (Roswell / Johns Creek edge) | 36 |

**Takeaway:** "Zip by zip" only works when the upstream feed carries structured addresses. For Georgia, the actionable unit today is **city ArcGIS layer first, county DRI second, Accela portal third**.

---

## 2026-07-25 update: window expanded to 24 months, new sources, Accela outage

Corpus went from 489 → **1,377** projects. Window expanded from 12 to 24 months on all date-filterable sources. Approach: validate every new/changed source at a 1-month window first, confirm real signal, only then scale to 24 months — caught several problems this way that a blind 24-month run would have hidden.

### New sources added

| Source | Script | 24mo yield | Notes |
|---|---:|---:|---|
| Fulton County "Building Permits Issued" (ArcGIS) | `pull-ga-municipal-commercial.py` (`pull_fulton`) | 299 | `JobTypeDescription='Commercial'`. Includes square footage (rare field). Has a real **~1-month ingestion lag** — a `--months 1` pull alone returns 0; use `--months 2+`. Covers unincorporated Fulton + cities without their own system; may overlap with Alpharetta (dedup isn't guaranteed to catch a full-county feed against a city-specific one). |
| Savannah/Chatham SAGIS "Site Permit by Work Class" (ArcGIS) | `pull-ga-municipal-commercial.py` (`pull_savannah`) | 103 | `WorkClass='Full Site-Private'`, text-filtered. No project-name field — synthesized from address. Live as of 2026-07-17. |
| USAspending.gov federal construction awards | `pull-usaspending-ga.py` | 414 (422 raw, 8 filtered as noise) | **No API key or quota** (unlike SAM.gov's ~10 calls/day limit). PSC filter `{"require": [["Product","Y"]]}`, contract award types A-D. Real top hits: $491M CDC high-containment lab, $221M CDC Chamblee campus, $195M Navy Trident Refit expansion. 75% of 2-year awards already show `completed` status (period of performance ended) — `open_for` text is conditioned on status so completed awards aren't misrepresented as active spec opportunities. |
| DRI (24mo) | `pull-ga-dri.py` | 252 | Scaled linearly from the 12mo baseline (108 → 252, ~2.3x). |

### Sources checked and rejected

| Source | Why rejected |
|---|---|
| Columbus/Muscogee "BuildingPermits" ArcGIS (`ccggisprod.columbusga.org`) | Best-structured schema found all session (owner, contractor, valuation, sqft, dedicated Commercial layer) but **stale — most recent record 2022-04-15**. Confirmed via `outStatistics` max-date query before building anything on it. |
| Atlanta city Hub "All Building Permits 2019-2024" (`dpcd-coaplangis.opendata.arcgis.com`) | Resolves through the DCAT catalog to a static **CSV upload, last touched 2024-08-08** — not a live feed, same dead-end pattern as Columbus. |
| Cobb County ArcGIS permits layer | Checked Cobb's open-data DCAT catalog directly for a "permit"/"building" dataset — **none exists**. Cobb's real permit system is Accela. A secondhand research summary claimed otherwise; didn't hold up under direct verification. |
| Gwinnett County ArcGIS permits layer | Same check on Gwinnett's catalog — only near-match is a generic "Buildings" footprint layer, not permits. Gwinnett's real permit system is Accela. |
| GDOT Vendor Portal (`vendorportal.dot.ga.gov`) | Login-gated, no public data on the entry page. |

### Gwinnett Accela: root-caused and partially fixed

Gwinnett was returning only ~10 records/month regardless of window (vs. Atlanta's 235/month) — two separate real bugs, not one:

1. **Type-discovery bug (fixed):** the commercial-type filter matched against the dropdown's display *label* only. Gwinnett encodes the category in the option *value* instead (`value="Building/Commercial/NA/NA"` shown to users as just `"Building"`), so the single biggest commercial permit type was silently skipped entirely. Fixed in `pull-ga-accela-commercial.py::commercial_permit_types()` by matching against `value + label` together. Also broadened `COMMERCIAL_TYPE`/`PRIMARY_TYPES` keywords (added hospital/school/church/institutional) for parity with the municipal script — side effect: this also surfaced high-volume trade-permit types for Atlanta/Cobb (Electrical, Fire Alarm, etc.) that weren't there before; see `scripts/tag-trade-permits.py`.
2. **No date-filter fields at all (root cause of the original bug):** confirmed live in a real browser that Gwinnett's Building-module search form has **no start/end date inputs** — Atlanta and Cobb have them, Gwinnett doesn't. The original raw-POST scraper was posting `txtGSStartDate`/`txtGSEndDate` values that don't correspond to any real control on Gwinnett's page; the server silently ignored them and always returned the same top-10-by-record-number result. Fixed with a **Playwright-based path** (`pull_gwinnett_playwright()`) that paginates the real numbered pager instead (results are sorted newest-first with no filter, so it walks forward and stops once dates cross the cutoff — filtering client-side, not server-side).
3. **Residual limitation:** high-volume types (e.g. "Building") still hit Accela's ~100-record display ceiling per unbounded query, since the Playwright path doesn't yet subdivide into date sub-windows the way the original Atlanta/Cobb scraper does. Accepted as good-enough for now (10 → 318 records/month on the last successful run) rather than invest further.
4. Real flakiness also found and mitigated: the search postback intermittently lands back on a reset `--Select--` form instead of executing (confirmed by direct reproduction). Added a verify-and-retry wrapper (checks for the "Showing X-Y of Z" text before trusting a search "succeeded").

### Accela/GPR network outage — data loss, unresolved

Late in the session, **both** `aca-prod.accela.com` (Accela) and `ssl.doas.state.ga.us` (Georgia Procurement Registry) started failing with `Operation timed out` simultaneously — very likely self-inflicted rate-limiting/blocking after a high volume of automated requests (Accela pulls + GPR UI debugging + Playwright network-interception attempts, all in a short window). Consequence: the 24-month Atlanta and Cobb Accela pulls both failed *and*, because all three agencies write to the same `data/raw/ga-accela-commercial.json` with no `--out` override, the failed runs' empty results **overwrote the file and lost the previously-good 318-record Gwinnett test data**. `accela_raw` is 0 in the current corpus as a result.

**Follow-up, not done today:** retry Atlanta/Cobb/Gwinnett Accela pulls once enough backoff time has passed. Consider adding per-agency `--out` paths to `pull-ga-accela-commercial.py` so concurrent/sequential runs can't clobber each other again.

### Georgia Procurement Registry (GPR) — promising, not yet automated

`ssl.doas.state.ga.us/PRSapp/PR_index.jsp` redirects to a real, modern app (`ssl.doas.state.ga.us/gpr/`) with genuine structured bid data — confirmed via a live event detail page (agency, category, NIGP codes, full description, buyer contact, and a **Documents tab** likely holding real bid/spec attachments, directly relevant to the spec-book extraction pipeline). Georgia law requires USG/state capital projects over $100k to post here. Search/filter dropdowns (`govEntity`, `catType`) load inconsistently across page loads — not yet reliably automatable, and now blocked by the outage above besides. Worth a dedicated session with network-request interception (to find the real backend JSON endpoint behind the UI) rather than more blind `select_option` attempts.

### University sources — mostly dead ends for bulk data, one real manual-research lead

USG Board of Regents facilities hub, UGA procurement, and Georgia Tech procurement pages are all **static guidance/landing pages** — no project lists, no bid boards. This is expected: GPR is the actual state-mandated central hub for USG capital-project bids, not individual campus procurement pages. One real find: Georgia Tech's "Current Major Projects" page lists **8 named, current capital projects** (Tech Square Phase 3, Fanning Student-Athlete Performance Center, Curran Street Residence Hall, etc.) — hand-curated, not a bulk API, same tier as the corpus's existing "prior research" entries. Not yet added to the corpus. UGA's equivalent page not yet checked.

### Scripts added/changed today

| File | Change |
|---|---|
| `scripts/pull-ga-municipal-commercial.py` | Added `pull_savannah()`, `pull_fulton()` |
| `scripts/pull-ga-accela-commercial.py` | Fixed value-vs-label type matching; added `pull_gwinnett_playwright()`; broadened commercial keywords |
| `scripts/pull-usaspending-ga.py` | New |
| `scripts/tag-trade-permits.py` | New — tags Accela records as `trade` vs `project` post-pull (not yet applied to real data since Accela output was lost) |
| `scripts/rebuild-ga-corpus.py` | Added `usaspending-ga-construction.json` as a merge source; updated date range to 24mo |

---

## Source tier playbook (reuse in other states)

Work in this order. Do not start with Reddit, LLMs, or generic web search. Start with what governments already publish.

### Tier 0: Statewide structured pre-construction (highest ROI per record)

**Georgia:** `https://apps.dca.ga.gov/DRI/Submissions.aspx`

Georgia's Planning Act requires a Development of Regional Impact review for large projects. This is the only statewide, structured, pre-construction feed. Filings happen before building permits. Fields include project name, development type, county, city, filing date, and status.

**Commercial filter applied:**
- Drop `Housing` development type entirely.
- Drop `Withdrawn` and `Terminated` reviews.
- Last 12 months: 142 filed → **108 commercial kept** after filters.

**Other states to check:**
- State economic development agency project announcements.
- Environmental impact / air quality permits for data centers and industrial.
- Public utility commission filings for large power loads.
- State DOT P3 and major infrastructure registers.

### Tier 1: Municipal open data (ArcGIS / Socrata / CKAN)

These are the best automated feeds when they exist. Query the REST endpoint directly; no browser needed.

| Jurisdiction | Platform | Endpoint | Commercial signal | 12-mo yield |
|---|---|---|---|---:|
| Alpharetta | ArcGIS MapServer | `OpenData/OpenData_PCE_Full/MapServer/1` | `Commercial *` case types | 318 raw → 274 kept |
| Johns Creek | ArcGIS FeatureServer | `ActiveDevelopmentProjects/FeatureServer/0` | Non-residential dev polygons | 7 |
| Marietta | ArcGIS MapServer | `HubContent/AGOL_OpenData/MapServer/8` | TYPE in Industrial, Commercial, Mixed Use | 26 |
| Fulton County | Socrata aggregate | `performance.fultoncountyga.gov/.../p3f6-ug7s` | Zip/quarter counts only | **Not usable** (no project records) |

**Commercial-only filters that matter:**
- Drop `Residential`, `Townhomes`, `Subdivision` type labels.
- Drop noise permits: seasonal sales, cell tower co-locate, construction trailers, temp signs.
- For Alpharetta, keep `Commercial New Construction`, `Commercial Addition`, tenant finish above a relevance threshold; drop pure interior remodel unless you sell finishes.

**ArcGIS query pattern:**
```
GET .../MapServer/{layer}/query?where=DATE_ENTERED >= DATE '2025-07-24'&outFields=*&f=json&resultRecordCount=1000
```
Paginate with `resultOffset` when `exceededTransferLimit` is true.

### Tier 2: Accela Citizen Access (major metros, browser or API)

Most Georgia metros run Accela. These portals hold the bulk of commercial permit volume but do not expose a clean public bulk API without automation.

| Metro | Portal | Commercial module |
|---|---|---|
| Atlanta | `aca-prod.accela.com/ATLANTA_GA` | Building, Planning |
| Gwinnett | `aca-prod.accela.com/GWINNETT` | Commercial Permits module |
| Cobb | `cobbca.cobbcounty.gov/CitizenAccess` | Commercial, Commercial Industrial, Infrastructure |
| DeKalb | Planning portal + in-person commercial submittals | New commercial guide on county site |

**How Shovels and PermitStack pull Accela:** headless browser or Citizen Access export endpoints, then normalize to a canonical schema. Expect Playwright, rate limits, and per-jurisdiction field maps. Apify actors (`paxiq/us-building-permit-scraper`) claim 163 Accela cities at ~32% US population coverage.

**Next step for Georgia:** wire Accela pulls for Atlanta + Gwinnett + Cobb with commercial record type filters only.

### Tier 3: Press, owner announcements, trade publications

Still necessary for projects that are public but not yet in a permit system, or where the permit record is an address stub ("Chicago Permit #101082051, 707 W JUNIOR TER" problem).

Sources that worked in the prior Georgia corpus:
- REBusinessOnline, citybiz, PR Newswire groundbreakings.
- Owner/developer press releases (Hyundai Metaplant, OpenAI Project Camellia).
- County economic development pages.

**LLM role here:** search and extract from HTML/PDF announcements, not invent project counts. Every extracted fact must link to a source URL.

### Tier 4: What did not work (Georgia)

| Source | Why it failed |
|---|---|
| Fulton County Socrata `p3f6-ug7s` | Aggregated permit counts by zip/quarter, not project records |
| ArcGIS Hub generic search | Returns national noise, not GA-specific layers |
| Savannah / Athens open data hosts | DNS / SSL failures at time of probe |
| Forsyth EnerGov ArcGIS | Token required (authenticated) |
| Reddit search API | 403 blocked without OAuth |
| Generic "scrape all GA counties" | No standard schema; 159 counties × different vendors |

---

## How Dodge pulls this information

Dodge Construction Network (formerly FW Dodge, McGraw-Hill Construction, Dodge Data & Analytics) is the incumbent BPMs already pay. Understanding their model explains why SpecIndex can win on timing and transparency without trying to replicate 130 years of field operations on day one.

### Origin: humans on bicycles, now humans plus machines

Dodge started in the 1890s with Frederick W. Dodge riding around Boston cataloging projects on index cards. That DNA still shows up in the product: **aggregation alone is not the moat; verification is.**

Today Dodge describes a hybrid pipeline:

| Stage | What Dodge does |
|---|---|
| **Ingest** | Monitor **19,000+ web sources**, **3,000 municipalities**, and **25,000 news publications** continuously |
| **Verify** | **400–500 field reporters and specialists** confirm stage, contacts, value, and specs on the ground |
| **Document** | Digitize **160,000 project documents per year** (plans, specs, bid docs) into Dodge Plan Room |
| **Publish** | **~7,000+ Dodge Reports per day** (~636,000–700,000 projects tracked annually) |
| **Enrich** | Firm graph via Blue Book Network (**677,000+ firms**), specification intelligence, brand mention alerts |
| **Deliver** | Dodge One platform, REST API (OAuth 2.0, JSON), CRM feeds to Salesforce / Dynamics / HubSpot |

Sources: [construction.com/about](https://www.construction.com/about/), [construction.com/dodge-one](https://www.construction.com/dodge-one/), [construction.com/apis](https://www.construction.com/apis/)

### Dodge's secret is not scraping. It is early lifecycle plus documents plus people.

Three things separate Dodge from permit aggregators like Shovels or PermitStack:

1. **Pre-planning visibility.** Dodge tracks projects from the first planning permit and design phase, often months before a building permit exists. Their IMS product (Integrated Marketing Systems) delivers advance notices of public pre-design projects across thousands of agencies before official publication.

2. **Specification and plan room access.** Dodge Plan Room hosts plans, specs, and bid documents. For BPM sales teams, this is the actual monetizable layer: basis-of-design and approved-manufacturer intelligence. SpecIndex's reporting page is honest that this layer is not built yet.

3. **Human verification at scale.** Every Dodge Report is researched and quality-checked before it hits a subscriber dashboard. Shovels leans on LLM normalization; Dodge leans on reporters plus analysts. Dodge is also the U.S. Census Bureau's preferred construction data provider for 55+ years.

### Dodge acquisitions that matter for a competitor map

| Asset | What it adds |
|---|---|
| **The Blue Book** (1913) | Subcontractor and vendor registry; relationship graph |
| **Sweet's** (1906) | Manufacturer catalog and spec workflow for architects |
| **IMS** (1991) | Advance public agency notices pre-RFP |
| **Principia** (1995) | Building materials market research and consulting |

### Dodge API (what a custom model would compete with)

Dodge now sells REST API access with:
- **Projects:** stage, valuation, trades, spec divisions, lifecycle
- **Companies / contacts:** decision-makers on active work
- **Project documents:** plans and specs for automated product mention extraction

Their API marketing explicitly positions **document intelligence at scale** and **AI agents** as use cases. Dodge is not ignoring LLMs. They are applying them on top of a verified document corpus they spent decades assembling.

### What SpecIndex should copy vs not copy

| Copy | Do not copy yet |
|---|---|
| Stable project ID with lifecycle history | 500 field reporters |
| Source link on every fact | Claiming spec share without reading spec books |
| Stage-aware lead scoring (still open, nobody named) | Census-bureau-grade forecasting |
| CSI division segmentation | 10M historical projects |
| Honest zeros on bid winners / installed products | Plan room document hosting at Dodge scale |

**Positioning against Dodge:** SpecIndex is top-of-funnel and transparent. Dodge is full-lifecycle, verified, and expensive. SpecIndex wins when a BPM rep needs a **clean list of early commercial jobs in their territory with citations**, not when they need a spec book parsed by a human analyst.

---

## How Shovels.ai pulls this information

Shovels is the closest pure-data competitor to what you are building programmatically.

| Layer | Shovels approach |
|---|---|
| **Collection** | Direct from jurisdictions: open data portals, building department APIs, website scraping, FOIA when needed. They state they do not buy from third-party vendors (marketing claim). |
| **Coverage reality** | 20,000+ US permit jurisdictions exist; no one has them all. Shovels combines sources and accepts linear maintenance cost. |
| **Processing** | **LLM-based pipeline** to normalize, classify, and derive metrics (job value modeling, inspection pass rate, construction duration). |
| **Enrichment** | Census National Address Dataset, state contractor license files, tax assessor property records |
| **Delivery** | REST API, CLI, Charlie AI natural-language query interface |
| **Refresh** | Continuous ingestion; competitor PermitStack claims Shovels refreshes ~twice monthly (June 2026) vs their daily cadence |

Sources: [docs.shovels.ai data sources](https://docs.shovels.ai/docs/knowledge-base/data/quality/data-sources), [foundations understanding permits](https://docs.shovels.ai/docs/foundations-understanding-permits)

**Key insight:** Shovels openly says early on they focused on **processing** and initially **left scraping to incumbent data providers**, then expanded direct jurisdiction collection. The moat is normalization plus derived metrics, not raw permit rows.

---

## How PermitStack / PermitRadar / practitioners use LLMs

These are the best public blueprints for a **custom model per customer** business.

### PermitStack methodology (most explicit technical stack)

Platform connectors built per vendor:

| Platform | Access method |
|---|---|
| Socrata / Tyler SODA | REST API |
| ArcGIS FeatureServer / MapServer | REST query |
| CKAN / CARTO | DataStore / SQL API |
| Tyler EnerGov Citizen Self Service | Public JSON search behind portal |
| Accela Citizen Access | Public export / scrape, then normalize |

Pipeline steps:
1. **Per-jurisdiction config** maps source columns → canonical fields.
2. **Geocode / reproject** to WGS84.
3. **Status normalization** to fixed enum (`filed`, `issued`, `in_progress`, `final`, …).
4. **LLM or rules classifier** assigns ~20 categories (roofing, solar, HVAC, new construction, …).
5. **Future-date rejection** on bad upstream timestamps.
6. **`data_status` flag** per jurisdiction: `active`, `historical_archive`, or `frozen`.

Source: [permit-stack.com/methodology](https://permit-stack.com/methodology/)

### PermitRadar (HN builder, 200 scrapers)

Public stack described on Hacker News:
- **200+ scrapers across 85 cities**
- Express/TypeScript + Next.js + PostGIS + Redis + BullMQ
- Scrapers on cron → queue → geocoding → normalization → **AI classification (Claude Haiku)**
- Builder quote: *"AI was extremely useful for the repetitive parts (parsing HTML and mapping fields), but the hard part is comprehending each city's unique data and normalizing it into something consistent. That's still a human problem."*

Source: [HN thread](https://news.ycombinator.com/item?id=47260507)

### Where LLMs actually help (and where they do not)

| Good LLM use | Bad LLM use |
|---|---|
| Map unknown column headers to canonical schema | Invent project counts or dollar values |
| Classify permit description → CSI division / project type | Replace jurisdiction-specific business rules |
| Extract owner/GC/architect from press release HTML | Bulk-scrape Reddit as a primary source |
| Dedupe "Ryan Companies" vs "Ryan Companies US, Inc." | Present brand mention rate without reading specs |
| Summarize DRI PDF into structured fields with citation | Deploy without independent count verification |

Reddit's API blocked unauthenticated search during this research pass. Practitioner signal came from HN, vendor methodology pages, and Dodge/Shovels docs instead.

---

## Recommended architecture for a "custom model per customer" business

This is the business shape you described: anyone can pull construction intelligence for their territory and product categories.

### Product layers

```
┌─────────────────────────────────────────────────────────────┐
│  Customer-facing: alerts, CRM feed, division-filtered leads │
├─────────────────────────────────────────────────────────────┤
│  Classification: CSI division, commercial vs res, stage    │
│  (rules + LLM on description text, never on counts)        │
├─────────────────────────────────────────────────────────────┤
│  Normalization: canonical Project schema, entity resolution  │
├─────────────────────────────────────────────────────────────┤
│  Connectors: DRI, ArcGIS, Accela, EnerGov, Socrata, press  │
├─────────────────────────────────────────────────────────────┤
│  Provenance: raw document store, source URL, content hash    │
└─────────────────────────────────────────────────────────────┘
```

### Connector priority by ROI (any state)

1. **Statewide pre-construction register** (if it exists).
2. **Top 10 metros by construction spend** → identify vendor (Accela, EnerGov, Cityworks, in-house).
3. **ArcGIS open-data layers** with commercial permit or active development types.
4. **Accela/EnerGov automation** for cities without open data.
5. **Press/announcement LLM extraction** for gaps and marquee projects.
6. **FOIA batch** only for high-value counties with no digital access.

### Georgia-specific next actions

| Priority | Action | Expected yield |
|---|---|---|
| P0 | Accela commercial pull: Atlanta, Gwinnett, Cobb | Hundreds to thousands of commercial permits |
| P1 | Savannah-Chatham GIS conditional use + development layers | Coastal industrial/logistics |
| P1 | DeKalb planning status pages / permit lookup | Decatur / I-285 corridor |
| P2 | Forsyth EnerGov (token/API partnership) | North metro growth |
| P2 | Remove residual residential DRI mislabels (e.g. subdivision names) | Data quality |
| P3 | LLM press monitor for "groundbreaking" + "Georgia" + commercial types | Early-stage names |

### Commercial-only rules (enforce in code, not prose)

```python
EXCLUDED_TYPES = {"housing", "residential", "single_family", "townhomes", "subdivision"}
EXCLUDED_NOISE = {"seasonal sales", "tower co-locate", "construction trailer", "temp sign"}
KEEP_MULTIFAMILY = False  # set True only if customer sells into multifamily specs
```

SpecIndex currently keeps 3 multifamily records from prior research (apartment groundbreakings). Set `KEEP_MULTIFAMILY = False` to drop them if you want strict non-residential only.

---

## Scripts and data files (this repo)

| File | Purpose |
|---|---|
| `scripts/pull-ga-dri.py` | Georgia DRI statewide commercial filings |
| `scripts/pull-ga-municipal-commercial.py` | Alpharetta, Johns Creek, Marietta ArcGIS |
| `data/raw/ga-dri-projects.json` | Raw DRI output |
| `data/raw/ga-municipal-commercial.json` | Raw municipal output |
| `data/states/ga.json` | Merged Georgia corpus (489 projects) |
| `scripts/merge-national-corpus.py` | Rebuilds national JSON after state edits |

**Rebuild sequence:**
```bash
python3 scripts/pull-ga-dri.py --months 12
python3 scripts/pull-ga-municipal-commercial.py --months 12 --merge
python3 scripts/merge-national-corpus.py
npm run build
```

---

## Competitive positioning summary

| Vendor | Primary moat | Weakness SpecIndex can exploit |
|---|---|---|
| **Dodge** | Field verification, plan room, spec intelligence, Census-grade history | Expensive, black-box scoring, legacy UX |
| **Shovels** | Permit normalization API, LLM-derived metrics | Shallow on pre-planning; brand/spec depth limited |
| **PermitStack** | Broad connector library, honest `data_status` flags | General-purpose, not BPM spec-window focused |
| **SpecIndex** | Early-stage commercial leads by CSI division, cited public sources, honest zeros | Coverage still patchy; no spec book parsing yet |

Your custom-model business is not "scrape everything." It is:

1. **Connector library** per platform (Accela, EnerGov, ArcGIS, Socrata, state DRI).
2. **Jurisdiction config** per county/city (field map, commercial filters, refresh cadence).
3. **Customer profile** (states, divisions, brands, territory zips).
4. **LLM classification layer** that runs on descriptions and documents, never on aggregate statistics.
5. **Provenance and verification** so sales reps trust the list enough to call Monday morning.

That is Dodge's playbook minus the 500 reporters, delivered with Shovels-style automation and SpecIndex-style transparency.

---

## Appendix: Georgia Accela portal URLs

- Atlanta: https://aca-prod.accela.com/ATLANTA_GA/welcome.aspx
- Gwinnett: https://aca-prod.accela.com/GWINNETT/Welcome.aspx?module=Development
- Cobb: https://cobbca.cobbcounty.gov/CitizenAccess/Cap/CapHome.aspx?module=Permits

## Appendix: Georgia DRI portal

- Submissions index: https://apps.dca.ga.gov/DRI/Submissions.aspx
- Detail pattern: `AppSummary.aspx?driid={id}` and `InitialForm.aspx?driid={id}`
