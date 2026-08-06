# Arkansas Spec Pull — Content Evidence

Retrieved 2026-08-06 via WebFetch (page/PDF converted to text and summarized; binary PDFs could not be stored in this environment, so per the skill's storage fallback the table-of-contents/section evidence below plus the source URL stands in for each full PDF).

Note on classification: none of the confirmed documents use CSI MasterFormat (Division 01/23/26, "PART 1 GENERAL / PART 2 PRODUCTS / PART 3 EXECUTION"). All confirmed documents are ARDOT highway lettings, which use the AASHTO-style ARDOT Standard Specifications (Edition 2014) section system (SS 100–800 series plus Job Special Provisions). This matches the skill's own framing that DOT sources yield "roads-and-bridges specs," not CSI building specs. The single Vertical (building-type) project produced no readable spec book.

## Source 1: DBA Bid Announcements (Vertical) — live, 1 active solicitation

URL: https://sas.arkansas.gov/building-authority/bid-announcements/

Page content as fetched (structure paraphrased from fetch output):

> Trotting Fox Trail Improvements | Arkansas Department of Parks, Heritage, and Tourism | Bid due 07/28/2026 2:30 PM | Project # 9002418R | Documents: Advertisement-9002418R.doc / Unofficial-Bid-Tab-9002418R.pdf
> Services: No current notices. Design Professional & Consultant Opportunities: No current notices.

- Advertisement-9002418R.doc: fetch returned "[binary data]" — legacy .doc, not parseable by the fetch tool. No spec structure verifiable.
- Unofficial-Bid-Tab-9002418R.pdf: fetch reported "unreadable or contains no machine-readable text content" — likely a scanned bid tab.
- No spec book or project manual is posted on the portal, consistent with the sources.csv note: "spec books sometimes distributed via the project design professional listed in the ad."

## Source 2: ARDOT Currently Advertised Projects (DOT) — live, 7 projects, all documents free, no login

URL: https://ardot.gov/divisions/program-management/construction-contract-development/construction-contractors/currently-advertised-projects/

Listing page evidence (fetch output): "This is a standard HTML page (not a JavaScript app, login, or error page)... ALL BIDS MUST BE SUBMITTED ELECTRONICALLY BY 10:00 A.M." Two lettings listed: August 12, 2026 (6 jobs) and November 4, 2026 (1 job). Every document link resolves to a direct PDF on media.ark.org/ardot/ with no login.

### 090702 proposal — full structure read (https://media.ark.org/ardot/090702_proposal.pdf)

Fetch output, quoted:

> "This is a federal-aid highway construction contract document package for an Arkansas Department of Transportation (ARDOT) project. It combines proposal instructions, regulatory requirements, and specifications."
>
> Section headings: "General," "Nondiscrimination," "Davis-Bacon and Related Act Provisions," "Contract Work Hours and Safety Standards Act," "Subletting or Assigning the Contract," "Safety: Accident Prevention," ... [Form FHWA-1273]
>
> "Errata for Standard Specifications (Edition 2014); Supplemental Specifications and Special Provisions Listing (organized by reference codes like 'SS 100-3,' 'JOB SP,' 'SP 108-1')" ... "section numbering (e.g., SS 400-1, SS 606-1) for technical specifications and references Arkansas State Highway Commission Standard Specifications, Edition 2014."

### 110812 proposal — Hwy 49 Mississippi River Bridge Rehab (https://media.ark.org/ardot/110812_proposal.pdf)

> Title block: "HWY. 49 MISSISSIPPI RIVER BRIDGE REHAB. (S)" – State Highway 49 Section 11, Phillips County. State Job 110812, Federal Aid NHPP-PRTT-HIPBIP-0054(31).
>
> Supplemental Specifications listed: "SS 100-3, SS 100-4, SS 102-2, SS 102-3, SS 103-2, SS 105-4, SS 107-2, SS 303-1, SS 306-1, SS 307-2, SS 308-2, SS 400-1 through SS 410-4, SS 416-1, SS 501-3, SS 502-1, SS 600-2 through SS 807-2" plus "JOB SP items for Cargo Preference, Buy America, Asphalt Mixtures, Bridge Work, Traffic Control."

### 030531 notice/proposal — Red River – Ogden (https://media.ark.org/ardot/030531_notice.pdf)

> Job PRTT-0041(46), "RED RIVER – OGDEN (S)": "raise the roadway grade on Highway 71 in Little River County" — ~1.466 miles; site clearing, earthwork, asphalt paving (base/binder/surface), drainage, guardrail, erosion control, pavement markings. "Site Use (A+C Method)-Calendar Day Contract."

### A30046 proposal (https://media.ark.org/ardot/A30046_proposal.pdf)

> "State Job No. A30046" — "Texarkana Visitor Center – East (Pvmt. Repairs) (S)", I-30 Section 11, Miller County. Headings quoted: "SS 102-3 Prequalification of Bidders," "SS 306-1 Quality Control and Acceptance," "JOB SP Mandatory Electronic Contract."

### 012535 proposal (https://media.ark.org/ardot/012535_1-proposal.pdf)

> "State Job Number 012535" — "Pope Co. Line – Little Rock Interstate Sign Upgrades (S)". Headings: "SS 100-3 Contractor's License," "SS 102-2 Issuance of Proposals," "JOB SP Mandatory Electronic Contract." Fetch: "containing complete proposal instructions, federal contract provisions (FHWA-1273), addendum notices."

### SA5143 proposal (https://media.ark.org/ardot/SA5143_proposal.pdf)

> "WOODLAND TRL. – CO. RD. 50 (OVERLAY) (S)", Newton County. Headings: "AGGREGATE BASE COURSE" (SS-303-1), "DESIGN AND QUALITY CONTROL OF ASPHALT MIXTURES" (SS-400-4), "PERCENT AIR VOIDS FOR ACHM MIX DESIGNS" (SS-400-5).

### SA5865 proposal (https://media.ark.org/ardot/SA5865_proposal.pdf)

> "HUDSON RD. OVERLAY (S)", Pope County, ~4.23 miles. Headings: "CONTRACTOR'S LICENSE" (SS-100-3), "DEPARTMENT NAME CHANGE" (SS-100-4), "ISSUANCE OF PROPOSALS" (SS-102-2). Fetch: "includes... the 2014 Standard Specifications reference, multiple supplemental specifications with revision dates, special provisions... construction plans, and proposal forms with required certifications."

## Stage 4 gap-fill (Vertical spec book) — attempted, no recovery

Searches run: `"9002418R" OR "Trotting Fox Trail" Arkansas specifications "project manual" bid`; `"Trotting Fox Trail Improvements" Arkansas bid specifications filetype:pdf`; `"9002418" Arkansas "Trotting Fox" addendum OR specifications OR "design professional"`; plus a design-professional search. Candidate URLs found in the search index, all returned 404 on fetch:

- https://ardot.gov/wp-content/uploads/Addendum-02-9002418.pdf (Addendum 02, project 9002418 — the pre-rebid number; "9002418R" suffix indicates a rebid)
- https://www.olympusgc.com/wp-content/uploads/2024/11/add_1_spec_plan.pdf
- https://www.olympusgc.com/wp-content/uploads/2024/11/add_2_specs.pdf

No publicly hosted spec book for 9002418R was found; distribution appears to be via the design professional named in the (unreadable) advertisement .doc.
