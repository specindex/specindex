# Bid Express (bidx.com, Infotech) — adapter findings

Probed live 2026-08-06. Adapter: `scripts/portal_adapters/bidexpress.py`.
No account was created and no credential was entered at any point.

---

## 1. The headline: Bid Express serves no document anonymously

The brief assumed Bid Express hosts letting documents for 30 state sources and
that a free info-only account can browse them. The first half is true. The
second half requires a signed-in account, and there is **no anonymous read path
at all**. Three independent probes agree:

| Probe | Result |
|---|---|
| `POST https://graphql.bidx.com/graphql` `{ agencies { … } }`, no cookie | **200**, 45 agencies returned (44 real + `TEST`) |
| Same endpoint, `lettings` / `proposals` / `activelinks` | **200 with `errors[0].extensions.code = FORBIDDEN`**, "You are not authorized to access this information." |
| `https://www.bidx.com/{agencydomain}/lettings` (curl, browser UA, follow redirects) | **302 → `ui.bidx.com/login?referer=…`** for every agency domain tried |
| `https://ui.bidx.com/GADOT/lettings` rendered in headless Chromium, no cookies | redirected to `/login`, sign-in form rendered |

`ui.bidx.com` is a Vue SPA whose entire data layer is that one Apollo endpoint.
Reading its bundle (`/assets/index-*.js`) shows the only auth-adjacent headers
it sends are `x-api-role`, `x-api-services` and `x-api-keep`, and the guard
around them (`isAuthorizedAgency(agencyId, "accessagencylettings")`) makes them
privilege **downgrades** on an existing session — they cannot grant access.
GraphQL introspection is disabled (`INTROSPECTION_DISABLED`).

Two queries do answer anonymously and are worth keeping: `agencies` (the
authoritative agency directory, used to build `STATES`) and
`agencySettings(agencyid:)`. Neither returns a document.

**Conclusion:** an adapter that fetches documents *from bidx* cannot exist
without an account. Every document this adapter returns comes from the
agency's own public mirror.

## 2. What the mirrors actually hold

Arizona is the one clean, fully public, machine-readable mirror found:
`cnsads.azdot.gov/current` lists every advertised project and
`/Home/Documents/{id}` returns a plain HTML table of direct S3 PDF links —
bid book, plans, cross sections, geotech — with no login, no cookie and no
Referer requirement. The adapter implements it and it works.

But **ADOT bid books contain no CSI MasterFormat structure.** All 21 currently
advertised ADOT projects were swept: bid books of 73–937 pages, and neither
the first 25 pages nor the first 200 pages carry a CSI section number, a
`PART 1/2/3` skeleton, or a `DIVISION n` heading. This is not an ADOT quirk.
State DOT specifications are organised by each state's own standard
specification numbering (ADOT Section 601, Alabama item 206A000, WSDOT
Division 1–9, Iowa Divisions 11–42), not by MasterFormat. MasterFormat is a
**vertical construction** convention. A DOT letting corpus is the wrong place
to look for it.

## 3. THE CHECKER SAYS PASS AND THE PASS IS NOT REAL — read this before believing it

`python3 scripts/check-portal-adapters.py --only bidexpress` currently prints:

```
bidexpress   PASS   verified: 1,918,925 bytes, CSI evidence ['section numbers']
```

**Do not treat that as a verified spec document.** The file is
`T040901C_Bid_Book.pdf` (a real ADOT bid book, correctly discovered and
correctly downloaded), but the only text satisfying `CSI_SECTION` in its first
25 pages is the *upside-down engineer's seal* on the cover sheet:

```
07 20
26
.A.S.U ,ANOZIRA
SMITH
DEREK
```

`"07 20 26"` — the seal date 2026-07-20, extracted in reverse because the seal
is rotated — matches `\b(0[0-9])\s\d{2}\s\d{2}\b`. There is no MasterFormat
section, no `PART 1/2/3`, no `DIVISION n` anywhere in the document.

The honest result for this adapter is **FAIL: no CSI structure in any
reachable Bid Express document.** The PASS is an artefact of the verifier's
regex and would flake away the moment ADOT re-advertises that project.

### 3b. An earlier, larger false PASS that was fixed in the adapter

The first version of the adapter returned each ADOT project's full file set.
`check-portal-adapters.py` reported:

```
bidexpress   PASS   verified: 37,067,556 bytes, CSI evidence ['section numbers']
```

That is a **false positive** and was not shipped. The 37 MB file was
`F052201C_Plans.pdf`, a plan set, and the text that satisfied `CSI_SECTION`
was:

```
FILL HEIGHT RANGE TABLE (Ft.)
3 5 8 11 15 20 25 30 40 55 70 90
```

`"20 25 30"` matches `\b(2[0-8])\s\d{2}\s\d{2}\b`. Two earlier candidates
failed the same way: an ALDOT/ADOT engineer's seal rendered upside down gave
`"07 20 26"`, and MnDOT's tentative letting schedule gave a project-number
triple. The adapter now **excludes** drawings, cross sections, geotech,
earthwork, survey, geometry and DTM files from `doc_urls` rather than merely
ranking them below the bid book.

**This is a defect in the checker, not only in the adapter.** `CSI_SECTION`
alone, over 25 pages of a drawing set or any numeric table, is not evidence of
MasterFormat. Suggested hardening (not applied — outside this task's file
scope): require `CSI_SECTION` to co-occur with `CSI_PARTS` or `CSI_DIVISION`,
or require two or more distinct section numbers with plausible division
prefixes on separate lines.

## 4. Per-state results

30 sources from `G1_bidexpress.txt`, plus the extra Bid Express agencies the
live directory revealed. "Reachable without login" means the letting/project
listing renders and its document links resolve without an account.

| State / agency | bidx agency id | Reachable without login | Spec documents found | Reason if no |
|---|---|---|---|---|
| Alabama (ALDOT) | `ALDOT` | yes (own mirror) | no | `alletting.dot.state.al.us/PLANPROP/{date}_Call_{nnn}_Proposal.pdf` downloads freely (1.6–3.4 MB, 5 verified). Content is the bid form / item schedule; no CSI structure. |
| Alaska (DOT&PF) | `ALASKA` | no | no | `dot.alaska.gov/procurement/bidding/` carries only the calendar and links plans/specs to `bidx.com/ak/lettings` → login. |
| Arizona (ADOT) | `ADOT` | **yes** | no | `cnsads.azdot.gov` fully public; 21/21 bid books swept, none carry CSI in 200 pages. **Implemented mirror.** |
| Colorado (CDOT) | `CDOT` | listing yes | no | `codot.gov/business/bidding` carries no document links; plans/specs/proposals route to Bid Express. |
| Georgia (GDOT) | `GADOT` | no | no | `ui.bidx.com/GADOT/lettings` → login. GraphQL `lettings(agencyid:"GADOT")` → FORBIDDEN. |
| Indiana (INDOT) | `INDOT` | listing yes | no | Letting page carries only forms and schedules; contract documents live in ERMS behind the letting portal. |
| Iowa (IADOT) | `IADOT` | listing yes | no | Current-lettings page is an application shell; no PDF links in the served HTML. |
| Kansas (KDOT) | `KDOT` | **no** | no | `ksdot.gov` returned **HTTP 403** to a real-browser UA + Referer. Edge block, not a 404. |
| Kentucky (KYTC) | `KYTC` | listing yes | no | No document links on the letting page. |
| Louisiana (LADOTD) | `LADOTD` | listing yes | no | 4 PDFs reachable, all administrative; documents route to `bidx.com` and the Falcon plan room. |
| Maine (MDOT) | `MDOT` | listing yes | no | 42 PDFs crawled from the bid-opportunities tree; no bid book with CSI. Two "hits" were regex false positives (environmental memo, bridge study). |
| Maryland (MDOT SHA) | `MARYLAND-DOT` | listing yes | no | No document links surfaced from the ad-schedule page. |
| Massachusetts (MassDOT) | `MASSDOT` | **no** | no | `mass.gov` returns **403** to plain fetch; rendered in Chromium it links straight to `bidx.com/ma/main` → login. |
| Massachusetts (MBTA) | `MBTA` | yes (own mirror) | **gated** | See §5 — real CSI project manuals exist on the public host, but current solicitations expose only the Notice to Bidders. |
| Michigan (MDOT) | `MIDOT` | listing yes | no | 42 PDFs crawled; all administrative. Two regex false positives. |
| Minnesota (MnDOT) | `MNDOT` | listing yes | no | E-Plan Room is QuestCDN (`qap.questcdn.com`), membership-based. The public `edocs-public` hit was the tentative letting schedule, a false positive. |
| Missouri (MoDOT) | `MODOT` | n/a | n/a | Covered by `missouri_vertical.py` for vertical work; DOT lettings are on bidx. |
| Montana (MDT) | `MDT` | listing yes | no | 15 PDFs crawled from the contracting tree; advertised-bid-packages page did not serve project documents. |
| Nebraska (NDOT) | `NDOT` | listing yes | no | 18 PDFs, all administrative; one false positive (statewide coordinated plan). |
| New Jersey (NJDOT) | `NJDOT` | listing yes | no | 3 PDFs, none project documents. |
| New Jersey Turnpike | `NJTA` | partial | no | `njta.com` current-solicitations redirects to `njta.gov`; bidding pages 404 under the new IA. Documents route to Bid Express. |
| New Mexico (NMDOT) | `NMDOT` | listing yes | no | PS&E page links to `bidx.com`; 1 PDF on a third-party file host. |
| New York (NYSDOT) | `NYSDOT` | listing yes | no | 29 PDFs crawled from bids-and-lettings; none a proposal book with CSI. |
| New York Thruway | `NYSTA` | **no** | no | `thruway.ny.gov` sits behind a Cloudflare interactive challenge; headless Chromium got the challenge page. Proposal-book URLs found via search returned **404**. |
| North Carolina (NCDOT) | `NCDOT` | not probed | — | Not in the G1 list; agency exists in the bidx directory. |
| North Dakota (NDDOT) | `NDDOT` | listing yes | no | 35 PDFs crawled; one false positive (precast needs). |
| Ohio (ODOT) | `ODOT` | not probed | — | G1 lists Ohio as *vertical* (OFCC), which is not a Bid Express agency. |
| Oklahoma (OKDOT) | `OKDOT` | not probed | — | G1 lists Oklahoma as *vertical* (OMES), not Bid Express. |
| South Carolina (SCDOT) | `SCDOT` | listing yes | no | 1 PDF (planholders list); documents route to Bid Express. |
| Tennessee (TDOT) | `TDOT` | listing yes | no | 2 PDFs, neither a project document. |
| Virginia (VDOT) | `VDOT` | **yes** | no | 252 PDFs including `cabb.virginiadot.org/upload/*.pdf`; 5 downloaded and read — all are Notices of Advertisement, no CSI. |
| Washington (WSDOT) | `WSDOT` | listing partial | no | The ad-and-award URL in circulation now 404s; the contracts tree carries no project document links. |
| West Virginia (WVDOT) | `WVDOT` | listing yes | no | 8 PDFs; two false positives (estimate cutoff calendars). |
| Wisconsin (WisDOT) | `WIDOT` | listing yes | no | 21 PDFs crawled, all administrative. |

Agencies present in the live bidx directory but absent from G1, all
login-gated the same way: `ARDOT`, `CALTRANS`, `CTDOT`, `DELDOT`, `FDOT`,
`ITD`, `MSDOT`, `NCDOT-DIVISIONS`, `NSDPW`, `ORDOT`.

## 5. MBTA — the one real CSI document, and why it is out of reach

MBTA is the only Bid Express agency doing vertical/transit-facility work, and
its public host genuinely serves MasterFormat project manuals. Downloaded and
read, no login, no cookie:

```
https://bc.mbta.com/business_center/bidding_solicitations/pdf/
  CAP%2063-16%20Specification-Contract%201%20VOL%20I%20Specs%20-Div%202-16.pdf
→ 200, 5,065,891 bytes, %PDF
→ CSI evidence: PART 1/2/3, division headings
  "CONTRACT SPECIFICATIONS for MBTA Contract No. 1 … VOLUME ONE"
```

That is exactly the document class SpecIndex wants. It is not discoverable:

- All 126 solicitation ids in `?cbid=7380..7505` were enumerated. 40 have a
  PDF link. **All 40 are Notices to Bidders**; none links a specification.
- Every current construction solicitation says: *"Contract specifications and
  drawings are available for download from an MBTA FTP site … Click here to be
  put on the Planholders list, and request a copy."* — i.e. an email request,
  not a URL.
- CMAR and Design-Build pages expose only prequalified-trade lists, outreach
  memos and RFQs.
- `/pdf/` returns 403 to a directory listing.

So the spec books are on a public path with unguessable, human-authored file
names, reachable only by search engine. The adapter's `mbta_bc` mirror is
implemented and returns real projects and real (notice) PDFs, which is the
honest state of that source.

## 6. What would actually yield CSI

Not this platform. Bid Express is horizontal-construction procurement, and its
document class is DOT bid books. The MasterFormat corpus lives with the
*vertical* agencies in the same workbook — Massachusetts DCAMM, New York OGS,
Ohio OFCC, Oklahoma OMES — none of which is a Bid Express agency. The MBTA
result is the proof of concept: the moment the agency does buildings, the
documents are MasterFormat.

Two follow-ups worth the time, in order:

1. **MBTA planholder path.** The specs are public once requested. Determine
   whether the FTP host is reachable without the request, or whether the
   request is a form rather than an email.
2. **Vertical adapters, not DOT ones.** DCAMM / OGS / OFCC / OMES are where
   the CSI documents are, and `missouri_vertical.py` already proves the shape
   works for that class.
