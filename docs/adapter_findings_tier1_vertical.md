# Tier-1 vertical portal adapters — findings

Fifteen state building/facilities construction portals were listed as Tier 1
("direct free PDF, no login"). Eight are. Seven are not, and the reasons differ
enough to matter.

Verdicts below are `scripts/check-portal-adapters.py` output, which requires a
downloaded PDF containing CSI MasterFormat structure. Nothing here is a
self-report.

## Verified — adapter written and PASSing

| State | Adapter | Proof |
|---|---|---|
| Missouri | `missouri_vertical.py` (pre-existing) | 4,574,081 B — PART 1/2/3, division headings |
| Maine | `maine_vertical.py` | 3,991,753 B — section numbers, division headings |
| Alaska | `alaska_vertical.py` | 1,094,921 B — section numbers, PART 1/2/3, divisions |
| Delaware | `delaware_vertical.py` | 10,527,410 B — PART 1/2/3, division headings |
| Iowa | `iowa_vertical.py` | 14,689,433 B — PART 1/2/3, division headings |
| Georgia | `georgia_vertical.py` | 6,127,537 B — section numbers, PART 1/2/3, divisions |
| Texas | `texas_vertical.py` | 748,429 B — section numbers |
| Florida | `florida_vertical.py` | 9,842,746 B — PART 1/2/3, division headings |

## Not viable — no adapter written

No adapter file exists for these. Writing one would add a permanent FAIL to the
checker and imply the source is one fix away from working; none of them is.

| State | Reason | Evidence |
|---|---|---|
| Arkansas | Edge block on the whole host | `sas.arkansas.gov` returns nginx **403, 548 bytes** to every path, to curl, to urllib, and to real headless Chromium (144-byte body). Not a UA problem — the host root 403s too. |
| Idaho | Documents are not online at all | `dpw.idaho.gov/construction/` publishes only `*-Ad-Long.pdf` advertisements. Each one states: *"Plans, specifications, proposal forms and other information are on file for examination at"* — then lists the AGC plan room, Blueprint Specialties and the architect's office. The specs are physical/plan-room only. Tier-1 classification is wrong for Idaho. |
| Indiana | Microsoft login | Bid documents are SharePoint links (`ingov.sharepoint.com/:b:/s/IDOADAPWBiddingDocs/...`) that 302 to `login.microsoftonline.com`. The portal's own text admits it: *"You may be instructed by SharePoint to request access… request access and a member of the team will approve your request."* An account is required; not created. |
| Minnesota | Bot wall | `mn.gov/admin/...` is behind Radware Bot Manager. Plain fetch returns a "Radware Bot Manager Captcha" page; headless Chromium is redirected to `validate.perfdrive.com` and served **hCaptcha**. Playwright does not help — this is an edge decision, not a rendering problem. |
| New Mexico | Portal holds no vertical construction | The `active-procurements` page is an iframe over `spd.gsd.state.nm.us`. All **74** open procurements are sole-source, emergency, or commodity buys; **zero** building-construction ITBs. eProNM (Jaggaer) lists **6** open events — consulting, temp staffing, backhoe, elevator maintenance, geothermal drilling. Their event PDFs download freely and contain no CSI structure. Nothing is blocked; there is nothing to take. |
| Pennsylvania | Only bid tabs are published | 113 PDFs across the DGS bidding pages: unofficial/official bid tabs, pre-bid sign-in sheets, and standard contract boilerplate. Zero project manuals. eMarketplace has 7 open IFBs; the two DGS construction ones attach a campus map and a "Low Bidder Additional Info" sheet. Plans and specs go through a separate plan-holder service. |
| Virginia | reCAPTCHA on the attachment | The Solr feed behind eVA is open — `solrconnect.jsp` returns 111 open Construction solicitations as JSON, and detail pages are reachable at `IVDetails.jsp?rfp_id_lot=<internalid>&rfp_id_round=<version>`. But the detail page renders **"Please verify reCAPTCHA to continue:"** and only reveals `#attachDownloadBtn` after a Google reCAPTCHA passes. Metadata is free; documents are not. |

## Recurring failure modes

Worth carrying into the next batch — every one of these returned a plausible
zero rather than an error.

**1. The listing URL is a landing page.** Missouri's known trap repeated in
Alaska: bare `Search.aspx` renders the search *form* and zero results, so
`discover()` returned nothing and looked like a login wall. Any `search=` value
flips it to the result list — and the term is then ignored server-side
(identical output for "construction" and "bid"). Two separate lies in one
parameter.

**2. Server-side filters that silently do nothing.** Georgia's DataTables
endpoint accepts `search[value]` and returns `recordsFiltered == recordsTotal`
for every term. Texas's ESBD list service takes no filter at all — capturing the
XHR while typing in its own search box shows the identical payload. An adapter
that "searches" these portals is really pulling the whole set while looking
targeted. Both are filtered locally instead, and the reason is in the file.

**3. Content negotiation as an access control.** Florida's attachment endpoint
returns the Angular shell — 1,132 bytes, HTTP 200 — when `Accept` admits
text/html, and the actual PDF when `Accept: application/json`. Same URL, same
status. Probing it with `Accept: */*` produced the shell; it would have been
recorded as "endpoint not found". Delaware's guessable document routes
(`/BidDocs`, `/GetBidDocuments`, `/GetDocs`) all return the SPA shell at 200 as
well. Baseline the shell, compare against it.

**4. The spec book is never the first file, and rarely says "spec".** Every
portal here needed a `_rank()`:

- Alaska sorts `00 3000 Bid Schedule.pdf` first — a bid form numbered like a CSI
  section, which is exactly the shape a naive filename filter looks for.
- Maine's `_Legal_Ad_` sorts before `_Project_Manual_` both alphabetically and
  in document order.
- Georgia is the hard case: of 28 vertical events sampled, **zero** had a file
  named `*spec*`. The CSI content was inside a 15 MB *addendum*. Ranking on the
  word "spec" returns nothing and the portal reads as empty, so the ranking there
  is negative — push notices, advertisements, plan-holder lists and award letters
  to the back, try everything else.
- Texas attaches the same four boilerplate PDFs to every posting (direct deposit
  form, tax ID application, terms and conditions, subcontracting plan). All are
  large, real PDFs with no CSI. "Take the biggest attachment" gets a tax form.

**5. Metadata is public; documents are a separate decision.** Iowa, Virginia,
Idaho and Pennsylvania all publish complete solicitation metadata while the
project manual sits behind a captcha, a private plan room, or nothing at all.
Roughly 20 of Iowa's 45 open bids say the plans are at "Beeline and Blue, Des
Moines". That is a real property of the source, not a bug to fix, and it is the
main reason a state can be listed Tier 1 and not be.

## Rate limiting

Every adapter holds `PAUSE = 1.0` between requests to one host and every
discovery loop prints `[n/total] … x/min ETA`. No portal was queried faster than
1 req/s at any point, including during probing.
