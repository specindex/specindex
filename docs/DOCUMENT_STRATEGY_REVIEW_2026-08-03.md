# Document-Acquisition Strategy Review (Gemini, 2026-08-03)

External critical review of the 10-step pipeline, requested by Asif after a full
session added ~2,100 permit rows and zero documents. Gemini session:
`pipeline_10step_review` (search-grounded). Verbatim findings below, then our
assessment of which are actionable.

## Context given to Gemini

The differentiator is real construction documents (approved plan sets, structural
calcs, geotech reports, council/planning packets, RFPs), not permit-metadata
breadth — Shovels.ai already covers 2,450+ jurisdictions on that axis. Observed
failure modes supplied: batches stopping after step 5; an n=3 blanket conclusion
suppressing investigation across 49 Accela tenants; the biggest document find
living in a separate records portal invisible from the permit feed; ~2/3 of large
counties walled off by vendor platforms (BS&A, ViewPoint, MGO Connect, eTRAKiT,
SmartGov).

## (a) What is structurally wrong

1. **Permit-centric ROI & metric inversion.** Success is measured by permit rows
   ingested (step 5) rather than document yield. With no early "document circuit
   breaker," budget goes to ingesting barren rows — 404,000 of them against 55 PDFs.
2. **Coupling metadata ingestion to file retrieval.** Treating documents as
   optional downstream sub-resources of a permit record fails because Permitting
   Management Systems are built for workflow tracking, not document distribution.
   Attachments are routinely stripped, session-gated, or routed through separate CDNs.
3. **Premature blanket disqualification.** Steps 2/4 let n=3 failures or one gated
   endpoint mark a whole jurisdiction or platform dead, without distinguishing
   *the permit API being gated* from *document repositories being public*.

## (b) Is feasibility-in-step-2 / capture-in-step-8 the right split?

**No — wrong split.** Document acquisition should be its own decoupled phase with
its own discovery loop. Step 2 evaluates document feasibility *relative to the
permit portal*; when the portal lacks files, the pipeline wrongly concludes
documents don't exist. Recommended shape:

- **Phase I — Entity/Project Discovery:** extract address, APN/parcel ID, project
  name, permit # from *any* structured source.
- **Phase II — Document Endpoint Discovery:** a dedicated loop querying EDMS
  archives, council portals, and state databases using APN/address/permit #.
- **Phase III — File Capture & Validation:** guarantee content-type = PDF/CAD
  before text extraction.

## (c) High-yield sources we're ignoring by being permit-portal-centric

1. **Planning & zoning / city council portals — Legistar, Granicus, PrimeGov,
   BoardDocs.** Agendas and board packets for Planning Commissions, Design Review
   Boards, and City Councils carry complete, unauthenticated, high-resolution
   architectural plan sets, EIRs, and geotech reports.
2. **Public procurement / RFP / bid portals — Bonfire, DemandStar, PlanetBids,
   BidNet, SAM.gov, state DOTs.** Public bid packages release complete engineering
   drawings, structural calcs, and project manuals *before* permit issuance.
3. **Enterprise Document Management Systems (EDMS) — Laserfiche WebLink, Hyland
   OnBase, JustFOIA, NextRequest.** Municipal clerks store historical and approved
   plan sets in public record archives rather than the active permit database.
4. **State-level technical & environmental filings** — CA CEQAnet/GeoTracker,
   state fire marshal commercial plan-review databases, state occupational boards
   (e.g. Texas TDLR TABS).
5. **GIS / parcel feature attachments** — ArcGIS Online layers (capital projects,
   zoning cases, development tracking) often attach plan PDFs directly to map
   features, bypassing permit table APIs entirely.

## (d) Systematically exploiting the "separate records portal" pattern

1. **EDMS signature fingerprinting.** During jurisdiction discovery, probe root and
   subdomains for known EDMS software signatures — `/weblink/`, `/docushare/`,
   `/onbase/`, `/publicrecords/` — *regardless* of which permit system the
   jurisdiction runs.
2. **APN / address multi-target search.** Treat APN and normalized street address as
   the universal query key. Run automated searches like
   `site:{jurisdiction_domain} "plan set" OR "structural" OR "geotech" filetype:pdf`.
3. **Board packet API scrapers.** Build dedicated connectors for the four dominant
   council-management systems (Legistar, Granicus, PrimeGov, BoardDocs), filtering
   meeting attachments by keywords (conditional use permit, site plan review,
   variance, structural).

## (e) Highest-leverage change to make first

**Decouple document discovery and build an automated Planning Commission / Board
Packet harvester (Legistar / Granicus / PrimeGov / BoardDocs).** These packets hold
exactly the high-density documents wanted (approved site plans, architectural
elevations, geotech reports), are unauthenticated PDFs by law, and bypass the
walled-off vendor permit platforms entirely.

**Immediate rule to add at step 5:** if a permit source yields <1% document density
on a 50-record sample, freeze permit-row ingestion for that source and divert
discovery to the jurisdiction's planning board and EDMS endpoints.

## Our assessment

- **(d)'s EDMS fingerprinting directly explains our biggest win.** Snohomish County
  WA's 12–213-docs-per-permit repository is an OpenText Content Server at
  `/pdspublicrecords/` — precisely the "probe for EDMS signatures on subdomains"
  pattern. We found it by luck; fingerprinting would find it by rule, and would
  likely find more.
- **(a)3 matches the item-91 failure exactly** — one gated permit API generalized
  into "this platform never serves documents," across 49 tenants.
- **(c)1 and (c)2 are genuinely unexploited.** The corpus has SAM.gov federal
  solicitations (roadmap item 16) but no Legistar/Granicus/PrimeGov/BoardDocs
  connector and no state/local bid-portal connector at all.
- **The <1% document-density circuit breaker is the cheapest high-value change** —
  it converts "documents are the moat" from a stated policy into an enforced gate,
  which is what actually failed this session.

---

# Round 2 — pressing Gemini on specifics (2026-08-03)

Gemini was challenged on the claims it asserted without justification. It conceded
several. Same session, resumable.

## 1. The <1% threshold — conceded as statistically flawed

Gemini: "The 1% rule on N=50 was statistically flawed. At N=50, zero document hits
has a wide 95% binomial confidence interval (0% to 7.1%)." Replacement rule:

- **Stratify first** — filter out low-value trade permits (roofing, MEP, sign,
  residential alterations). Sample only Commercial New Construction, Major
  Additions, or valuation > $1M (or top 10% valuation for that jurisdiction).
- **N = 200 high-value records**, then take the upper bound of the 95% Wilson score
  interval. 0/200 gives an upper bound of 1.8% → classify the portal's document
  tier as Gated/Barren and trip the breaker.
- **Value-weighted metric**: measure documents per valuation dollar, not raw count.
  One $400M hospital yielding a 200-page plan set passes the gate even if 499 minor
  permits yield nothing.

## 2. "Unauthenticated by law" — conceded as overstated

State open-meetings statutes (Brown Act CA, Texas OMA, Florida Sunshine, Illinois
OMA) mandate that **agendas** be posted and that materials distributed to board
members be available for inspection. They do **not** mandate digital unauthenticated
PDF hosting of every exhibit.

- **Reliably public:** California and Florida municipalities consistently attach
  full multi-MB site plans, elevations, and EIRs to digital packets on
  Legistar/Granicus. Major metro county commissions likewise.
- **Not public:** Texas and rural jurisdictions often post 2-page text agendas with
  backup exhibits held at the City Secretary's office (PIA/FOIA required). Many
  planning departments also strip drawings citing **AIA copyright** or post-9/11
  **building-security exemptions** (schools, utilities, government facilities).

## 3. Council-management vendor landscape (verify before building)

| Vendor | Est. US jurisdictions | Access | Endpoint shape |
|---|---|---|---|
| Legistar (Granicus) | ~500–800 major cities/counties | **Stable public REST API** | `GET https://webapi.legistar.com/v1/{client}/matters` and `/matters/{id}/attachments` |
| BoardDocs (Diligent) | ~3,000–4,000 (school boards, small/mid cities) | No public REST API; scraping | `POST https://go.boarddocs.com/{state}/{client}/Board.nsf/BD-GetAgendaItem` (IBM Domino AJAX) |
| PrimeGov (CivicPlus) | ~300–500 mid-sized cities | Internal JSON API | `GET https://{client}.primegov.com/api/v2/PublicPortal/GetListItems?meetingId={id}` |
| CivicClerk / eScribe | ~1,500+ small/mid municipalities | Internal portal API / HTML | `GET https://{client}.civicclerk.com/Web/Meetings/GetMeetingItems` |

Legistar is the only one with a published unauthenticated REST API for attachments
across nearly all client instances. **Counts are Gemini estimates — verify live.**

## 4. EDMS fingerprinting signatures

- **Laserfiche WebLink** — paths `/WebLink/`, `/weblink/`, `/laserfiche/`; markers
  `<title>Laserfiche WebLink</title>`, `weblink.js`. Download:
  `GET /WebLink/ElectronicFile.aspx?docid={DocID}&dbid={DBID}`. Search:
  `POST /WebLink/Search.aspx` or `GET /WebLink/api/search` (WebLink 10+).
- **Hyland OnBase** — paths `/OnBase/`, `/AppNet/`, `/PublicAccess/`, `/docpop/`;
  markers `docpop.aspx`, `passthru.aspx`, `<input name="clienttype" value="html">`.
  Download: `GET /AppNet/docpop/docpop.aspx?docid={DocID}`; modern REST
  `GET /OnBase/api/documents/{docId}/content`.
- **OpenText Content Server** — paths `/otcs/livelink.exe`, `/otcs/cs.exe`,
  `/Livelink/`; marker `<input type="hidden" name="func" value="ll">`. **Important:
  Gemini says the SOAP proxy we reverse-engineered at Snohomish
  (`otlinkerws.asmx`, GetData/SaveFile) is NOT generalizable** — it's a bespoke
  third-party integrator deployment. Standard OpenText uses native REST
  (`/otcs/cs.exe/api/v1`) or legacy CGI
  (`/otcs/cs.exe?func=ll&objId={id}&objAction=download`).
- **NextRequest** — `{client}.nextrequest.com`; `GET /api/v1/documents?q=plan+set`.
- **JustFOIA** — `{client}.justfoia.com`; `GET /api/public/documents`.

## 5. Bid portals — the registration trap (kills automated capture)

- **Bonfire** — gated. Titles public; attachment download needs vendor registration.
- **PlanetBids** — gated. Registration required for bid/contract documents.
- **DemandStar** — gated *and paywalled*, ~$5 per document package without a subscription.
- **BidNet Direct** — gated, full plan downloads often behind paid tiers.

**Actually open:** state DOT portals (Caltrans, TxDOT, FDOT) host plan sets and
bridge specs on unauthenticated servers; and self-hosted municipal purchasing pages
that post RFPs as static `.gov` PDF links without commercial procurement software.

## 6. Connector build order (Gemini's ranking + confidence)

| Rank | Connector | Confidence | Key risk | What would change the rank |
|---|---|---|---|---|
| 1 | Legistar Web API | 95% | Some clients require an API token | Drop if >30% of top-100 metros token-lock |
| 2 | State DOT + environmental (CEQAnet, GeoTracker) | 90% | Non-standard schemas per state | Drop if geography needs local permits over state infra |
| 3 | EDMS auto-probes (Laserfiche, OnBase) | 75% | Public search disabled at IIS level | Raise if fingerprinting finds >200 live unauthenticated targets |
| 4 | Council scrapers (BoardDocs, CivicClerk, PrimeGov) | 60% | UI changes break DOM parsers | Raise if a unified abstraction yields high plan-set density |
| 5 | Filtered permit attachment extractor ($1M+ only) | 30% | Session timeouts, auth redirects | Raise if valuation filtering yields >15% doc availability at N=200 |
| 6 | Commercial bid portals | 10% | Anti-bot, CAPTCHA, paywalls, bans | Only if willing to maintain paid vendor credentials |

---

# Empirical result: Accela document probe (2026-08-03)

20 of 21 wired Accela tenants probed live with the OKC 3-step pattern. Full table in
`docs/accela-doc-probe-batch2.md`.

**5 confirmed document-viable, each proven by downloading real PDF bytes anonymously:**

| Tenant | Hit rate | Proof |
|---|---|---|
| IN-INDIANAPOLIS (`INDY`) | 3/3 | 8.9 MB architectural sheet set |
| ID-ADA (Boise) | 5/5 | 202 KB permit application |
| IN-ALLEN (`ACFW`) | 5/5 | 66 KB ILP permit |
| OH-BUTLER | 4/5 | 1.0 MB application |
| MN-OLMSTED | 2/5 | 386 KB application submittal |

**Item-91 verdict: two right, one wrong, generalization disproven.** SLCREF (Salt
Lake) and COC (Cleveland) genuinely gated — empty grid across 14 sampled records
each. **INDY was misjudged: it serves full plan sets with no login.** Item 91's
load-bearing claim ("standard Accela General Public behavior, not a per-agency
fluke") was used to justify *not* testing the remaining 5 Accela sources — that skip
cost four viable sources, Boise among them. Anonymous document access is a
**per-agency config choice**, never a platform property.

**Two provider bugs that make a viable tenant look gated** (fix these — some of the
13 "gated" verdicts may be false negatives for the same reasons):
1. **Wrong `agencyCode`.** On custom-domain tenants the URL path segment is not the
   agency code — Boise is `BOISE` not `CitizenAccess`; McAllen is `MCALLEN` not
   `Portal`. A wrong code yields an error-banner detail page and an attachments
   frame that never binds — visually identical to gating. Harvest `agencyCode` from
   the results grid's own hrefs instead of inferring it from the URL.
2. **Date fields suppress the search.** ACFW, BUTLER, OLMSTED, SHELBYCO, and
   grandrapids return no results grid when the general-search date range is
   populated, but work fine when it's blank.

**Unresolved:** 2 tenants broke at the search layer with no document verdict —
TX-BROWNSVILLE (its configured `permit_type_label` no longer exists; dropdown shows
only `--Select--`) and NC-BUNCOMBE (non-standard search UI).

**One claim in the probe report is wrong and should not be propagated:** it states 8
probed agencies "have no entry in `state_configs.py` at all" (ACFW, grandrapids,
OLMSTED, BUNCOMBECONC, CABARRUS, BUTLER, MONTCOOH, SHELBYCO). They are all wired —
as IN-ALLEN, MI-KENT, MN-OLMSTED, NC-BUNCOMBE, NC-CABARRUS, OH-BUTLER,
OH-MONTGOMERY, TN-SHELBY respectively (verified by enumerating `STATE_CONFIGS`).
