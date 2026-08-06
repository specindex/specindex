---
name: spec-pull
description: Run the SpecIndex data pipeline — discover US commercial construction projects from verified public sources (city/county permit APIs, permit platform adapters, bid aggregators, SAM.gov) and collect pre-construction spec documents (spec books, project manuals, bid proposals) from official state bid portals, using two verified source tables (100 state + 47 discovery sources) and a proven 4-stage pipeline. Use whenever Asif asks to run the spec pull, pull or collect spec documents or spec books, get all commercial projects, expand project or county coverage, crawl state bid portals or permit feeds, get bid documents for a state or city, update the pull log, or count spec docs. Also use when he asks which portal or permit feed covers a state, county, or city, whether a source needs an account, payment, or an API, or how many projects a source yields. Do NOT use for SpecIndex investor or accelerator writing (specindex-context) or decks (specindex-deck).
---

# Spec Pull: 50-State Pre-Construction Spec Document Collection

This skill runs the document-collection pipeline behind SpecIndex's spec-book layer. Everything in it was verified in August 2026: 91 of 100 portal links checked live, and full spec books were actually retrieved end to end from Missouri, Maine, and Delaware with no login.

## Standing rules (apply every run, no exceptions)

1. **Public data only.** Official government portals and the open web. Never paid plan rooms, never Dodge or ConstructConnect content, never anything from a prior employer. These portals are government sources, not plan rooms, so SpecIndex's "no plan room resale" claim stays true — protect that.
2. **Never create accounts, bypass logins, or spoof headers.** If a document needs an account, log it as "registration required" and move on. A human decides which registrations to make.
3. **Never pay for anything.** QuestCDN states (ID, NV, WY) charge $15–42 per download; log and skip.
4. **Never submit anything on any portal.** Read and download only.
5. **Every document keeps its source URL and fetch date.** A fact without a citation is worthless to SpecIndex.
6. **Verify success by reading content, not HTTP status.** A login redirect returns 200. A real building spec doc shows CSI structure: division headings, section numbers like "23 05 00", "PART 1 GENERAL / PART 2 PRODUCTS / PART 3 EXECUTION". DOT documents are different by design: they use the state's Standard Specifications numbering (supplemental specs like "SS 100-3", Job Special Provisions, FHWA-1273) instead of CSI. Both count as confirmed spec docs; record which format you saw.
7. Respect robots.txt and each site's terms of use.

## The source tables

Two tables, matching the two halves of the pipeline.

**`references/project-sources.csv`** — 47 verified sources for Stage 1 (project discovery), in three categories:

- **permit_feed** (29): the largest metros' open-data permit datasets with API endpoints. Eleven have a clean commercial filter (Denver is commercial-only by design; Philadelphia's Carto SQL API has a `commercialorresidential` field verified live; Seattle, Austin, Columbus, Nashville, Miami-Dade, Raleigh, Orlando, Minneapolis, LA city). Big-metro holes with no open data: Houston, Phoenix/Maricopa, Clark County NV, King County, Dallas (frozen 2020), Atlanta (static 2024).
- **permit_platform** (8): one scraper per platform opens tens to hundreds of jurisdictions. Accela Citizen Access (aca-prod.accela.com/{AGENCY}, 900+ agencies) is the highest-leverage adapter and covers most of the no-open-data metros. Citizenserve and SmartGov are the next easiest. Cloudpermit and MyGovernmentOnline are login-walled — skip.
- **bid_aggregator** (10): SAM.gov is the standout — its free Get Opportunities API v2 includes direct spec attachment downloads (federal buildings: GSA, VA, USACE). Local networks consolidate into Euna (Bonfire, DemandStar, Ionwave) and SOVRA (BidNet) adapter families. Vendor Registry is sunsetting — never build on it.

**`references/sources.csv`** — 100 rows, one per state per source type, for the document pull. Columns include the portal URL, access requirements, estimated project volume since Jan 2025, and quirks. Key fields:

- **type**: `Vertical` (state building/facilities construction — where CSI-division building-product specs live; this is what matters most for SpecIndex) or `DOT` (highway lettings — volume, but roads-and-bridges specs).
- **ease_tier**: `1` = direct free PDFs, no login (30 sources — always start here). `2` = free account needed (59; one free Bid Express info account covers ~20 DOT states). `3` = fee, password, or architect-distributed (11; log only).
- **est_projects_since_jan2025**: approximate solicitation volume, ±50% on any single state. ~30K total (~8K vertical, ~21K DOT).

Known quirks to expect: Delaware and Florida listings are JavaScript apps (use a browser tool to enumerate; the PDFs themselves are open — Delaware docs live on bidcondocs.delaware.gov and are Google-indexed). Missouri and Maine expose spec PDFs directly on their listing pages. URLs rot: Alabama and Wisconsin both migrated platforms within two years, so on a 404, search "[state] [agency] construction bid advertisements" and log the replacement URL.

## The pipeline (4 stages, in order)

Full detail, naming conventions, and per-phase instructions: `references/execution-plan.md`. Read it before a full run. The shape:

1. **Get the projects.** Enumerate active solicitations on each portal, Tier 1 first.
2. **Get the documents.** Download every attachment (ads, proposals, drawings, addenda, manuals). Don't filter yet.
3. **Classify.** Type each PDF (spec book, project manual, drawings, ad, addendum, bid form, bid tab) by checking for CSI structure. Record divisions present with page ranges, basis-of-design mentions, named manufacturers, "or equal" language.
4. **Gap-fill by search.** For projects with no spec doc, targeted web search recovers copies hosted on architect sites, authority subdomains, and document hosts. Patterns: `"PROJECT NAME" specifications filetype:pdf`, `"PROJECT NAME" "project manual"`, `site:` the authority or A/E domain, project number + state. Run recovered docs through stage 3 too.

## Outputs (always)

- `pull_log.csv` — one row per source attempted, even when nothing was found: state, type, portal, project id, project name, bid due date, document URL, file name, file size, CSI divisions spotted, retrieved date, status. Allowed statuses: `downloaded` / `verified, not stored` (content confirmed, TOC evidence captured in lieu of the binary — the normal case when the runtime can't save PDFs) / `listed, registration required` / `needs browser` / `unreadable format` (legacy .doc, scanned image, no extractable text) / `dead link` / `no active solicitations`.
- `specs/` folder of PDFs named `STATE_TYPE_PROJECTID_shortname.pdf` (e.g. `MO_VERT_R2511-01_hvac-troopB.pdf`).
- A short summary: documents per state, dead links with suggested replacements, which registrations would unlock the most coverage, and the funnel — projects found → % with documents → % with confirmed spec docs → % recovered by search.

Spec books run 300–1,000+ pages. If storage is tight, capture the table-of-contents pages plus the URL instead of the full PDF, and say so in the log. Batch states in groups of 10 and checkpoint the log after each batch.

## Partial runs

Most requests won't be the full 50 states. "Pull specs for Georgia" means: look up Georgia's rows in sources.csv, run stages 1–4 on just those, produce the same outputs. "How many spec docs can we get from Texas?" means: read the Texas rows and volume estimates, and note TxDOT's Socrata dataset (data.texas.gov, Bid Tabulations, `de7b-7dna`) is the one true public API in the whole table.
