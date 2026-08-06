# SpecIndex Strategy

> **Mirrored from Google Docs `1gXJwIgxKJArdLKTQsiyUNUD0tqZafOkbLpFGUEJCLU8` /
> `1wyKOBTcRXvps31iCdE1RNUyPUZsS3qJxV3hkHFtgcUk` on 2026-08-05.** The Doc
> remains the editable original; this copy exists so the strategy is
> **versioned alongside the code that implements it**.
>
> Why that matters: the two had already drifted. Part 4 below still lists
> "VA PG-18-1 masters — free .docx, predictable URLs" as a live source. The VA
> TIL moved behind an Okta login and those paths now 404; the masters were
> recovered via `wbdg.org/FFC/VA/VAASC/` (see `AGENT_STRATEGY.md` Part 3). A
> strategy the agents cannot read is one they cannot follow, and a document
> outside git drifts without leaving a trace.
>
> **When this file and `AGENT_STRATEGY.md` disagree: this decides WHETHER a
> thing is worth doing, that decides HOW.** Re-mirror after any Doc edit.

Prepared 2026-08-05 for Asif Hussain. Consolidates the Procore deep dive, the
ConstructConnect teardown, and research passes on the spec-intelligence
incumbents, the rep channel, and contech funding comps.

**Every factual claim carries a source. Anything marked UNVERIFIED is a lead,
not a fact, and must not go into a deck or an application.**

---

## The one-page version

SpecIndex today is a project-lead product — the same category as ConstructConnect
Insight, Dodge One and Building Radar, and the category where every customer
complaint in this research lives. Insight rates 3.1/10 on TrustRadius. A
salesperson at Hubbell, exactly the target buyer, rated it 1/10. A G2 reviewer
wrote *"much of the info can be found publicly online"* — the SpecIndex thesis
stated by a competitor's customer on the competitor's review page.

**Leads are a feature. The business is spec position.**

Every commercial specification names a basis of design, lists acceptable
alternates, then sets a substitution deadline. Being basis of design and being a
listed alternate are the same brand name in the same document and completely
different commercial outcomes. One filed rep agreement pays 25% of commission for
finding the opportunity, **50% for writing and securing the specification**, and
25% for closing. The channel already prices this step at half the deal.

**Nobody sells it.** Dodge SpecShare, ConstructConnect Insight Analyze and RIB
SpecLive Impact all report that a brand *appears* in a spec; none documents
reporting **which position** it holds. That is the wedge.

**The moat is the second half.** Approved and rejected substitutions are ruled on
in addenda posted to public bid portals, naming winners and losers with dates.
Nobody indexes them, and they come down after award — so an eighteen-month
archive cannot be reconstructed by anyone starting later.

Sell to independent rep agencies first, priced by territory with unlimited seats,
free to search. Manufacturer brand licences follow the agencies.

---

# Part 1 — The strategy change

| | Today | Proposed |
| :- | :- | :- |
| What is sold | Projects, earlier | Spec position, cited |
| The unit question | "Which projects should I chase?" | "Am I basis of design, an alternate, or absent — and who is trying to displace me?" |
| Pricing unit | ~$149/seat/month (illustrative) | Territory, unlimited seats |
| Buyer | Manufacturer marketing | Rep agency and regional sales manager first; manufacturer VP Sales second |
| Delivery | Search and dashboard | Email digest and API first, dashboard last |
| Free tier | Beta, free for now | Free forever, public, indexable — the growth engine |
| Moat claim | Coverage and extraction accuracy | The addenda ledger and the citation graph |

**Why the lead framing loses.** The Construction Marketing Association notes that
vendor selection here is "more brand oriented than service oriented" because
database quality is "nearly impossible to determine from an outside perspective."
Where quality is unverifiable, the incumbent brand wins by default. A cited
product breaks that.

**Volume is a losing frame.** ConstructConnect claims 825,000 active projects;
Dodge claims 700,000/year and 10M+ historical. Leading with 500K+ invites the one
comparison SpecIndex loses. (Worth knowing quietly: ConstructConnect's own pages
simultaneously claim 825,000 and 1.4M, so their figures are marketing rounding.)

---

# Part 2 — The wedge

In Division 23 (mechanical) and Division 26 (electrical) schedules, the engineer
names a **basis of design** manufacturer and model, sizes the schedule around it,
lists acceptable alternates, then adds an "or equal" clause governed by Division
01 Section 01 25 00. Three states exist for any manufacturer on any project:

1. **Basis of design** — the schedule is built around your product.
2. **Listed alternate** — you are eligible, and you are a price check.
3. **Absent** — you need a substitution request, and there is a deadline.

The difference between 1 and 2 is the difference between a won job and a quote
nobody returns.

**Evidence nobody sells this** (checked 2026-08-05 across product pages,
brochures, help docs, press and the public review corpus):

| Product | What it says it detects | Position reporting |
| :- | :- | :- |
| Dodge SpecShare | "Alerts when you or your competitor's products are specified" | Not documented anywhere public |
| ConstructConnect Insight Analyze | "Track competitor specification rates and market share", 1,400+ MasterFormat codes | Not documented anywhere public |
| RIB SpecLive Impact | "Tracks where, when, and how they're specified" | Not documented anywhere public |

All three describe brand-name detection inside spec text. A basis-of-design clause
and an alternate list both contain the brand as a text match; separating them
requires parsing the *procedural language around* the clause. None describes doing
that.

**State it as** "not evidenced in the public record for any of the three leading
products" — never "proven absent."

**Why it is worth money.** A filed rep agreement (EvoLucia, via EDGAR/Justia)
pays 25% / **50% for securing the specification** / 25%. Spec protection runs
18–24 months, so a spec won in 2026 is protected commission into 2028. And there
is **no public benchmark** for what a spec win is worth — the first defensible
number is simultaneously a product, a research asset and a PR asset.

**The registry gap.** NEMRA's model contracts contain no spec-registration
clause. Every manufacturer runs its own agent-only form with no published proof
requirements or dispute policy. Ingen's own OASIS documentation states: *"There
exists no magic method to ensure the agency receives proper credit for an out of
territory job."* There is no neutral arbiter. A cited, timestamped, public record
with a permanent project ID is exactly the missing artifact.

---

# Part 3 — The product

**Layer 1 — the public project record (free).** Permanent, indexable, no signup.
Every project gets a permanent SpecIndex ID, the structured record, spec position
per CSI division, and a source list where every fact links to a page in a public
document with a retrieval date. This is the ARCAT move (2M+ annual visits, free,
ungated). Dodge, ConstructConnect, Building Radar and RIB gate everything behind
a sales conversation — which is precisely why none will follow.

- **The ID ships now**, not "long term." A registry is canonical only if the
  identifier exists before anyone needs it.
- **Every fact carries its source inline.** Make "click through to the source"
  the signature interaction; an uncited competitor then looks evasive.

**Layer 2 — specification position (paid).** Per CSI division, per project: basis
of design, listed alternate, or absent, with page-level citation into the project
manual, plus the substitution clause and its deadline. Ship Div 26 and Div 23 on
public projects first. **Say explicitly which projects have a parsed manual and
which are permit-only** — overclaiming coverage is the fastest way to become the
product the reviews complain about.

**Layer 3 — the addenda and substitution ledger (paid, and the moat).** Every
approved and rejected ruling, extracted from addenda and pre-bid Q&A logs, naming
the requester, the ruling and who was displaced, with a date and page citation.
The only public artifact showing **competitive displacement**. **Start crawling
before building anything else — every week not crawling is data permanently
lost.**

**Layer 4 — delivery (paid).** Weekly territory digest by email, an API, a CRM
push. **Email and API first, dashboard last**, for two reasons:

- *Commercial:* reps live in an inbox, a quoting tool and a CRM.
- *Legal:* ConstructConnect's issued patent family (US 9,116,895 · 9,529,868 ·
  9,946,715 · 9,785,638 · 9,633,012 · 10,540,401) reads on faceted-search chart
  dashboards over CSI-formatted specifications. **US 2020/0159985 A1 — the branch
  covering AI extraction of manufacturer names — was ABANDONED**, so the
  extraction is unclaimed and the exposure is entirely in the UI.

Rules that follow: lead with alerts, digests and API · if a dashboard ships, use a
filter sidebar or read-only charts, never cross-filtering · **never render a
permit job-cost histogram** (9,633,012 claims it and does not require
interactivity) · keep US 2020/0159985 A1 in a defensive file.

*Claim-scope reading, not legal advice. Get an FTO opinion before GA. UNVERIFIED:
maintenance-fee status on 9,946,715, grace period closed April 2026.*

**Where free stops.** Free gives you the world's view of a project; paid gives you
your own position and the history of who attacked it. Free must be genuinely good
— not a trial, not a record cap. It is also an **incumbent trap**: ConstructConnect
cannot make search free without cannibalising $199/market/month contracts, and
Dodge cannot fund a free tier at CCC+ with a PIK second lien due 2029.

---

# Part 4 — The moat

Five layers by durability. **Only the first two are genuinely uncopyable.**

1. **The addenda and substitution ledger.** Public, named, dated, removed after
   award. Time-sensitive in a way nothing else is.
2. **The citation graph.** Every assertion links to a page with a retrieval date.
   Incumbents structurally cannot match it: their corpus is partly
   customer-uploaded under agreements that do not permit redistribution, partly
   researcher phone calls with no artifact behind them.
3. **The specifier graph.** Which architects and MEP engineers name which brands.
   Contested rather than empty — the differentiation is access: free, self-serve,
   cited.
4. **Legally clean corpora nobody indexes systematically:**

| Source | Access | Div 23 / 26 |
| :- | :- | :- |
| SAM.gov Opportunities API `resourceLinks` | Free API key | Full federal project manuals |
| UFGS via WBDG | Free, no login | Full Divisions 21–28, quarterly |
| VA PG-18-1 masters | ⚠️ **now Okta-gated** — use `wbdg.org/FFC/VA/VAASC/` | Full master library |
| Public university / state agency design standards | Free, permanent URLs | Full, MasterFormat-numbered |
| ~50 state + thousands of local e-procurement portals | Mostly free registration | Full manuals **plus addenda** |

   **The fourth row is the underrated one** — every large public university system,
   state facilities agency and K-12 authority publishes a MasterFormat-organised
   standards library at permanent URLs, and nobody harvests it systematically.

5. **Free as an incumbent trap** — a moat because of the incumbents' balance
   sheets, not the product.

**What is NOT the moat: parsing quality.** Parspec, Autodesk Pype AutoSpecs and
Procore Datagrid all parse spec documents — handed to them by a customer, inside
one project. **SpecIndex assembles the universe from public records.** Say it that
way.

---

# Part 5 — Go to market

**Sell to rep agencies first**, not manufacturer HQ: they are organised by
territory (the pricing unit); they buy fast; they physically chase the project
(80%+ of lighting reps say spec business is their primary business); their
compensation rests on provable spec attribution with no system of record; and
manufacturer deals follow the agencies.

| | Figure |
| :- | :- |
| NEMRA member agencies | 500+, ~250 manufacturers |
| NEMRA Lighting Division | Formed Nov 2024; growing 15–20 members/month |
| **NEMRA27** | **Feb 1–4 2027, Hilton Anatole, Dallas** — densest room of the target buyer in the calendar |
| Lighting rep commission | 11.4%–13.3% blended |
| Line-card churn | 85% review annually; 87% drop non-performers |

**There is no national trade association for HVAC/mechanical rep agencies** —
lighting and electrical is the cleaner beachhead.

**Integration path.** Reps run Repfabric, OASIS (Ingen) and Repbox. **None ingests
any external project or spec database.** OASIS runs a formal "Certified
Integration" program — an institutional door, not a cold email. Price as a
per-account feed with revenue share, not a seat.

**Who pays.** Manufacturers already issue CRM licences to reps at ~$1,500/
salesperson/year. Absent better data, the buyer to name is the **VP of Sales**,
not the CMO — the sales budget is larger and less discretionary, and the output is
a sales artifact.

**First 90 days.** Days 1–30: prove the wedge on 20 public Div 23/26 projects with
page-level citations, pull their addenda, take the sample to five rep agencies.
Days 31–60: automate SAM.gov / VA TIL / UFGS / the ten largest standards
libraries; ship basis-of-design extraction as alert and API; **start the addenda
crawler**; resolve the MasterFormat licence. Days 61–90: approach Ingen and
Repfabric; publish the first credible benchmark on the value of a spec win; book
NEMRA27.

---

# Part 6 — Pricing

| SKU | Price | Unit |
| :- | :- | :- |
| Public Index | $0 | Unlimited search, every page public and cited |
| Territory Starter | $2,490/yr | One metro, alerts and digest only |
| Territory | $4,990/yr | Per state or top-50 metro |
| Region | $24,990/yr | Per Census region, up to 12 states |
| Brand | $45,000/yr | One brand, one CSI division, all 50 states |
| Brand Enterprise | $120,000/yr+ | Multi-brand, specifier graph, back-file, API |

All tiers **unlimited seats**.

- **Never price by seat.** Half the people who need access work for the
  manufacturer, not the agency signing the invoice. Procore's S-1: *"we do not
  charge a per-seat or per-user fee."*
- **Respect the channel's ceiling.** An eight-person agency's entire software
  spend is ~$6–10K/yr.
- **Publish the price and cap the renewal.** ConstructConnect carries 64 BBB
  complaints in three years, 21 on billing, with documented renewal increases of
  50%, 100% and 300%. A published 5% cap costs nothing and is the loudest thing
  to say to anyone who has been repriced.

---

# Part 7 — Market size

| | |
| :- | :- |
| TAM | $209M |
| SAM (lighting + HVAC) | $46.7M |
| Year 3 ARR, base case | $3.62M (7.8% of SAM) |

Two independent cross-checks land within 21%. **State the uncomfortable part
plainly:** Dodge + ConstructConnect is ~$195M across all buyers; if manufacturers
are 30%, current spend is ~$59M, so a $209M TAM assumes the category roughly
triples. The reason it can is **attribution** — exactly what the ledger and
position data produce.

---

# Part 8 — The competitive set

| Player | Owner | Position reporting | Condition |
| :- | :- | :- | :- |
| **ConstructConnect** | Roper | No | Strong parent (50.9% EBITDA), weak product (Insight 3.1/10) |
| **RIB SpecLive** | Schneider Electric | No | 750+ manufacturers claimed, quiet in the US |
| **Hubexo** | TA Associates / Stirling Square | Unknown | **Launched Lattira in the US, Feb 2026. Watch closely** |
| **Parspec** | $31.5M raised | Internally | **Launched an OS for lighting rep agencies, Mar 2026** |
| **Dodge** | Clearlake + STG | No | S&P Selective Default 2024, now CCC+, PIK due 2029 |
| **Building Radar** | ~$7.2M raised | Discovery only | Europe-weighted |
| **ARCAT** | Independent | No | 2M+ visits/yr, free to users |

**The three that should worry you:** **Hubexo** (owns both spec content and
project leads in North America; whether they combine them is UNVERIFIED but the
org chart points at it) · **Parspec** (just moved into the beachhead buyer;
moving from "help the agency quote" to "tell the manufacturer where its brand
appears" is a packaging decision, not a data problem) · **ConstructConnect/Roper**
(owns both ends via Deltek Specpoint and AIA MasterSpec; could build this from
first-party data SpecIndex will never have — the answer is the two things they
will not do: free public search, and a demand-side specifier graph).

**Check personally: SpecBooks (Conduit)** — the closest verbal collision with
SpecIndex's positioning language, before any deck goes to an investor who will
search that phrase.

---

# Part 9 — What to avoid

- **Do not scrape ConstructConnect, Dodge, Blue Book or BuildingConnected.** Their
  AUP explicitly prohibits scraping "for use in machine learning or training
  artificial intelligence systems" and for building competing services. With a
  former VP of Product as founder this is the worst available optic.
  **The public-data-only boundary is what keeps the company defensible.**
- **Do not build the cross-filtering chart dashboard**, and never render a permit
  job-cost histogram.
- **Do not claim MasterFormat classification without resolving the licence.** CSI
  moved to a revenue-scaled subscription in Feb 2026 (from $699/yr). Pay it, say
  so publicly, and note that the federal government publishes complete
  MasterFormat-numbered libraries free.
- **Do not lead with 500K+.**
- **Do not drift toward a verification army.** Dodge advertises 400+ field
  reporters. In 2026 that is a cost liability, not a moat.
- **Do not overclaim what is live.** Label the beta scope explicitly on every
  record and every slide.

---

# Part 10 — Fundraising

Recent comparable rounds: PermitFlow $54M B (Accel) · Trunk Tools $40M B ·
Attentive.ai $30.5M B · **Parspec $20M A (Threshold)** · Document Crunch $21.5M B ·
Agave $15M A · Building Radar $7.2M · Handoff $5.8M (Nemetschek **with Masco, a
building-product manufacturer**) · Shovels.ai $5M seed · **Cascade $3.5M seed
(a16z Speedrun)** · Bild AI $3.1M.

Two matter beyond the numbers: **Cascade** mines permits, bond filings and public
meeting minutes — the same mechanism, different buyer. **Masco** investing in
Handoff is evidence manufacturers already allocate capital here.

**Valuation anchor:** Paradigm/Builders FirstSource, $450M on ~$50M revenue
(**~9x**), the closest functional comp. Vertical data comps range MSCI 14.3x to
ZoomInfo 1.8x — the spread comes from whether the data is an input to
high-stakes decisions customers cannot rebuild. **The addenda ledger is a
hard-to-replicate historical corpus. Do not claim an exclusive feed.**

**The empty seat, stated correctly.** No venture-funded US startup was found
selling self-serve, public-data-driven, project-level spec intelligence to
building-product manufacturers as its core business — and that survived a hard
falsification attempt. **Do not say "nobody is even trying."** Say the narrower,
stronger thing: several players sit adjacent, and nobody with venture backing has
stitched the mechanism and the buyer together. An empty category usually means no
market; a validated-but-unstitched one does not.

---

# Part 11 — Risks and open questions

**What a sharp investor will press on:**

- **The product the strategy prices does not fully exist yet.** Basis-of-design
  extraction and the addenda ledger are a real build. State it before someone
  finds it.
- **The timing claim.** Permits are filed at or near the *end* of design, later
  than "a year before anyone requests a quote" implies. Measure the announcement-
  vs-permit split and quote that.
- **The ConstructConnect overlap.** Non-compete scope and departure date need a
  clean story. The honest version is better than the evasive one.

**Open questions only Asif can answer:** Do SpecShare or Insight Analyze actually
distinguish basis of design from listed alternate? · Is the pipeline ingesting
full specification documents? · What share entered at announcement vs permit
stage? · What did design partners say they would pay? · Do lighting manufacturers
fund their agencies' software? · Has US 9,946,715's maintenance fee lapsed? ·
Is the Delaware certificate actually filed?

**Facts still open, never to be estimated:** design partner count and names,
weekly-active reps, beta signups, brand-mention accuracy, the raise amount.

---

# Part 12 — Corrections to make before the next submission

1. **The competitor line.** "ConstructConnect is contractor-side, different
   customer entirely" is **wrong** — they sell a manufacturer product line today
   at $199/month with specification share tracking by MasterFormat code, and Roper
   owns both ConstructConnect and Deltek Specpoint.
2. **The pricing unit** becomes territory pricing with unlimited seats.
3. **The AWS language:** built Cloud Control API from zero into a top-ten service,
   launched at re:Invent 2021, ran product for CloudFormation across 2M+ accounts.
   The "$6.5B revenue impact" figure is **retired in writing**.
4. **Age:** 52 until 2026-09-23.
5. **Dodge's field reporter count** is 400+, not 500+.

---

## Sources

Full source list retained in the Google Doc. Key references:
[ConstructConnect AUP](https://www.constructconnect.com/acceptable-use-policy) ·
[Insight on TrustRadius](https://www.trustradius.com/products/constructconnect-insight/reviews/all) ·
[US 2020/0159985 A1 (abandoned)](https://patents.google.com/patent/US20200159985A1/en) ·
[US 9,633,012](https://patents.google.com/patent/US9633012B1/en) ·
[CSI MasterFormat EULA](https://www.csiresources.org/csistore/mf-eula) ·
[NEMRA Contracts Whitepaper](https://www.nemra.org/wp-content/uploads/2023/12/CONTRACTS-WHITEPAPER.pdf) ·
[EvoLucia rep agreement](https://contracts.justia.com/companies/evolucia-inc-23746/contract/685731) ·
[OASIS spec registration](https://support.oasissalessoftware.com/hc/en-us/articles/360038388172-Specification-Registration) ·
[SAM.gov Opportunities API](https://open.gsa.gov/api/get-opportunities-public-api/) ·
[UFGS via WBDG](https://www.wbdg.org/dod/ufgs) ·
[Procore S-1](https://www.sec.gov/Archives/edgar/data/1611052/000119312520057081/d564161ds1.htm)
