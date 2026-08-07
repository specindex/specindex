# Plan: Pull Pre-Construction Projects and Spec Documents

This is the execution detail for the spec-pull skill. Source tables: when running as the skill, use `references/project-sources.csv` (Stage 1 discovery sources) and `references/sources.csv` (state portals) in this folder. When running standalone from the workbook, the same data lives on the "Commercial Project Sources" and "State Portals" tabs of `state_spec_document_portals.xlsx`.

## Mission

Two jobs, run in this order. Job A (project discovery): widen commercial project capture using the verified sources on the workbook's "Commercial Project Sources" tab. Job B (document pull): collect current specification documents (spec books, project manuals, bid proposals) for active pre-construction projects from official state government bid portals on the "State Portals" tab. Two source types per state there: Vertical (state building/facilities construction, where CSI-division building product specs live) and DOT (highway lettings), each with URL, access requirements, and an Ease Tier.

## Job A: project discovery (Stage 1 of the funnel)

Verified 2026-08-06, 47 sources on the "Commercial Project Sources" tab in three groups:

1. Open-data permit feeds (29 metros). Start with the eleven that expose a clean commercial filter through a real API: Denver (commercial-only dataset), Seattle, Austin, Philadelphia (Carto SQL, `commercialorresidential` field), Columbus, Nashville, Miami-Dade, Raleigh, Orlando, Minneapolis, LA city. Pull daily or at the dataset's stated cadence; store source URL and record ID with every project.
2. Platform adapters. The Accela Citizen Access adapter (aca-prod.accela.com/{AGENCY} pattern, 900+ agencies) is the highest-leverage build because it covers the biggest no-open-data metros: Houston area, Dallas, Phoenix/Maricopa, Clark County NV, King County. Citizenserve (enumerable installationID) and SmartGov (shared domain) are the next easiest. Skip Cloudpermit and MyGovernmentOnline (login-walled).
3. Bid aggregators + federal. SAM.gov's Get Opportunities API v2 (free key) is the only source with a documented API that includes direct spec attachment downloads; use it for federal buildings (GSA, VA, USACE). Local-bid networks consolidate into two adapter families: Euna (Bonfire, DemandStar, Ionwave) and SOVRA (BidNet). Per-agency portals are public; documents usually need a free account, so log rather than register.

Excluded on purpose everywhere: Dodge, ConstructConnect, Construction Journal, BuildCentral. Paid or competitor content, off-limits under the public-data rule.

## Ground rules

1. Use only official government portals from the spreadsheet. Do not scrape third-party aggregators.
2. Respect robots.txt and each site's terms of use. Do not create accounts, bypass logins, or spoof headers. If a document needs an account, log it as "registration required" and move on. A human decides later which registrations are worth doing.
3. Public data only. Everything collected must be traceable to its public source URL.
4. Do not submit anything on any portal. Read and download only.

## Job B: document pull — order of attack

Work the Ease Tiers in order. Tier 1 first because it is proven and cheap, Tier 2 next, Tier 3 last (log only, do not chase).

### Phase 1: Tier 1 sources (direct free PDFs, no login)

These are the rows marked Tier 1 in the spreadsheet. Three are already proven end-to-end (spec books retrieved with a plain fetch on 2026-08-06):

- Missouri FMDC: listing page exposes a direct spec PDF per active project. Example pulled: R2511-01 Final Bid Specs (HVAC replacement, Division 23 and 26 content).
- Maine BGS: Manual and Drawings PDFs are linked inline on the single listing page. Example pulled: 3843_Project_Manual_DAFS.pdf.
- Delaware: spec books live free on bidcondocs.delaware.gov. The listing UI at bids.delaware.gov is a JavaScript app, so enumerate the document host or use a browser tool.

For each Tier 1 row:

1. Fetch the portal URL from the spreadsheet.
2. Enumerate active solicitations. If the page is a JavaScript app (noted in the Notes column for DE and FL), use a browser/computer-use tool if available; otherwise note "needs browser" and continue.
3. For each active project, find the specification document. Names to look for: "specs", "specifications", "project manual", "bid book", "proposal", "IFB", "contract documents". Prefer the spec book over drawings.
4. Download the PDF. Confirm it is a real spec document by checking for CSI division headings (Division 01 General Requirements, Division 23 HVAC, Division 26 Electrical, and so on).
5. Save as `STATE_TYPE_PROJECTID_shortname.pdf` (example: `MO_VERT_R2511-01_hvac-troopB.pdf`).
6. Append a row to `pull_log.csv`: state, type, portal, project id, project name, bid due date, document URL, file name, file size, CSI divisions spotted, retrieved date, status.

### Phase 2: Tier 2 sources (free account required)

Do NOT create accounts. For each Tier 2 row:

1. Fetch the portal and enumerate whatever is publicly visible (project titles, bid dates, agencies, ad PDFs).
2. Log every active construction solicitation found to `pull_log.csv` with status "listed, registration required" and the registration URL.
3. Flag the highest-value registrations in a summary. Bid Express (bidx.com) caveat, measured Aug 2026: no anonymous read path exists and even an info account requires signing in, so treat it as a deliberate human registration decision, not a quick unlock, and note that 12+ DOT states already have working adapters without it. Others worth noting: NY OGS (Bid Express, 7-day activation), Bonfire (UT, WA), CTsource, SIGMA (MI), NDBuys.

### Phase 3: Tier 3 sources (fee, password, or offline distribution)

Log only. For each Tier 3 row, record what exists and what it costs (QuestCDN fees for ID/NV/WY, WV's $125 vendor fee, NH's phone-issued password, designer-distributed spec books in MT, NE, TN). Do not pay or call anyone.

## Deliverables

1. `pull_log.csv` covering all 100 sources, even the ones that produced nothing.
2. A `specs/` folder of downloaded PDFs organized by state.
3. A short summary: documents retrieved per state, dead links found (with suggested replacement URLs), which registrations would unlock the most additional coverage, and any portal whose URL has changed since August 2026.

## Practical notes

- Portal URLs rot. Alabama and Wisconsin both migrated platforms within the last two years. If a URL 404s, search "[state] [agency] construction bid advertisements" and log the new URL.
- DOT lettings run on monthly or biweekly cycles, so the set of available documents changes constantly. Record the letting date with every document.
- Spec books are large (often 300 to 1,000+ pages). If storage is a concern, capture the table of contents pages plus the document URL rather than every full PDF, and note that choice in the log.
- Verify every "success" by reading actual content from the PDF, not just by getting a 200 response. A login redirect page can return 200.
- Batch states in groups of 10 and checkpoint the log after each batch so partial progress survives interruption.
