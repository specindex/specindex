# Tier-1 DOT portal adapters — findings

Eleven bespoke state DOT letting portals (the Bid Express states are a separate
batch; bidx.com was not touched). Built and verified 2026-08-06 against
`scripts/check-portal-adapters.py`. Every result below is a line the checker
printed, not a self-report.

## Result

| State | Checker | Documents reachable | Note |
|---|---|---|---|
| Arkansas | **PASS** | yes | Cloudflare-blocked listing; needs headless Chromium |
| Delaware | **PASS** | yes | listing is a JSON console on a different domain |
| North Carolina | **PASS** | yes | SharePoint anonymous REST |
| Ohio | **PASS** | yes | ePlus DigitalPaper; form posts to a different endpoint |
| South Dakota | **PASS** | yes | listing app is a different host |
| Texas | **PASS** | yes | anonymous FTP tree behind a JS licence click-through |
| Vermont | **PASS** | yes | proposals public, only plan sheets need the iCX login |
| Washington | **PASS** | yes | anonymous IIS contract directory |
| Florida | FAIL | yes — but no specifications | spec package is behind CPP account |
| Hawaii | FAIL | yes — but wrong document class | listed URL is bid *results* |
| Oklahoma | FAIL | **no** | documents moved to Bid Express (bidx.com) |

8 of 11 verified. The three failures are portal facts, not adapter defects.

---

## The calibration finding (raised before the checker was widened)

The original checker required CSI MasterFormat structure. Highway lettings do
not use it. Every one of the eight now-passing adapters was first recorded as a
FAIL against real, complete, free specification documents. The clearest single
example:

**`https://media.ark.org/ardot/030531_1-proposal.pdf`** — 9,548,635 bytes, 209
pages, opens:

> ARKANSAS STATE HIGHWAY COMMISSION / PROPOSAL DOCUMENTS / FOR THE CONSTRUCTION
> OF / STATE JOB NO. 030531 / FEDERAL AID PROJECT PRTT-0041(46) / RED RIVER –
> OGDEN (S)

Nowhere in those 209 pages is there a MasterFormat section number, a
`PART 1 - GENERAL` heading, or an arabic `DIVISION n` heading. It is written
against the ARDOT Standard Specifications for Highway Construction.

Second example, **`https://apps.sd.gov/HC65C2C/EBS/lettings/specprov/09ML_SpecProv.pdf`**
— 12,764,699 bytes, 100 pages:

> DEPARTMENT OF TRANSPORTATION / NOTICE TO CONTRACTORS, PROPOSAL, SPECIAL
> PROVISIONS, CONTRACT AND CONTRACT BOND / FOR / STRUCTURE (3-11'X7' CIP RCBC) &
> APPROACH GRADING / FEDERAL PROJECT NO. BRO-B 8055(37) (PCN 09ML)

…containing, on a later page:

> SPECIAL PROVISION FOR INDIAN EMPLOYMENT AND CONTRACTING / SISSETON-WAHPETON
> OYATE / PURPOSE / The purpose of the Indian Employment and Contracting Special
> Provision is to establish the specifications for Indian preference…

Zero MasterFormat evidence in the whole file.

The checker now accepts a numbered highway spec section co-occurring with the
measurement/payment skeleton, which recognises both of these. That change turned
six recorded failures into passes with no adapter logic change beyond ranking.

### Residual page-window caveat

The checker reads the first 25 pages. Highway proposals open with the contract
cover, bond forms and the itemised bid schedule, and the technical provisions
start later. Measured:

* NCDOT `GUILFORD_U-4758_C204971.pdf` (402 pp) — first `DIVISION` heading on
  page 56.
* SDDOT `09ML_SpecProv.pdf` (100 pp) — section + skeleton first co-occur in the
  page 50–75 window.
* ODOT proposals (99–148 pp) — section + skeleton first co-occur in the page
  25–50 window.

Those three still pass, because other signals land early enough or another
sampled document does. But a portal can be one page-count away from a false
negative. If a DOT adapter fails with "downloaded N PDFs, none with…", check the
page window before concluding the portal is thin.

---

## Per-state detail

### Arkansas — PASS
`ardot.gov` sits behind Cloudflare bot management. Every plain fetch of the
listing returns **403 from nginx** — urllib and curl, with and without a browser
User-Agent, Referer, or `sec-fetch-*` headers. `robots.txt` on the same host
returns 200, so it is a TLS/JA3 fingerprint check, not a header check and not an
IP ban. Headless Chromium gets 200 and 329,015 bytes.

Two sub-traps:
* Passing `user_agent=` to `browser.new_page()` re-triggers the 403 (200 /
  329,015 bytes → 403 / 144 bytes). The pinned UA string disagrees with the
  client hints Chromium actually sends. Let Chromium be itself.
* The documents are on a **different host**, `media.ark.org`, which is not
  protected — `fetch()` works with plain urllib. "The host is blocked, the source
  is dead" would have thrown away a passing source.

### Delaware — PASS
`deldot.gov/Business/bids/` (the spreadsheet URL) is a landing page holding a bid
bond form and a bidders list, and **no advertised contracts**. The contracts are
on the statewide console `mmp.delaware.gov/Bids`, a jqGrid backed by two POST
endpoints named in `/js/bidsConsole.js`:

```
POST /Bids/GetBids?status=Open          -> JSON rows (AgencyCode == "DOT")
POST /Bids/GetBidDocumentList?id=<id>   -> HTML fragment of document links
```

A GET on either returns the SPA shell at HTTP 200 — a soft 404. A POST with an
empty body returns an HTML error page. The jqGrid paging parameters are
required. Documents live on `gssdocs.deldot.delaware.gov`, which needs the
browser UA + Referer.

### North Carolina — PASS
`connect.ncdot.gov/letting/Pages/default.aspx` is a landing page; the Division
letting table is rendered in JavaScript, so a plain fetch sees 82,354 bytes and
zero document links — a silent zero. The site is SharePoint and its **anonymous
REST endpoint answers**:

```
/letting/_api/web/GetFolderByServerRelativeUrl('/letting/Central Letting')/Folders
/letting/_api/web/GetFolderByServerRelativeUrl('<letting folder>')/Files
```

`Accept: application/json;odata=nometadata` is required; with the default Accept
the same URL returns XML that a JSON parse reads as "no documents".

### Ohio — PASS
The spreadsheet URL is a SharePoint page with exactly one PDF (the prebid
questions log) and a "Sign In" link — it reads as gated. The documents are on the
ePlus DigitalPaper host `contracts.dot.state.oh.us`, free and anonymous.

The trap: the search form's submit handler calls `submitAction(this.form)` with
no action argument, so the form's own POST target is **not** the search endpoint.
Posting to `documentSearchCriteria.do` returns the criteria page again at HTTP
200 — a silent zero that reads as "no results". The real endpoint is
`/document/documentSearch.do`, and the session cookie from the criteria page must
be carried (a cookie jar; the `jsessionid` path segment alone is not enough).
Download is `/document/downloadDocument.do?documentId=…&cabinetId=…`, no cart.

Unfiltered search returns 2002 lettings first, so the adapter wildcards recent
project-number year prefixes.

### South Dakota — PASS
`dot.sd.gov/doing-business/contractors/bid-letting-information/` is a landing
page: zero PDFs, 284 navigation links. One link, "Bid Letting →", goes to the
letting application on `apps.sd.gov/HC65BidLetting/`. From there
`ebslettings1.aspx` lists advertised letting dates and
`ebslettingsdetail1.aspx?args=…` lists each project's Special Provisions
(`specprov/<PCN>_SpecProv.pdf`) and electronic plans.

### Texas — PASS
`txdot.gov/business/plans-online-bid-lettings.html` is a landing page with zero
PDFs. It links a licence-agreement page whose "I Agree" button is a plain
JavaScript redirect to `/business/plansonline/ftpinfo.htm`, which holds the FTP
root in an `onClick`. `https://ftp.txdot.gov/plans/` serves anonymously over
HTTPS; the credentials embedded in one of that page's handlers are not required
and are not used.

Ranking trap: a month folder lists subdirectories alphabetically, which puts
`08 Proposal Addenda` **ahead of** `08 Proposals`. Walking in listing order fills
all six document slots with 2–14 page addendum cover letters while the 83–271
page proposals sit one folder later, untouched. That alone was the difference
between FAIL and PASS.

### Vermont — PASS
`vtrans.vermont.gov/contract-admin/bids-requests` is a landing page. Its
Design-Bid-Build sub-page says in bold *"DBB Plans must be downloaded by logging
in to the iCX Web System"*, which reads as a hard login wall and would justify
recording Vermont as Tier 3. It is not. Further down the same page an `<iframe>`
embeds `vtrans.exevision.com/icxpublic/BidOpportunityContainer.aspx`, which
embeds `BidOpportunities.aspx`, which serves each contract's PROPOSAL anonymously
via `DocumentHandler.ashx`. Only the plan sheets need the login.

### Washington — PASS
The contract detail pages under `wsdot.wa.gov` carry only a bid tabulation and a
link reading "order plans and specifications". The documents are one host away,
in an anonymous IIS directory listing linked as "Active Contracts Directory":
`https://ftp.wsdot.wa.gov/contracts/<CONTRACT>/Plans&Specifications/` — 392
contract folders, no authentication.

Second trap: that IIS listing emits `<A HREF=…>` in **uppercase**. A
case-sensitive href regex returns 0 links against a 60,091-byte body.

This is also the only DOT portal in the batch that serves true MasterFormat: the
Tumwater RHQ Building Demolition project manual opens `00 01 00 TABLE OF
CONTENTS / DIVISION 00 BIDDING AND CONTRACT REQUIREMENTS`. It is a *building*
demolition let by a DOT — which is exactly why the vertical/highway distinction
is about the document, not the agency.

### Florida — FAIL (documents reachable, none are specifications)
The letting page carries 333 real PDFs on `ftp.fdot.gov`, in four classes:

| pattern | what it is |
|---|---|
| `T####BSN.pdf` | Bid Solicitation Notice + approximate quantities, 2–7 pp |
| `T####Addendum###.pdf` | addendum cover + plan-revision table, 1–8 pp |
| `T####-Bid-Tab.pdf` | bid tabulation, post-award |
| `CO-MM-DD-YYBSN-n.pdf` | letting-wide advertisement |

Six addenda were scanned in **full**, not just the first 25 pages: none contains
a numbered highway spec section, and none contains BASIS OF PAYMENT / METHOD OF
MEASUREMENT / CONSTRUCTION REQUIREMENTS. The absence is real, not a numbering
mismatch. The project Specifications Package and plans are ordered through the
CPP Online Ordering System (`fdotwp1.dot.state.fl.us`), which needs an account —
so no account was created.

Recorded false positive: `T7599Addendum001.pdf` matched the old CSI section regex
on `447935-1-52-01 1 07/20/26`, a plan-revision row where a sheet number and a
date extract as "1 07 20". Seven pages, no specification prose. The hardened
checker no longer counts it; `_rank()` keeps the BSN first regardless.

### Hawaii — FAIL (spreadsheet row is mislabelled)
`hidot.hawaii.gov/administration/con/current-bid-openings/` is a bid **results**
page. Its own parent page titles the link "Current Bid Results" and lists
siblings "Prior Bid Results – FY2022/FY2021/FY2020". The PDFs are tabulations:
`RH1016-22.pdf` is 12,635 bytes and reads "PROJECT NO.: RH1016-22 / BID OPENING:
2:00 P.M., JULY 21, 2022 / BIDDER BID AMOUNT".

**Open lead.** Real Hawaii DOT specification books are anonymously downloadable
from HIePRO, verified by download:

> `https://hiepro.ehawaii.gov/resources/173899/Specifications-FINAL SPECIFICATIONS w NTB HWY C 32 25.pdf`
> 8,837,082 bytes — "STATE OF HAWAII DEPARTMENT OF TRANSPORTATION HIGHWAYS …
> SPECIAL PROVISIONS, SPECIFICATIONS, PROPOSAL AND CONTRACT … PROJECT NO.
> HWY-C-32-25"

There is no anonymous **listing** to discover them from. `hiepro.ehawaii.gov`
exposes only a vendor search publicly; the aggregator `hands.ehawaii.gov` is an
Angular SPA whose opportunities API lives in a lazy-loaded chunk, and whose
obvious REST paths (`/hands/api/opportunities`, `/hands/rest/opportunities`)
return the SPA shell at HTTP 200 — soft 404s, not data. Recorded as a lead rather
than guessed at. Worth an hour: the documents themselves are ungated.

### Oklahoma — FAIL (no documents on the portal at all)
Checked the whole bid-opening tree, not just the landing page:

| page | links | PDFs |
|---|---|---|
| `contracts-and-proposals.html` | 281 | 0 |
| `future-bid-openings/oct-15-2026.html` | — | 0 |
| `past-bid-openings/2026/jun-18-2026.html` | — | 0 |
| `past-bid-openings/2025/oct-16-2025.html` | — | 0 |
| `past-bid-openings/2023/jun-15-2023.html` | — | 0 |

Not hidden behind JavaScript — absent. The only external links on a letting page
are two Vimeo showcases. `previous-bid-openings.html` still names "Advertised
Plans", "Sample Proposals", "Pre-Bid Letters" and "Addenda" as plain text and
links out to `https://www.bidx.com/`. Oklahoma DOT letting documents are
distributed through Bid Express, which is out of scope for this batch.

---

## Reusable lessons

1. **Nine of eleven spreadsheet URLs were landing pages.** The Missouri trap is
   the norm for DOT, not the exception. If `discover()` returns few links, the
   documents are usually on a different host entirely — an FTP tree, an IIS
   directory, a JSON console, or a vendor SaaS in an iframe.
2. **A stated login wall may cover only part of the document set.** Vermont says
   plans need a login; the proposal does not.
3. **Subdirectory listing order is a ranking hazard.** Alphabetical order put
   Texas's addenda ahead of its proposals and cost a PASS.
4. **Playwright is the right tool when the block is on the client fingerprint.**
   Arkansas 403s every plain fetch and 200s in headless Chromium — but only if
   the UA is left alone.
5. **A checker rule can be the bug.** Six of these portals were correct all
   along and read as failures.
