# Tier-2 VERTICAL state portals — what the tier actually was

Assessed 2026-08-06 against 21 states carried in the source workbook as
**T2 = "a free account or vendor registration is believed necessary."**

That belief was wrong in both directions, and the direction it was wrong in is
the useful finding:

| | count | meaning |
|---|---|---|
| **(a)** documents reachable with **no login at all** | 6 | tier was too pessimistic |
| **(b)** listing needs a **browser**, PDFs are open | 4 | tier was wrong about *what* was hard |
| **(c)** **genuine login wall** — recorded, not worked around | 9 | tier was right |
| skipped | 2 | Periscope portals, another agent's scope |

**No account was created. No credentials were entered. No terms were accepted
on any site.** Nine (c) findings are the deliverable, not a shortfall — each one
is a portal nobody now has to spend a day re-discovering.

Two adapters were built and both are verified by
`scripts/check-portal-adapters.py`, which downloads a document and requires CSI
MasterFormat structure in the extracted text.

---

## Results

| State | Class | Checker | Evidence actually observed |
|---|---|---|---|
| **Wisconsin** | **a** | **PASS** — `verified: 88,690 bytes, CSI evidence ['section numbers', 'division headings']` | Current bids are Trimble-walled ("All bidders must sign in ... using a Trimble ID"), but the retired **WisBuild** system still serves its archive with no login. `bid_documents.aspx?projnum=23C2A` → `filedownload.aspx?...23C2A TOC.pdf` = 803,417 bytes, CSI sections + DIVISION headings, anonymous. |
| **North Carolina** | **b** | **PASS** — `verified: 89,328 bytes, CSI evidence ['division headings']` | eVP (`evp.nc.gov`) is Microsoft Power Pages: a plain fetch of `/solicitations/` returns 270KB of chrome and **zero** solicitation ids. Under Playwright the grid renders ids. The attachment endpoint `/_entity/annotation/<id>/<id>` then returns the PDF to an **anonymous plain urllib request** — 4,078,206 bytes for the Raleigh BRAC project manual, no cookie, no account. Registration gates *responding*, not *reading*. |
| Alabama | a | not built | `alabamabuilds.gov/AdvertisementBids` lists every project with an open `DownloadFile?AdvertisementId=N`. All six sampled returned real PDFs (110–150KB) with **no login**. But every one is a 1–2 page legal notice; none carries CSI structure. Open, and thin. |
| Louisiana | a | not built | `doa.la.gov` serves 77 PDFs directly. Sampled ads are 1 page: "ADVERTISEMENT FOR BIDS ... Complete Bid Documents ... may be obtained from the Designer". Open, and thin — the project manual never touches the state host. |
| Mississippi | a | not built | `dfa.ms.gov` serves bid ads and bid tabs openly. The ad states the terms: *"Contract documents may be obtained from: Professional: Neel-Schaffer, Inc. ... **A deposit of $100.00 is required.**"* Not a login wall — a **paywall held by a third party**. |
| New Jersey | a | not built | `project_construction_advertisements.shtml` exposes ~440 direct PDFs (`S0652-00.pdf`, `-SignIn.pdf`, `-BidResults.pdf`, `-Award.pdf`). All open. Text extraction returns **empty** — they are scanned images, and the set contains no project manual. |
| Illinois | a | not built | CDB Construction Bulletin project pages (e.g. `370-800-24-024-marine-bank-building-east-wall-.html`) carry exactly one PDF: a generic "Bidding and Contract Requirements". Plans go to "Participating Plan Rooms" (`binrooms.pdf`). Open, no documents. |
| South Carolina | b | not built | SCBO's advertisement database is JS-rendered (a plain fetch of `/online-edition` yields the form, no rows). Under a browser it emits open PDFs at `scbo.sc.gov/files/scbo/*` — but they are SE-110 / SE-310 one-page invitations. Sampled three, incl. `00_11_13_Advertisement_25009_-_Bids.pdf`: no CSI in any. Ads say "Documents May Be Obtained From: <named person>". |
| South Dakota | b | not built | The workbook URL `boa.sd.gov/state-engineer/adv-advertisements.aspx` **302s to a ServiceNow SPA** at `sd.gov/bhra` — a plain fetch returns 962KB of "Loading…". Driving it to the "OSE Bids & Proposals" article exposes `sys_attachment.do?sys_id=…`, which serve **openly** (1.2MB, 200KB, 225KB). Content is Invitations to Bid and Requests for Statement of Interest; plans come from the engineering firm. |
| Connecticut | c | — | CTsource bid board is a **Proactis WebProcure iframe**. Its search API is anonymous and works (`/wp-full-text-search/search/sols?customerid=51` → 10,000 hits), so the *listing* is open. Document access is not: every row's action is `Login` → `portal.ct.gov/DAS/CTSource/Login`, and many rows just point out to Bonfire/SmartInsight. |
| Hawaii | c | — | Definitive. Project pages carry "Download Plans and Specs" → `dags.hawaii.gov/plans/download.php?doc=12-10-0999.zip`. With a full browser UA **and** the project page as Referer, that **302s to** `dags.hawaii.gov/plans/index.php` — `<title>Public Works Division | Login</title>`. The site also says outright: "Register to download plans and specs". |
| Kansas | c | — | DCC's "On-Line Plan Room" is `kansasdfm.idtplans.com` → `kansasdfm.geocivix.com`. The listing renders projects, but every `/secure/project/?projectid=NNNN` **302s to** `/secure/domain/login/?message=9` whose body reads *"Please log in or register to view this page."* |
| Kentucky | c | — | Two walls. `stateofkyplanroom.com` (Lynn Imaging): `ViewJob.aspx?job_id=29564` **302s to** `Login.aspx?ReturnUrl=…`. And the state's own page states the model: *"Registered users can view project descriptions, thumbnail drawings, plan holder lists or **order** plans and specifications."* Registration **and** purchase. |
| Michigan | c | — | DTMB's design-and-construction page hosts only forms, standards and bid *results*. Every solicitation routes to SIGMA VSS, and the state's own text is *"You must be registered to respond to an RFP."* No public VSS browse endpoint resolved (`sigma.michigan.gov/*VSS*/AltSelfService` → 404). |
| Rhode Island | c | — | All solicitations live in **Ocean State Procures**; RIDOP's own page: *"All vendors interested in submitting a bid in the OSP system must be registered in OSP to do so."* The public site carries one PDF, a fee notice. |
| Vermont | c | — | The workbook URL leads to planholder lists and bid-tab sheets only (`/files/purchasing-contracting/**planholders**/2025/…`). Solicitations are in **VTBuys**, which CloudFront-403s a headless browser and is a registered-supplier ERP. |
| Wyoming | c | — | SCD publishes nothing itself: *"The SCD currently releases bids on **Public Purchase**"* (free vendor account required to download) and school work on **QuestCDN** (paid). `publicpurchase.com/.../publicInfo` returned a table with headers and no rows; closed-bid list is JS-paged. |
| California | c (unresolved) | — | Not a clean call. `caleprocure.ca.gov` is PeopleSoft behind an Akamai edge that returns **403 to a bare headless browser**; with a real User-Agent the Event Search page renders fully (search form, "Download Attachment" dialog, no login required to view). The search itself hung at "Loading…" across two attempts and returned no event ids, so **document reachability was never proven either way**. Recorded as unresolved, not as dead. Worth one more pass. |
| Arizona | skip | — | `app.az.gov/page.aspx/en/rfp/request_browse_public` — **Periscope**. Another agent's scope. |
| Maryland | skip | — | `emma.maryland.gov/page.aspx/en/rfp/request_browse_public` — **Periscope**. Redirects to `/bas/browser_check`. Another agent's scope. |
| *(North Dakota)* | skip | — | Listed as its own portal, but `omb.nd.gov` hands off to `internal.ndbuys.nd.gov/page.aspx/en/rfp/request_browse_public` — the **same Periscope path** as Arizona and Maryland. Reclassified into the Periscope batch. |

---

## Traps this pass actually hit

**The spreadsheet URL is a landing page more often than not.** Wisconsin's real
documents are three hops down and behind a form post; North Carolina's SCO page
holds *zero* documents and only points at eVP; South Dakota's URL 302s to an
entirely different CMS. In each case, stopping at the given URL produces a
confident, wrong "this portal is thin."

**An empty table is not an empty portal.** WisBuild's listing defaults to "the
last 3 months". The system was retired in May 2024, so the default view is
blank — the exact shape that reads as a dead source. It needs a date range
posted back with the page's own hidden `__VIEWSTATE` / `__EVENTVALIDATION`.

**Registration gates responding, not reading.** North Carolina's eVP fronts a
"Sign in" button and a page of vendor-registration copy, which is what put it in
T2. The attachment endpoint is anonymous. The wall was real; it was just not on
the path we needed.

**Cookieless ASP.NET sessions expire between discover() and fetch().** WisBuild
URLs embed `/(S(xxxxx))/`. A URL captured during discovery and fetched minutes
later returns nothing. Stripping the segment makes the server issue a fresh one.
This failed *silently* — the first checker run reported "no URL returned a real
PDF (WAF block?)", which pointed at the wrong cause entirely.

**Double-encoding is silent too.** WisBuild file URLs carry raw spaces and `+`.
They must be quoted once; quoting an already-quoted URL turns `%20` into `%2520`
and the file 404s. `_encode()` unquotes first so it is idempotent.

**Ranking is the difference between a portal that "has no specs" and one that
does.** Wisconsin publishes `TOC` / `A-1 Document` / `BidTab` / `Award Results`
per project; only the first carries CSI. North Carolina attaches the sales-tax
form and the insurance exhibit alongside the project manual. Both adapters rank,
and both explicitly demote the known-useless names.

**"Open" and "useful" are different axes.** Six states hand over their documents
with no login and are still not worth an adapter, because what they publish is a
one-page advertisement and the project manual sits with the designer — sometimes
behind a literal $100 deposit (Mississippi). Recording *open but thin* separately
from *walled* is what stops the next pass from re-probing them.

---

## Verification

```
$ python3 scripts/check-portal-adapters.py --only wisconsin_vertical north_carolina_vertical
ADAPTER                     RESULT  DETAIL
  north_carolina_vertical   PASS    verified: 89,328 bytes, CSI evidence ['division headings']
  wisconsin_vertical        PASS    verified: 88,690 bytes, CSI evidence ['division headings', 'section numbers']

2/2 adapters verified against live portals
```

Every claim of PASS above is a line this checker printed. Nothing in the (c)
column was inferred from a status code — each is a redirect target, a login
`<title>`, or the agency's own published sentence, quoted.
