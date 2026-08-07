# Spec document coverage — sources, funnel, and what is proven

**SPX-COV-001 v1.1 · consolidated 2026-08-06**

Merges `specindex_coverage_plan.md.docx` (the four-stage funnel) and
`state_spec_document_portals.xlsx` (100 link-checked state sources) into one
file, plus live verification done while consolidating. The originals stay in
`docs/` as the record of what was compiled; this is the working copy.

> **In one line.** Get every project, then every document, then classify the spec
> books and hunt down the missing ones by search — a four-stage funnel where the
> first three stages are already proven and the whole thing costs almost nothing
> but adapters.

---

## 1. Where coverage stands

The index is **wide by state and thin by county**, and depth stops at the spec
book's front door.

| Dimension | Today (2026-08-06) | The gap |
|---|---|---|
| Projects | 591,618 tracked | Healthy. Public claim stays 500K+. |
| Geography | 50 states, 382 counties | US has 3,143 counties. |
| Sources | Public permit, bid, award records | State and local bid portals barely tapped. |
| Record depth | Stage, location, value, sq ft, owner, A/E | Permit-derived; sparse on private work. |
| Brand intelligence | Mention detection from public coverage | Press-based. The real answer is in Division 23/26 text. |
| **Spec books** | **Zero** | **This is the moat.** |
| Freshness | Weekly pipelines | Bid-stage sources change daily. |

**Honest about the numbers.** "382 counties" undersells reach if state sources
already catch projects in unindexed counties. Define *indexed* as "has a
dedicated source feed", then recount before marketing any county number.

A sharper version of the same problem, measured 2026-08-06: **43% of in-window
zero-document projects are NYC, and none of them carried a street address** until
the DOB NOW backfill. A county count cannot see field-level emptiness.

---

## 2. The funnel

Four stages, in order. Each stage's output is the next stage's input, and each
has its own metric.

| Stage | What it does | Metric |
|---|---|---|
| **1. Get all commercial projects** | Widen capture: permits, bid portals, awards | Projects indexed; counties with a dedicated feed |
| **2. Get all their documents** | Pull every attached PDF for every bid-stage project | % of bid-stage projects with ≥1 document |
| **3. Classify spec documents** | Detect true spec books (CSI division structure) | % of documented projects with a confirmed spec doc |
| **4. Gap-fill by search** | Targeted search **only where stage 3 found nothing** | Recovery rate on the gap |

> **If you ship one thing:** stages 2 and 3 on the Tier 1 portals. Full spec
> books were pulled from Missouri, Maine and Delaware with no login, containing
> real Division 23 HVAC and Division 26 Electrical content. No competitor cites
> page-level spec text from free public sources.

**Search is stage 4, not stage 2.** It runs only for projects already known to be
missing a spec doc. Running it early — as was tried on 2026-08-06 — spends
grounded-search budget everywhere and returned a 0% hit rate over 10 projects.

---

## 3. Breadth moves (stage 1)

Scale by **platform adapter, not by jurisdiction**. A few vendors run permitting
and bidding for hundreds of agencies each.

| # | Move | What it adds | Effort |
|---|---|---|---|
| B1 | City/county open-data permit feeds (Socrata) | Structured JSON permits, daily, free | Low — start here |
| B2 | Permit platform adapters: Accela, Tyler EnerGov | Each opens tens to hundreds of jurisdictions | Medium, one at a time |
| B3 | The 100 state bid portals below | Bid-stage vertical projects with owner and A/E | Low for Tier 1, already mapped |
| B4 | Local aggregators: Bonfire, BidNet, Periscope | Universities, K-12, hospitals, airports | Reuses B3 adapters |
| B5 | Structured DOT feeds: TxDOT Socrata | Real APIs, lower priority | Low |

**Measured example of B-class leverage (2026-08-06):** the Legistar/Granicus API
is one adapter covering 15 resolved jurisdictions, including NYC — 212,985
projects, all five boroughs, on a single client slug.

---

## 4. Retrieval by source group (stage 2)

| Source group | How | Notes |
|---|---|---|
| Tier 1 portals | Direct crawl, no accounts | MO and ME expose spec PDFs on the listing page |
| WAF-protected hosts (DE) | Browser User-Agent **and** `Referer` | See §7 — this is not a JS problem |
| JS-rendered listings (FL, DE) | Headless browser to enumerate; PDFs themselves open | Playwright |
| Free-registration portals | One Bid Express info account (~20 DOT states) | Confirm terms of use permit automated pulls |
| QuestCDN states (ID, NV, WY) | $15–$42 per document | Skip until a customer asks |

## 5. Classification (stage 3)

A cheap classifier pass over every stored PDF. A true spec document has CSI
MasterFormat structure: numbered sections (`23 05 00`), division headings,
"PART 1 GENERAL / PART 2 PRODUCTS / PART 3 EXECUTION".

| Output field | Why |
|---|---|
| `doc_type` (spec book, project manual, drawing set, addendum, bid form) | The funnel metric depends on it |
| Divisions present, with page ranges | Powers division-level search and brand extraction |
| Basis-of-design mentions, named manufacturers | The product answer, with page-level citation |
| Spec openness signals (proprietary vs performance vs "or equal") | Openness score v2 |

## 6. Gap-fill by search (stage 4)

| Query pattern | Example |
|---|---|
| `"PROJECT NAME" + specifications filetype:pdf` | `"Wellness Center Re-Use Renovation" specifications filetype:pdf` |
| `"PROJECT NAME" + "project manual"` | Catches the commonest spec-book title |
| `site:` the awarding authority or A/E domain | `site:bidcondocs.delaware.gov PSD25001` |
| Project number + state | `R2511-01 Missouri bid specs` |

**Guardrails:** public, no-login sources only. No paid plan rooms, no Dodge or
ConstructConnect content, ever. Every recovered doc keeps its found-at URL.

---

## 7. Proven pulls — verified end to end

Three portals drilled to a complete spec book with a plain HTTP fetch and no
account. **Re-verified on consolidation**, page counts and divisions read out of
the actual PDFs rather than taken from the source workbook.

| State | Project | Pages | Divisions found in the PDF | Result |
|---|---|---|---|---|
| **Missouri** | R2511-01 Replace HVAC & Boilers, Troop B HQ, Macon | **227** | 00, 01, 05, **23 Mechanical, 26 Electrical** | SUCCESS, no login |
| **Maine** | #3843 Wellness Center Re-Use Renovation, Augusta | **131** | 00 Procurement, 01 General Requirements, 20 | SUCCESS, no login |
| **Delaware** | PSD25001 Polytech HS Storm Water | 9.3 MB | 31 Earthwork, 33 Utilities | SUCCESS **with headers** |

```
https://oa.mo.gov/sites/default/files/bid-opportunities/_R2511-01%20Final%20Bid%20Specs.pdf
https://www.maine.gov/dafs/bgs/sites/maine.gov.dafs.bgs/files/inline-files/3843_Project_Manual_DAFS.pdf
https://bidcondocs.delaware.gov/PSD/PSD25001-PHS_STORM-specs.pdf
```

### Correction to the source workbook: Delaware is WAF-blocked, not JS-rendered

The workbook files Delaware under "JS-rendered portals". The *listing UI* is —
but the **PDF host itself rejects plain fetches at the edge**:

```
$ curl -sL https://bidcondocs.delaware.gov/PSD/PSD25001-PHS_STORM-specs.pdf
<html><head><title>Request Rejected</title></head><body>
The requested URL was rejected. Please consult with your administrator.
Your support ID is: <14533086336493691946>
```

245 bytes, **HTTP 200**. A crawler that checks status codes records this as a
successful fetch of a real document. Adding a browser User-Agent and
`Referer: https://bids.delaware.gov/` returns the full **9,345,738 bytes**.

Two rules follow, both of which this file exists to prevent re-learning:
content-check every fetch rather than status-check it, and treat a "dead" host as
unproven until it has been tried with real browser headers.

---

## 8. Sequencing — 90 days

| Window | Ship | Measure |
|---|---|---|
| Days 1–30 | Stages 2+3 on MO, ME, DE. First Socrata city feeds | Spec docs stored and classified; % with Division content |
| Days 31–60 | Stages 2+3 on all Tier 1 portals. Stage 4 gap-fill | % of bid-stage projects with a confirmed spec doc |
| Days 61–90 | Free-registration sources (Bid Express, Bonfire) | Openness coverage; freshness lag |

**Definition of done:** funnel dashboard live (projects → % with documents → %
with spec docs → % recovered by search), and every brand claim carries a
page-level citation.

## 9. Cost and guardrails

| Item | Reality |
|---|---|
| Cash cost | Near zero. Only QuestCDN charges per download. |
| APIs | Almost none exist. TxDOT Socrata is the exception. |
| URL rot | Alabama and Wisconsin both migrated platforms within 2 years. |

> **The rule.** Public data only, every fact linked to its public source.
> Government portals and the open web are not plan rooms, so "no plan room
> resale" stays true. Nothing from any prior employer, ever.

---

## 10. Source inventory — 100 portals

Compiled and link-checked 2026-08-06; **91 of 100 links verified live**, the rest
blocked automated checking but are the correct official portals.

**Type:** *Vertical* = state building/facilities construction, where
CSI-division spec books for building products live (50 sources). *DOT* = highway
lettings, roads and bridges (50 sources).

**Ease tier:** 1 = direct free PDF, no login. 2 = free account or vendor
registration. 3 = fee, password, or distributed offline via the project
architect.

| Tier | Sources | Access split |
|---|---|---|
| 1 | 34 | Free: 43 overall |
| 2 | 56 | Free registration: 53 overall |
| 3 | 10 | Registration + fee: 4 overall |

**Common platforms.** Bid Express (bidx.com) hosts DOT letting docs for 20+
states, free account to view in most. QuestCDN is a paid plan room (ID, NV, WY).
Bonfire hosts UT and WA vertical bids. Several vertical programs distribute spec
books through the project architect rather than any portal — MT, NE, TN, KS, MS,
SD — so no crawler reaches those at any effort.

## Tier 1 — direct free PDF, no login (34 sources)

The capture target. Start here.

| State | Type | Agency | URL | Documents available |
|---|---|---|---|---|
| Alabama | DOT | Alabama DOT (ALDOT) | https://alletting.dot.state.al.us/ | Letting files, bid proposals, plans, notices by letting date |
| Alaska | Vertical | Office of the Lt. Governor (statewide notices) | https://aws.state.ak.us/OnlinePublicNotices/ | ITB/RFP notices for state facility construction with links to solicitation docs |
| Arizona | DOT | Arizona DOT (ADOT) | https://cnsads.azdot.gov/current | Proposal pamphlets, project plans, addenda as PDFs |
| Arkansas | Vertical | Shared Administrative Services, Division of Building Authority | https://sas.arkansas.gov/building-authority/bid-announcements/ | Ads, bid documents, bid tabulations |
| Arkansas | DOT | Arkansas DOT (ARDOT) | https://ardot.gov/divisions/program-management/construction-contract-development/construction-contractors/currently-advertised-projects/ | Notices, proposals, plans, Q&A, EBS files per letting |
| Delaware | Vertical | OMB, Division of Facilities Management | https://bids.delaware.gov/ | Open solicitations with ITBs, specs, addenda |
| Delaware | DOT | Delaware DOT (DelDOT) | https://deldot.gov/Business/bids/ | Proposals, plans, specifications for advertised contracts |
| Florida | Vertical | Dept. of Management Services (DMS) | https://vendor.myfloridamarketplace.com/search/bids | Agency ads incl. DMS Real Estate Development & Management construction |
| Florida | DOT | Florida DOT (FDOT), Contracts Administration | https://www.fdot.gov/contracts/lettings/letting-project-info.shtm | Letting ads, bid items, proposals, plans, addenda by letting date |
| Georgia | Vertical | GSFIC / DOAS | https://ssl.doas.state.ga.us/gpr/ | GSFIC capital project construction/design solicitations with documents |
| Hawaii | DOT | Hawaii DOT (HDOT) | https://hidot.hawaii.gov/administration/con/current-bid-openings/ | Highway, airport, harbor bid notices, proposals, plans |
| Idaho | Vertical | Dept. of Administration, Division of Public Works | https://dpw.idaho.gov/construction/ | Ads for bids with plans and specifications per project |
| Illinois | DOT | Illinois DOT (IDOT) | https://webapps1.dot.illinois.gov/WCTB/LBHome | Notices of letting, plans, special provisions, proposals |
| Indiana | Vertical | IDOA Public Works Division | https://www.in.gov/idoa/state-property-and-facilities/public-works/ | Notices to bidders, plans, specs for state facility projects |
| Indiana | DOT | Indiana DOT (INDOT) | https://www.in.gov/indot/doing-business-with-indot/home/contracts/ | Letting schedules, contract letting docs (ERMS), plans, proposals |
| Iowa | Vertical | Iowa Dept. of Administrative Services | https://bidopportunities.iowa.gov/ | Active state bids incl. DAS construction with attached plans/specs |
| Kentucky | DOT | Kentucky Transportation Cabinet (KYTC) | https://transportation.ky.gov/Construction-Procurement/Pages/Letting-Bids.aspx | Letting schedules, bid proposals, plans, addenda |
| Maine | Vertical | DAFS Bureau of General Services | https://www.maine.gov/dafs/bgs/business-opportunities | Notices, project manuals/specs, drawings, addenda |
| Maine | DOT | MaineDOT | https://www.maine.gov/dot/doing-business/bid-opportunities | Ads, bid books, plans, addenda |
| Minnesota | Vertical | Dept. of Administration, RECS | https://mn.gov/admin/business/vendor-info/construction-projects/solicitations-announcements/ | State building solicitations, plans, specs/project manuals |
| Missouri | Vertical | Office of Administration, FMDC | https://oa.mo.gov/facilities/bid-opportunities | IFBs, electronic plans, project manuals/bid specs |
| New Mexico | Vertical | GSD Facilities Management / State Purchasing | https://generalservices.state.nm.us/state-purchasing/active-itbs-and-rfps/active-procurements/ | ITB/RFP docs and specs for state facility construction |
| New York | DOT | New York State DOT (NYSDOT) | https://www.dot.ny.gov/bids-and-lettings | Contract proposals, plans, amendments, letting schedules |
| North Carolina | DOT | North Carolina DOT (NCDOT) | https://connect.ncdot.gov/letting/Pages/default.aspx | Central and division letting proposals, plans, addenda, results |
| North Dakota | DOT | North Dakota DOT (NDDOT) | https://www.dot.nd.gov/construction-and-planning/construction-and-contractor-resources/bid-information | Plans and proposals (ePlans), specifications, bid opening info |
| Ohio | DOT | Ohio DOT (ODOT) | https://www.dot.state.oh.us/Divisions/ContractAdmin/Contracts/Pages/Bidding-Documents.aspx | Plans, proposals, addenda, EBS files, planholder lists, bid tabs |
| Oklahoma | DOT | Oklahoma DOT (ODOT) | https://oklahoma.gov/odot/business-center/contracts-and-proposals.html | Bid openings by date with advertised plans, proposals, bid docs |
| Pennsylvania | Vertical | Dept. of General Services (DGS), Public Works | https://www.pa.gov/agencies/dgs/submit-proposals-and-bids-for-commonwealth-projects | Public works IFBs/RFPs with project manuals and drawings |
| South Dakota | DOT | South Dakota DOT (SDDOT) | https://dot.sd.gov/doing-business/contractors/bid-letting-information/ | Letting plans, specifications, proposals |
| Texas | Vertical | Texas Facilities Commission / Comptroller | https://www.txsmartbuy.gov/esbd | Solicitations with attached specs/drawings for TFC and all state agencies |
| Texas | DOT | Texas DOT (TxDOT) | https://www.txdot.gov/business/plans-online-bid-lettings.html | Letting plans, proposals, addenda, bid tabs |
| Vermont | DOT | Vermont Agency of Transportation (VTrans) | https://vtrans.vermont.gov/contract-admin/bids-requests | Construction bid ads, plans, proposals |
| Virginia | Vertical | Commonwealth of Virginia (DGS) | https://eva.virginia.gov/ | VBO solicitations incl. Open Construction category with attachments |
| Washington | DOT | Washington State DOT (WSDOT) | https://wsdot.wa.gov/business-wsdot/contracts/search-contracting-opportunities | Currently advertised highway contracts, plans, proposals |

## Tier 2 — free account or vendor registration (56 sources)

Reachable, but each needs a credential. Confirm terms of use permit automated retrieval before building an adapter.

| State | Type | Portal | URL | Access |
|---|---|---|---|---|
| Alabama | Vertical | AlabamaBuilds (Public Works Bid Advertisements) | https://alabamabuilds.gov | Free |
| Alaska | DOT | Construction & Maintenance Contracting | https://dot.alaska.gov/procurement/bidding/ | Free registration |
| Arizona | Vertical | Arizona Procurement Portal (APP) | https://app.az.gov/page.aspx/en/rfp/request_browse_public | Free registration |
| California | Vertical | Cal eProcure (CA State Contracts Register) | https://caleprocure.ca.gov/pages/index.aspx | Free registration |
| California | DOT | Caltrans Advertised Projects (Weekly Ads) | https://ppmoe.dot.ca.gov/des/oe/weekly-ads/all-adv-projects.php | Free registration |
| Colorado | Vertical | OSA Construction & Design Notices | https://osa.colorado.gov/state-buildings/construction-design-notices | Free registration |
| Colorado | DOT | Highway & Bridge Construction Bidding | https://www.codot.gov/business/bidding | Free registration |
| Connecticut | Vertical | DAS Construction Services Bid Board | https://portal.ct.gov/das/construction-services/bidboard | Free registration |
| Connecticut | DOT | CTDOT Contractor Resources (CTsource Bid Board) | https://portal.ct.gov/dot/business/contractor-resources | Free registration |
| Georgia | DOT | GDOT Lettings on Bid Express | https://ui.bidx.com/GADOT/lettings | Free registration |
| Hawaii | Vertical | DAGS PWD Bidding | https://publicworks.hawaii.gov/bidding/ | Free registration |
| Illinois | Vertical | CDB Construction Bulletin | https://cdb.illinois.gov/procurement/bidinformation.html | Free |
| Iowa | DOT | Current Lettings | https://iowadot.gov/consultants-contractors/contracts/current-lettings | Free |
| Kansas | Vertical | OFPM Design, Construction & Compliance | https://admin.ks.gov/offices/facilities-property-management/design-construction--compliance | Free |
| Kansas | DOT | KDOT Highway Letting Information | https://www.ksdot.gov/doing-business/highway-contractors/highway-letting-information | Free registration |
| Kentucky | Vertical | Kentucky eProcurement (eMARS VSS) | https://finance.ky.gov/eProcurement/Pages/default.aspx | Free registration |
| Louisiana | Vertical | FPC Construction Bid Ads & Results | https://www.doa.la.gov/doa/fpc/project-administration-state/construction-bid-advertisements-and-results/ | Free |
| Louisiana | DOT | LA DOTD Construction Lettings | https://wwwapps.dotd.la.gov/engineering/lettings/ | Free registration |
| Maryland | Vertical | eMaryland Marketplace Advantage (eMMA) | https://emma.maryland.gov/page.aspx/en/rfp/request_browse_public | Free registration |
| Maryland | DOT | MDOT SHA Contracts, Bids & Proposals | https://roads.maryland.gov/mdotsha/pages/Index.aspx?PageId=17 | Free registration |
| Massachusetts | Vertical | DCAMM Construction Bidding (e-Bid Room) | https://www.mass.gov/construction-bidding-and-other-dcamm-procurement | Free registration |
| Massachusetts | DOT | Highway Construction Contract Bidding | https://www.mass.gov/massdot-highway-construction-contract-bidding | Free registration |
| Michigan | Vertical | DTMB Design & Construction | https://www.michigan.gov/dtmb/procurement/design-and-construction | Free registration |
| Michigan | DOT | MDOT Bid Letting | https://www.michigan.gov/mdot/business/contractors/bid-letting | Free registration |
| Minnesota | DOT | MnDOT Bid Letting | https://www.dot.state.mn.us/bidlet/ | Free registration |
| Mississippi | Vertical | Construction Solicitations & Bid Tabs | https://www.dfa.ms.gov/construction-solicitations-bid-tabs | Free |
| Missouri | DOT | Bidding & Letting (Online Plans Room) | https://www.modot.org/bidding-and-letting-information | Free registration |
| Montana | DOT | MDT Contracting & Bidding | https://www.mdt.mt.gov/business/contracting/ | Free registration |
| Nebraska | DOT | Highway, Bridge & Local Projects Letting | https://dot.nebraska.gov/business-center/hwy-bridge-lp/ | Free registration |
| Nevada | DOT | NDOT Contract Services (Public Portal) | https://www.dot.nv.gov/doing-business/ndot-procurements/agreement-services/contract-services-3 | Free registration |
| New Jersey | Vertical | DPMC Project Advertisements | https://www.nj.gov/treasury/dpmc/contract_project_adv.shtml | Free |
| New Jersey | DOT | Construction Services - Current Advertised Projects | https://www.nj.gov/transportation/business/procurement/ConstrServ/ | Free registration |
| New Mexico | DOT | PS&E Bureau (Plans, Specs & Estimates) | https://www.dot.nm.gov/infrastructure/plans-specifications-estimates-pse-bureau/ | Free registration |
| New York | Vertical | OGS Construction Contractors Bid Opportunities | https://ogs.ny.gov/design-construction/construction-contractors | Free registration |
| North Carolina | Vertical | NC State Construction Office | https://www.doa.nc.gov/divisions/state-construction-office | Free registration |
| North Dakota | Vertical | ND Bidding Opportunities (NDBuys) | https://www.omb.nd.gov/doing-business-state/bidders/bidding-opportunities-and-resources | Free registration |
| Ohio | Vertical | OFCC Bids & RFQs | https://ofcc.ohio.gov/project-opportunities/bids-rfqs/bids-rfqs | Free registration |
| Oklahoma | Vertical | OMES CAP Bidding Process / Solicitations | https://oklahoma.gov/omes/divisions/capital-assets-management/construction-and-properties/biddding-process.html | Free registration |
| Oregon | Vertical | OregonBuys eProcurement Portal | https://oregonbuys.gov/bso/ | Free registration |
| Oregon | DOT | ODOT Bid & Award (eBIDS) | https://www.oregon.gov/odot/business/procurement/pages/bid_award.aspx | Free registration |
| Pennsylvania | DOT | ECMS (Engineering & Construction Management System) | https://www.ecms.penndot.gov/ECMS/ | Free registration |
| Rhode Island | Vertical | RI Bidding Opportunities (Ocean State Procures) | https://ridop.ri.gov/vendors/bidding-opportunities | Free registration |
| Rhode Island | DOT | RIDOT Bidding Opportunities | https://www.dot.ri.gov/ridotbidding/ | Free registration |
| South Carolina | Vertical | South Carolina Business Opportunities (SCBO) | https://scbo.sc.gov/ | Free |
| South Carolina | DOT | SCDOT Construction Letting Information | https://www.scdot.org/business/constructionletting-info.html | Free registration |
| South Dakota | Vertical | OSE Advertisements for Bids | https://boa.sd.gov/state-engineer/adv-advertisements.aspx | Free |
| Tennessee | DOT | TDOT Bid Lettings | https://www.tn.gov/tdot/tdot-construction-division/bid-lettings.html | Free registration |
| Utah | Vertical | DFCM Construction Management / U3P | https://dfcm.utah.gov/construction-management/ | Free registration |
| Utah | DOT | UDOT Contractor Resources / Contractor Zone | https://connect.udot.utah.gov/business/construction | Free registration |
| Vermont | Vertical | BGS Purchasing / VTBuys | https://bgs.vermont.gov/purchasing | Free registration |
| Virginia | DOT | VDOT Highway Contractors - Advertisements | https://www.vdot.virginia.gov/doing-business/business-opportunities/highway-contractors/advertisements/ | Free registration |
| Washington | Vertical | DES Public Works Bidding | https://des.wa.gov/do-business-state/public-works-bidding | Free registration |
| West Virginia | DOT | WVDOH Lettings | https://transportation.wv.gov/highways/contractadmin/Lettings/Pages/default.aspx | Free registration |
| Wisconsin | Vertical | DFD Projects Out for Bid | https://doa.wi.gov/Pages/DoingBusiness/DFDProjects.aspx | Free registration |
| Wisconsin | DOT | Highway Construction Contract Info (HCCI) | https://wisconsindot.gov/Pages/doing-bus/contractors/hcci/default.aspx | Free registration |
| Wyoming | Vertical | Bid Listings - Contractors | https://stateconstruction.wyo.gov/procurement/bid-listings-contractors | Free registration |

## Tier 3 — fee, password, or offline via the architect (10 sources)

Do not build for these. Several distribute spec books through the project architect, so no portal crawl can reach them at any effort.

| State | Type | Portal | Access | Notes |
|---|---|---|---|---|
| Idaho | DOT | ITD Advertised Projects & Bid Results | Registration + fee | Plan-holder access via QuestCDN (download fee); e-bidding via Bid Express. |
| Mississippi | DOT | MDOT Construction Lettings Bid System | Registration + fee | Many letting PDFs viewable free; proposal and plan sales through shop.mdot.ms.gov. |
| Montana | Vertical | A&E Current Bid Opportunities | Free | Listings free; plans and spec books usually distributed by the listed design consultant or Montana plan exchanges. |
| Nebraska | Vertical | State Building Division Construction Bids | Free | Full plans/specs hosted with third-party plan rooms (Builders Bureau Lincoln, Omaha Exchange Builders). |
| Nevada | Vertical | SPWD Bid Advertisements | Free registration | Bid documents issued through QuestCDN plan room; SPWD keeps a qualified bidders list. |
| New Hampshire | Vertical | NH Public Works Design & Construction | Free registration | Blocked automated check; NH public works projects are actually advertised on NHDOT's Invitation for Bid page with password-protected plans/specs. |
| New Hampshire | DOT | NHDOT Invitation for Bid | Free registration | Proposal/plan downloads need a password from the Contract Office (603-271-3732). |
| Tennessee | Vertical | STREAM Construction Bid List | Free | No direct downloads; contact the listed project designer for bid documents/project manuals. |
| West Virginia | Vertical | WV Bid Opportunities (wvOASIS Bulletin) | Registration + fee | Posts to wvOASIS Purchasing Bulletin; competitive bidding requires WV-1 registration + $125 annual fee. |
| Wyoming | DOT | WYDOT Contractor Bid Information | Registration + fee | Plans viewable free on site; downloads via QuestCDN for a small fee; e-bidding via iCX. |

## Paid platforms — what actually costs money

| Platform | Used by | Paid? | What costs money | What is still free |
|---|---|---|---|---|
| Platform / Site | Used By (in this workbook) | Paid? | What Costs Money | What Is Still Free |
| Bid Express (bidx.com, Infotech) | ~20 state DOTs (GA, CO, MA, MI, NJ, NM, OH-vert, OK-vert, SC, TN, WV, MT, NE, KS, IA, AK, and more) | Freemium | E-bidding: Core $100/mo (1 agency) or Advanced $349/mo (5 agencies); extra agency $35/mo. Online Plan Sheets download add-on $95/mo. Digital ID for bid submission $100 one-time. | Free info-only account can browse lettings and view/download letting documents from 40+ agencies. This is the single highest-value free registration. |
| QuestCDN | Idaho ITD, Nevada SPWD, Wyoming WYDOT (also many MT and municipal owners) | Pay per download | Digital bid set (eBidDoc) download: ~$15 to $42 per project (Idaho ITD is $15). Electronic bid submission via QuestVBid ~$42 extra. Premier subscription exists, price unpublished. | Free 'Regular' membership; viewing project ads and basic info is free. |
| Mississippi DOT (shop.mdot.ms.gov) | Mississippi DOT lettings | Pay for plans only | Printed/purchased plan sheets priced per sheet plus convenience fee via shopMDOT (registration required; Print Shop 601-359-7460 quotes exact cost). | Proposal PDFs and letting docs are actually free at mdot.ms.gov/bidsystem_data per-letting folders. Cheaper than the sheet says: docs are free, only plans cost. |
| West Virginia Purchasing (wvOASIS) | WV vertical (GSD building construction) | Fee to WIN, not to view | $125/yr WV-1 vendor fee is required only to receive purchase orders/contracts over $2,500. Not needed to view, download, or even submit a bid. | Viewing and downloading solicitations from the wvOASIS Purchasing Bulletin is free. Better than the Tier-3 rating on the State Portals sheet suggests. |
| Everything else in this workbook | All other 90+ sources | No | No other state portal in scope was confirmed to charge merely to download specs. | TxDOT, FDOT, PennDOT ECMS, and most portals post documents free (login sometimes required, but no fee). |
| API / MACHINE-READABLE ACCESS (almost none exist; scraping is the norm) |  |  |  |  |
| Platform / State | Used By (in this workbook) | API? | What Exists | Source / URL |
| TxDOT (data.texas.gov) | Texas DOT | Yes | Bid Tabulations is a live Socrata dataset with full SODA API (JSON/CSV, app token optional). Plus free structured EBS proposal files and PDF plans via txdot.gov / ftp.txdot.gov. Best machine-readable DOT in the country. | https://data.texas.gov/dataset/Bid-Tabulations/de7b-7dna |
| OpenGov Procurement | Texas Facilities Commission (bid submission portal) | Yes (customer-scoped) | Developer portal has Procurement APIs, but access needs an API key tied to an OpenGov customer entity. Not an open anonymous feed. | https://developer.opengov.com/catalog/public-service-platform-procurement |
| Proactis WebProcure | Rhode Island (Ocean State Procures) | Unofficial URL pattern | No official API, but the public MainBidBoard exposes predictable no-login URLs for solicitation views and even full document PDFs (solicitation_document.pdf?bidid=NNNN&ac=2). Programmatically fetchable. | https://webprocure.proactiscloud.com/MainBidBoard |
| Bid Express / Infotech | ~20 state DOTs | No | No public lettings API. Infotech's only public API is for Doc Express (contract docs, not lettings). Free .ebs/.ebsx AASHTOWare proposal files per letting are structured and parseable, but retrieved via the UI. | https://www.infotechinc.com/news/infotech-launches-new-doc-express-api-for-document-integration/ |
| Bonfire / Euna | Utah DFCM, Washington DES | No | No API. Public no-login Browse Opportunities HTML page (scrapeable); documents need a free vendor account. | https://vendor.bonfirehub.com/preview |
| Periscope S2G (OregonBuys) | Oregon | No | Public browse UI only; no feed found. | https://oregonbuys.gov/bso/ |
| Ivalua | North Dakota (NDBuys), Maryland (eMMA) | No | Ivalua's 'Open Ecosystem' integration layer is customer-only; public bid boards are UI-only. | https://www.ivalua.com/technology/ivalua-open-ecosystem/ |
| BidNet Direct | Colorado (Rocky Mountain E-Purchasing) | No | Account-based search and paid email-notification tiers; no API, RSS, or bulk feed. | https://www.bidnetdirect.com/colorado |
| California (Cal eProcure) | California vertical | No | SCPRS/CSCR bulk downloads froze in April 2018 (historical only). Current CSCR opportunities are UI-search only; nothing on data.ca.gov. | https://www.dgs.ca.gov/PD/Resources |
| Texas ESBD | Texas vertical (statewide solicitations) | No | UI search only; no dataset on data.texas.gov for ESBD. Docs are free downloads. | https://www.txsmartbuy.gov/esbd |
| New York (data.ny.gov) | NY OGS / NYSDOT | No | No current bid-opportunity dataset; only stale/adjacent ones. Live opportunities are in NYS Contract Reporter (free account, no API). | https://data.ny.gov |
| Virginia eVA Open Data | Virginia vertical | Historical only | eVA publishes open data on data.virginia.gov, but it is historical PO/spend data by year, not a live solicitation feed. | https://eva.virginia.gov/eva-open-data.html |
| Ohio DOT | Ohio DOT | No | DigitalPaper document viewer with free downloads and predictable documentId URLs; bid data published only as Power BI dashboards, not raw files. | https://www.transportation.ohio.gov/business/contracts/estimating/bid-data-reports |
| FDOT | Florida DOT | No | Per-letting pages with free plans/specs and machine-listable letting results at bidletting.fdot.gov (HTML/PDF, no documented API). | https://bidletting.fdot.gov/ |
| FL MFMP, NC eVP, IA bidopportunities, MI SIGMA, MD eMMA | Respective vertical rows | No | All are public or semi-public browse UIs with no documented API, RSS, or open-data feed. Scraping the listing pages is the only programmatic route. | See State Portals sheet for URLs |
| BOTTOM LINE |  |  |  |  |
| Money is rarely the barrier: only QuestCDN (3 states, ~$15-42/project) charges just to get documents. Bid Express is free to read; it charges to bid and for the plan-sheets add-on. |  |  |  |  |
| Real APIs are nearly nonexistent. TxDOT's Socrata dataset is the only true public API found; OpenGov's API needs a customer key; RI's WebProcure has an unofficial but fetchable URL pattern. |  |  |  |  |
| For a SpecIndex-style pipeline, the practical stack is: scrape Tier 1 listing pages directly, one free Bid Express account for ~20 DOT states, targeted free registrations (Bonfire, CTsource, SIGMA), and treat QuestCDN states as pay-per-document. |  |  |  |  |
| Research date 2026-08-06. Pricing from published fee schedules; confidence noted per row in the source column's page. |  |  |  |  |
---

## Companion files

- `docs/state_spec_document_portals.xlsx` — source workbook, 4 sheets
- `docs/specindex_coverage_plan.md.docx` — SPX-COV-001 v1.1, the funnel
- `docs/AGENT_STRATEGY.md` — how the pipeline runs, incident history
- `docs/SPECINDEX_STRATEGY.md` — whether, versus this file's what
