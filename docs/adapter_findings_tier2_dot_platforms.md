# Tier-2 DOT portals and hosted platforms — access findings

Probed 2026-08-06. Thirteen sources: seven bespoke state DOT portals (Group A)
and six that the workbook listed per-state but which are actually four hosted
platforms plus two state sites (Group B).

**No account was created, no credentials were entered, and no terms were
accepted on any site.** Where a login is genuinely required, that is recorded
as the result and the probe stopped there.

## The headline: "Tier 2" was wrong more often than it was right

Tier 2 meant "a free account is believed necessary". Of the eleven sources
carrying that label, **six turned out to need no account at all**. The label
came from what the front door looks like, and every one of these front doors
looks like a wall:

| Source | What made it look gated | What it actually was |
|---|---|---|
| Caltrans | `sys_attachment.do` 302s to an SSO host; `/api/now/attachment/…` returns 401 "User is not authenticated" | a *different*, public scoped processor serves the same file |
| UDOT | Contractor Zone shows only "Sign in"; `/advertisements/projects` returns **403 "User is not authorized to perform this action"** | that 403 is a MALFORMED-REQUEST error. Add `?section=advertisements` and a bare urllib request returns the list |
| MoDOT | plans room header offers Account/Create and ResetPwd | documents stream anonymously; the account is for plan-holder lists |
| Utah DFCM / WA DES | Bonfire detail pages return HTTP 403 "Just a moment…" | Cloudflare, not auth. The download links are literally named `downloadDocumentUnauthenticated` |
| PennDOT ECMS | a login form on the home page | the site publishes its own `SVCOMLogin?action=login&anonymous=true` guest entry |

The recurring shape is an **authorization-flavoured error returned for a
non-authorization reason**. Two of the six (UDOT's 403, Caltrans's 401) would
have been recorded as login walls by any probe that read the status line and
stopped.

## Results

Classification: **(a)** documents reachable with no login · **(b)** listing
needs a browser, PDFs open · **(c)** genuine login wall, stop.

### Group A — Tier-2 bespoke DOT portals

| State | Class | Adapter | Evidence observed |
|---|---|---|---|
| California | (a) | `california_dot.py` | `public_attachment_downloader_api/afa3e083…` → 468,806 B `%PDF-1.6`, contract 02-2K2304 special provisions. Listing via the anonymous ServiceNow `api/now/sp/page` JSON — no browser needed at run time |
| Missouri | (a) | `missouri_dot.py` | `ViewStream/22418?type=plan` → 947,598 B `%PDF-1.4`, `260821_A01_JNW0105_JNW0106_Bid_Book.pdf` |
| Utah | (a) | `utah_dot.py` | `project-files/download/dcd89098…?file_name=F-0089(640)353_Adv_Set.pdf` → 4,031,763 B `%PDF-1.7`, 213 pp |
| Pennsylvania | (a), plans only | none built | anonymous guest session reaches bid packages; `117443_1_Roadway Plan.pdf` 1,153,924 B `%PDF-1.4`. **But the anonymous path exposes drawings only** — three bid packages checked (10,605 / 110,066 / 116,965) list Roadway, Traffic Control, E&S, Structure and Cross Section plans and no proposal or special-provisions document. No specification text, so no adapter |
| Connecticut | **(c)** | none | CTsource is Proactis WebProcure (customerid 51). Search API is public; `getBidDocs.do?bidid=…` returns the 84,802-byte **WebProcure login page** |
| Rhode Island | **(c)** | none | same platform (customerid 46, 143 solicitations). `bidDocs` is `[]` in every public search record; the public SPA offers only "Go To Login" |
| Nevada | **(c)†** | none | `www.dot.nv.gov` returns **HTTP 403 "Access Denied" for every path including `/`** — to plain urllib *and* to a real headed browser. This is an edge/IP block, not a login wall and not a WAF soft-200. Browser headers do not help; the Delaware fix does not apply. Recorded as unreachable from this network |

† Nevada is not case (c) in the login sense. It is a blanket edge block.

### Group B — hosted platforms (the leverage argument)

| Platform / source | States it opens | Class | Adapter | Evidence observed |
|---|---|---|---|---|
| **Bonfire** (Euna) | Utah DFCM + Washington DES today; **any Bonfire tenant with one line in `TENANTS`** | (b) | `bonfire.py` | Public JSON list `PublicPortal/getOpenPublicOpportunitiesSectionData` → 187 open Utah opportunities, 12 WA DES. Utah project 244107 doc 10541650 `3-CS27002-27079310-Approved Specs.pdf`, 2,071,123 B `%PDF-1.5` |
| **Proactis WebProcure** | Rhode Island DOT + Connecticut DAS (one platform, both states) | **(c)** | none | see Group A rows above |
| **BidNet Direct** | Colorado OSA gateway (and ~50 state purchasing groups) | **(c)** | none | solicitation page renders `Bid Documents — Locked / Registered members only` |
| **OregonBuys** (Periscope/Euna BSO) | Oregon state + ~hundreds of Oregon public bodies | **(c)** | none | anonymous advanced search works and returns **13,719 solicitations**; clicking a solicitation number does not open a detail view without a session, so no attachment was reachable. Only the detail step was blocked — worth one more look if Oregon becomes a priority |
| Oregon DOT (eBIDS) | Oregon DOT | **(c)** | none | `ecmnet.odot.state.or.us/ebidse/` 302s to `/Account/Login`. The oregon.gov Bid & Award page carries only advertisement notices, prequalification forms and user guides — no spec books |
| Illinois DOT (WCTB) | Illinois | (a) | `illinois_dot.py` | `LBHome` → letting GUID → an **open IIS directory listing** at `apps.dot.illinois.gov/eplan/desenv/073126/`, 82 contract folders. `62T84-002.pdf` 15,285,308 B `%PDF-1.7`, cover page "Notice to Bidders, Specifications and Proposal" |

### The anonymous path was tested explicitly on every platform

Bid Express turned out to serve nothing anonymously, so the same premise was
re-tested here rather than assumed. Results:

* **Bonfire — genuinely anonymous.** The PDFs were pulled by a bare `urllib`
  request in a fresh process with **no cookie jar, no session and no prior page
  load**: `downloadDocumentUnauthenticated/10541503` → 726,566 B `%PDF-1.6`,
  `/10688095` → 2,388,588 B `%PDF-1.7`. The Cloudflare challenge sits on the
  HTML detail page only, and it is an edge challenge, not authentication.
* **BidNet — wall.** `Bid Documents · Locked · Registered members only`.
* **Proactis WebProcure (RI + CT) — wall.** `getBidDocs.do?bidid=140908`
  returns the 84,802-byte WebProcure login page.
* **OregonBuys / Periscope — wall at the detail step.** Anonymous search
  returns 13,719 solicitations; the solicitation link does not open a detail
  view without a session, so no attachment was ever reachable.
* **ODOT eBIDS — wall.** 302 to `/Account/Login`.

So Bonfire is the one platform of the four where the free-account premise was
wrong in our favour. The other three match the Bid Express pattern exactly.

### Out of scope, unchanged

**QuestCDN** (Idaho, Nevada, Wyoming) is a paid plan room charging $15–$42 per
document. Nothing was purchased and nothing was attempted.
**bidx.com / Bid Express** was not touched; MoDOT links to it and that link is
deliberately not followed.

## Adapters built

Results are against `check-portal-adapters.py` **as it stands after the
2026-08-06 hardening** (section numbers demoted to corroborating evidence; DOT
convention — `SECTION nnn` plus the measurement/payment skeleton — accepted).
Every adapter below was re-run against that version; earlier numbers are void.

| File | Checker | Note |
|---|---|---|
| `scripts/portal_adapters/bonfire.py` | **PASS** | `['PART 1/2/3', 'division headings']`, 2,305,283 B — genuine CSI |
| `scripts/portal_adapters/missouri_dot.py` | **PASS** | `['DOT spec sections + measurement/payment']`, 280,464 B |
| `scripts/portal_adapters/illinois_dot.py` | **PASS** | `['DOT spec sections + measurement/payment']`, 2,613,284 B |
| `scripts/portal_adapters/utah_dot.py` | FAIL | 25-page window artefact — see below. Portal is open and the document is a real spec book |
| `scripts/portal_adapters/california_dot.py` | FAIL | Caltrans matches neither convention — see below |

## Calibration: what specification detection does to highway documents

### The false positives — the reason not to trust `section numbers` alone

Before the hardening, **three of my four PASSes came from numeric tables, not
from specifications.** `CSI_SECTION` is
`\b(0[0-9]|1[0-4]|2[0-8]|3[0-5])\s\d{2}\s\d{2}\b` — any three whitespace-
separated two-digit groups in range. Highway documents are full of those. The
matched contexts, pulled directly:

* **California** — a lane-closure chart: `Hour 00 01 02 03 04 05 06 07 08 09 10 11 …`
* **Illinois** — an aggregate gradation table: `#4 (4.75 mm) 40 60 20 30 36 50 34 69 60 75 …`
* **Utah** — the **state route map on a plan sheet**: `15 84 80 84 15 80 70 40 189 66 65 83 23 42 30 …`

This is the same failure the Bid Express agent found in an ADOT culvert table
and an engineer's seal. The hardening is correct and these three PASSes are
gone. Illinois and Missouri now pass on the DOT skeleton instead, which is real.

### Utah — the document is a spec book; the 25-page window is the problem

`F-0089(640)353_Adv_Set.pdf` (213 pp) satisfies the DOT criteria **on the full
text** — `csi_evidence` returns `['DOT spec sections + measurement/payment']` —
but the first skeleton hit is on **page 55**, and `pdf_text()` reads 25. Pages
1–50 are uniform federal-aid boilerplate (EEO, DBE, wage rates, Title VI).
Checked all seven advertised projects: not one Adv_Set shows the skeleton
inside 25 pages, so this is structural to UDOT, not a bad pick.

The content is unambiguous — UDOT uses **CSI MasterFormat 1995**, five digits
unspaced:

> `SECTION 00221S … BIDDING CONTRACT TIME … Add Section 00221: PART 1 GENERAL …
> 1.1 SECTION INCLUDES`
> — `F-0089(640)353_Adv_Set.pdf` p. ~45, from
> `https://contractorzone.udot.utah.gov/project-files/download/dcd89098-c16d-4ffe-9331-a89b9ecff88a/project-files?file_name=F-0089%28640%29353_Adv_Set.pdf`

Sections 00221, 00555, 01284, 01355, 01455, 01458, 01554, 01556, 01557 and
01893 all appear in that one book. `CSI_SECTION` only matches the spaced
six-digit form (`01 55 40`), so the unspaced 1995 form is invisible to it.

**Two candidate checker changes, neither made here** (the checker is not mine
to edit): raise `pdf_text` to ~80 pages for DOT adapters, or add an unspaced
five-digit `SECTION \d{5}` alternative to `DOT_SECTION`. Either would turn this
FAIL into a truthful PASS. Do not "fix" the adapter instead — there is nothing
wrong with it.

### California — genuinely neither convention

Caltrans bid books are written against the Caltrans Standard Specifications,
numbered `7-1.02K(3)`, `12-4.02`, `14-11.14`. Full-text scan of contract
02-2K2304's special provisions (37 pp): no CSI section numbers, no DIVISION
headings, no PART 1/2/3, **and** no `SECTION nnn` heading and none of the
measurement/payment skeleton phrases either.

> "See sections 1-1.06, 1-1.07B, 2-1.23, 2-1.24, 2-1.33B(3), 5-1.13D, and
> 5-1.13F …", "See section 14-11.14 for changes to the management of treated
> wood waste."
> — `https://ppmoe.dot.ca.gov/cc?id=cc_advertisement_details&ad_id=02-2K2304`,
> attachment `02-2K2304sp.pdf`

This is real specification text in a third numbering system that neither the
vertical nor the highway rule describes. Reported, not worked around: the
adapter is left in place and honest about it. If Caltrans is wanted in the
corpus, the checker needs a Caltrans-convention arm (`\b\d{1,2}-\d{1,2}\.\d{2}\b`
plus a payment-clause phrase); do not loosen the existing arms to get there.

## Notes for whoever runs these next

* `bonfire.py` launches **headed** Chrome. Headless Chromium and headless
  `channel=chrome` both stall on the Cloudflare interstitial; headed Chrome
  clears it, and the clearance cookie then carries across every subsequent
  detail page in the same context. Downloads themselves never need the browser.
* Every adapter rate-limits at 1.0 s per request and prints `[n/total] … x/min
  ETA`.
* `illinois_dot.py` walks the eplan directory listing rather than the per-contract
  WCTB pages: 83 requests for 82 contracts instead of 165.
* One IDOT fetch (62T84, 15 MB) returned empty once and succeeded on retry —
  large files on `apps.dot.illinois.gov` are worth a retry, not a "dead source"
  conclusion.
