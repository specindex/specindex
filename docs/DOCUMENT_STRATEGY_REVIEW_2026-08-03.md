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
