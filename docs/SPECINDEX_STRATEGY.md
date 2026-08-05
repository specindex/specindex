> **Mirrored from Google Docs `1eR91QZU5QbA1unf7HUgZSHmJO6bzzexQ8cENknHjUQA`
> ("SpecIndexCompanyStrategy", modified 2026-08-05 23:43).** The Doc is the
> editable original; this copy is versioned alongside the code that implements
> it. **Re-mirror after any Doc edit.**
>
> **Division of labour:** this file decides WHETHER a thing is worth doing;
> [`AGENT_STRATEGY.md`](./AGENT_STRATEGY.md) decides HOW. On conflict, this wins
> on scope, that wins on method.
>
> ⚠️ **Appendix I is marked internal — remove before this circulates externally.**
>
> **This supersedes the earlier research-heavy strategy doc**
> (`1wyKOBTcRXvps31iCdE1RNUyPUZsS3qJxV3hkHFtgcUk`). The material change: that
> version defined the moat as *the addenda ledger + the citation graph*. **This
> one defines it as SPECS PLUS CRM** — spec data gets an agency to open the
> product; the tracked project record carrying that agency's own notes is why
> they do not leave. It also names **Acelab** as the closest competitor, which
> the earlier version did not.

**SpecIndex**

**Company Strategy**

*Asif Hussain, Founder and CEO. 5 August 2026. The narrative runs five pages. Everything after it is reference material and is not meant to be read in the room. Appendix I is internal and comes out before this circulates.*

# 1. Summary

SpecIndex tells a building product manufacturer whether its brand is the basis of design on a live commercial project, a listed alternate, or absent, and who is trying to displace it. Nobody sells that as an observed, market-wide, cited outcome today. We build it from public records only, every claim links to the page it came from, and the underlying project index is free.

We’re positioned today as a project lead product, and that’s the wrong category. It’s where ConstructConnect Insight, Dodge One and Building Radar already sit, and it’s where every customer complaint in our research lives. Insight rates 3.1 out of 10 on TrustRadius. A salesperson at Hubbell, an electrical manufacturer that is exactly our buyer, gave it 1 out of 10. A reviewer on G2 wrote that much of the information can be found publicly online, which is our own thesis, said by a competitor’s customer, on the competitor’s review page. Leads are a feature. Position is the business.

The moat is specs plus CRM. Spec data gets an agency to open the product. The tracked project record, carrying that agency’s own notes, is why they don’t leave. Over the next 18 months we’re funding the addenda crawler, basis-of-design extraction to general availability in Divisions 23 and 26, and a go-to-market hire who already knows rep agencies. The raise amount is open pending the design-partner conversations described in section 7.

# 2. What we sell, and why it’s changing

Every commercial specification does three things. An engineer names one manufacturer and model as the basis of design and sizes the schedule around that unit. A list of acceptable alternates settles who else is eligible. A substitution clause sets a date after which nothing changes. All three are recorded in documents that are already public, and nobody indexes them.

Being the basis of design and being a listed alternate are the same brand name in the same document. One is a job. The other is a price check. The channel already prices the difference: a rep agreement pulled from public filings pays 25% of commission for finding the opportunity, 50% for writing and securing the specification, and 25% for closing the order. Half the money sits on the step nobody sells a product for. Reps also negotiate spec protection of 18 months, and up to 24 on national accounts, so a specification lost this summer is commission lost well into 2028.

So we’re not selling earlier leads. We’re selling position, with evidence. A free permanent page for every project, indexable, carrying a permanent SpecIndex identifier and a source link on every fact. A paid layer that reports position per CSI division with a page-level citation. A ledger of every approved and rejected substitution, pulled from public addenda, naming who got displaced and when. Delivery by weekly email digest and API, not by dashboard, because reps live in an inbox and a CRM.

# 3. The wedge

We checked the three products that claim to do this. Dodge SpecShare alerts a manufacturer when its products or a competitor’s get specified. ConstructConnect Insight Analyze tracks competitor specification rates by MasterFormat code. RIB SpecLive Impact tracks where, when and how products are specified. All three report that a brand appears in a spec. None of them, anywhere in its public product pages, brochures, help documentation or review corpus, documents reporting which position that brand holds.

That gap isn’t cosmetic. Finding a brand name inside spec text is a string match. Telling a basis-of-design clause apart from an acceptable-manufacturers list means parsing the procedural language around it, and none of the three describes doing that. We say not evidenced in the public record rather than proven absent, because none of them publishes a data dictionary. Confirming it is the first question in every design-partner call, and Asif may already know the answer from inside ConstructConnect.

One company has to be named here, because an investor will name it. Acelab has raised roughly $25M, including a $13.5M Series A led by Navitas Capital with JLL Spark and DivcoWest, and the headline on its manufacturer page reads "Become the basis of design for every project." Close to our language, different product. Acelab sells influence over the decision inside the design workflow it controls, and it can only report what happened inside Acelab. We report the observed outcome across the market, from the public record. Acelab is also the best evidence anyone has that this thesis is fundable, and we should use it that way.

# 4. The moat: specs plus CRM

Either half alone is beatable. A spec dataset is copyable by anyone willing to spend the years, and Roper already owns a national project database and, through Deltek, a leading spec-authoring engine. A rep CRM with no spec data is a low-margin fight against Repfabric and OASIS, who hold the seats already. Together they compound.

One asset on the spec side genuinely can’t be reconstructed. Substitution requests get ruled on publicly, and the winning and losing manufacturers are named in addenda posted to public bid portals, with dates. Nobody indexes them. They come down after award, so an 18-month archive can’t be built later by anyone who starts later. The citation graph, the specifier graph and the public corpora we harvest are all defensible, but none of them is unique. The ledger is. It’s also the only thing on this plan with a clock running, which is why the crawler starts in week one.

The CRM half doesn’t exist until a rep tracks a project and writes a note on it. Then it produces three things nobody else can get. Switching cost stops being a subscription and becomes institutional memory: 18 months of call notes hung on project records don’t export anywhere, because no other system has a project record to hang them on. Second, a demand-side dataset showing which specs reps actually chase and win, invisible to every incumbent, which measurably improves our own openness scoring. Third, and this is the one that matters, a spec registration record.

NEMRA’s model contracts contain no spec-registration clause. Manufacturers each run their own agent-only web form, and none publishes proof requirements, protection length or dispute policy. OASIS does ship spec registration, but inside one vendor’s stack, and its own documentation concedes there is no reliable method to credit an out-of-territory job. So there’s no neutral, cross-manufacturer record and no arbiter. A tracked project carrying a permanent identifier, a cited position and a timestamp is exactly that record. Registries are the most durable structure in this market.

We won’t build these in parallel. Free index, position and ledger first, because nothing else earns a weekly open. Then one track button. Then notes. Then registration export. Pipeline and commission tracking only after that, and only if the earlier phases show real usage. Externally this is the spec system of record, not a Salesforce replacement, because the second framing starts a fight on the incumbent’s terms against an eight-person agency whose entire software budget is $6,000 to $10,000 a year.

# 5. Market and model

We price by territory with unlimited seats, never by seat. The people who need access are spread across a manufacturer’s regional team and the agencies carrying its lines, and most of them don’t work for whoever signs the invoice, so a seat price taxes the exact behaviour that makes the product valuable. Procore’s S-1 states the same principle. Parspec, the best-funded company selling into this channel, landed on it independently and sells unlimited users with metered credits.

The card: a free public index, a territory licence at $4,990 per state or top-50 metro per year with unlimited seats, and a national brand licence at $45,000 per brand per CSI division. A $2,490 starter rung exists because the rep channel’s budget ceiling is real. We publish the self-serve prices, which no incumbent does, and gate only the enterprise tier.

TAM is $209M, built bottom up from four sourced NAICS categories and two stated assumptions: a 2.8x scale factor to the full building-products universe, and 35% of manufacturers running a national spec motion. Both are visible in Appendix E rather than buried, and a Census SUSB pull replaces the first with a real count. The lighting and HVAC beachhead is $46.7M. Two independent methods agree: the bottom-up count gives $46.7M, and a top-down derivation from lighting and HVAC manufacturing revenue at 5% sales and marketing with 2% going to data tools gives $59.0M, so bottom-up is 0.79x top-down.

Base case ARR is $320K at the end of year one, $1.37M at year two and $3.62M at year three. Year three is 7.8% of the beachhead alone. The uncomfortable part, stated rather than buried: third-party estimates put Dodge and ConstructConnect combined at roughly $195M across all buyer types, both low confidence and neither disclosed. If manufacturers are 30% of that, current manufacturer spend on project data is about $58.6M, and our TAM assumes the category grows about 3.6x. It can, and the reason is attribution. Manufacturers pay the AIA between $4,900 and $18,500 a year for continuing-education provider status alone and can’t produce a single quantified return on any of it.

# 6. Competition

The set is crowded and the middle is empty. Dodge owns the category name for spec alerts and went through a selective default in 2024, was moved back into the CCC tier by S\&P that December, and carries a payment-in-kind second lien due 2029, so it can’t fund a free tier. ConstructConnect sits inside Roper’s Network Software segment, which runs $1.6B at 50.9% EBITDA, though ConstructConnect itself isn’t broken out. Its manufacturer product is its worst-rated asset, its AI spend went into computer vision on plan sets rather than specifications, and it can’t make search free without cannibalising a renewal book that reprices at 50% to 300%. RIB SpecLive, owned by Schneider Electric, is the most underrated and the quietest in the US. Hubexo launched a specification content platform here in February 2026 and now owns spec content and project leads in North America, which makes it the entrant to watch.

Two adjacent companies are better funded than any of them and neither occupies our seat. Parspec has raised $31.5M and owns everything from the request for quote onward, with 3.2M cut sheets crawled across roughly 4,000 manufacturer sites and $30B quoted in the twelve months to July 2025. It has no project data and no monetised manufacturer product, though it shipped a sales product for lighting rep agencies in March 2026, which collides directly with our beachhead channel. Acelab has raised $25M and owns the architect’s material research workflow, so it sees only projects inside its own platform, skewed toward the largest firms. Parspec starts where we end. Both prove this channel pays for software, which is the hardest question a pre-seed founder gets asked.

Acelab has one vulnerability worth saying out loud. It sells search boosting and priority placement in the same subscription that sells the analytics measuring that placement. Architects will work out eventually that the recommendation engine recommends whoever paid. Every SpecIndex fact links to a public source, and we sell no placement of any kind. Neutrality is a product feature and it belongs on a slide.

Three smaller players sit close enough to check before any deck goes out. SpecBooks markets itself as an intelligence platform for building product manufacturers, which is the nearest verbal collision with our own positioning, though the product underneath is distribution and showroom data rather than project tracking. UpCodes reaches architects at the moment of specification. Cascade, funded by a16z Speedrun in July 2026, mines permits and public meeting minutes using the same mechanism we do, aimed at construction firms rather than manufacturers.

# 7. What we do next

Days 1 to 30, two things run at once. We prove the wedge and we start the crawler. On the wedge: 20 public projects in Divisions 23 and 26 where the full manual is posted, basis of design extracted from each with a page-level citation, addenda pulled for the same 20, then that sample in front of five rep agencies. One question. What would you pay to have this for every project in your territory, and what would you stop paying for. The crawler cannot wait for the answer, because addenda come down after award and every week not crawling is data gone for good.

Days 31 to 60 we widen the intake and ship. Ingestion from the SAM.gov opportunities interface, the VA specification library, the unified federal guide specifications, and the ten largest public university and state agency standards libraries. Basis-of-design extraction for two divisions, delivered as an email alert and an API rather than a dashboard. Resolve the MasterFormat licence, which costs $699 and removes a live question.

Days 61 to 90, distribution. Approach Ingen and Repfabric about a certified integration. Stand up a design council of eight to twelve manufacturers and agencies, on the model Parspec used to build its own roadmap, which also closes the open design-partner question before the next application deadline. Publish a benchmark on what a spec win is worth, since no published figure exists. Build the programmatic index pages over the projects we already hold, because no incumbent in this category has a search surface and gating is why.

# 8. Risks

The largest risk is that the product this strategy prices doesn’t fully exist yet. The site today describes permits, bids and awards. Basis-of-design extraction and the addenda ledger are a real engineering build, not a filter change, and until they ship we’re selling leads against a published $199 anchor. Better to say that here than have it found.

Second, scope on the CRM. If reps read the digest weekly and never track anything, we’re a data subscription against a $46.7M beachhead rather than a registry, and the later phases shouldn’t get built. The mitigation is the sequence in section 4, not optimism.

Third, timing language. We say we track projects while they’re still being designed, often a year before a quote. Permits are usually filed at or near the end of design, which is later than that implies. Announcement data is genuinely early and permit data isn’t, so we should quote the split rather than the general claim. This is exactly where Dodge and ConstructConnect will attack.

Fourth, intellectual property, and it has a clock. Our public repository has disclosed the scoring methodology and extraction pipeline since 25 July 2026, which starts a 12-month US filing window and has in all likelihood already forfeited European rights on everything described there. Three inventions underneath the product are genuinely filable and none of them is the priority score. Separately, one granted competitor patent covers bidirectional hyperlinked citation between a spec book and a submittal item, with a continuation pending. The design constraints are cheap and they’re in Appendix G.

Fifth, the founder’s overlap with ConstructConnect through July 2026. The honest version reads better than the evasive one, and the public-data-only boundary has to be said out loud and kept true. Incorporation also needs closing: an EIN exists, but the Delaware certificate in Drive is an unfiled template with placeholder fields, and no investor document should answer yes on incorporation until the stamped copy is filed.

**Appendix**

*Reference material. Sourced throughout. Anything marked UNVERIFIED is a lead, not a fact, and must not go into a deck or an application.*

# A. The wedge, evidence

Checked 5 August 2026 across product pages, brochures, PDF datasheets, help documentation, press releases and the public review corpus.

|  |  |  |
| :-: | :-: | :-: |
| \*\*Product\*\* | \*\*What it says it detects\*\* | \*\*Position reporting\*\* |
| \*\*Dodge SpecShare\*\* | Alerts when you or a competitor’s products are specified. A list of projects where plans and specs call for your product. | Not documented |
| \*\*ConstructConnect Insight Analyze\*\* | Track competitor specification rates and market share, organised by 1,400+ MasterFormat codes. | Not documented |
| \*\*RIB SpecLive Impact\*\* | Tracks where, when and how your products are specified, as soon as they are used in a project spec. | Not documented |
| \*\*Acelab (manufacturer tier)\*\* | "Become the basis of design for every project." Placement and influence inside the architect workflow, plus platform-internal analytics. | Influence, not observation. Sees only projects inside Acelab. |

  

**Why the money is on this step.** A rep agreement filed publicly (EvoLucia) pays commission in three milestones: 25% for identifying the opportunity, 50% for writing and securing the specification, 25% for closing the order. Reps separately negotiate spec protection of 18 months, and up to 24 on national accounts. There is no public benchmark anywhere for what a spec win is worth, which is why producing the first one is simultaneously a product, a research asset and a public relations asset.

**The registry gap.** NEMRA model contracts contain no spec-registration clause. Spitzer, Insight Lighting, Karice, Delray and Tegan each run separate agent-only web forms, none publishing proof requirements, protection length or dispute policy. Ingen’s OASIS documentation states: "There exists no magic method to ensure the agency receives proper credit for an out of territory job." No neutral arbiter exists.

# B. Competitive dossiers

## B.1 The field, ranked by how much it should worry us

|  |  |  |  |  |  |
| :-: | :-: | :-: | :-: | :-: | :-: |
| \*\*Player\*\* | \*\*Owner / funding\*\* | \*\*Sells to mfrs\*\* | \*\*Position reporting\*\* | \*\*Published price\*\* | \*\*Condition\*\* |
| \*\*ConstructConnect\*\* | Roper (NYSE: ROP) | Yes, Insight line | No | $199/mo per licence per market | Roper Network Software segment: $1,600.8M FY25, 50.9% EBITDA. CC not broken out. Insight rates 3.1/10. |
| \*\*Acelab\*\* | \\\~$25M raised; $13.5M A led by Navitas, Oct 2025 | Yes, core wallet | Influence only | None, demo-gated | 20K+ design firms claimed, 80% of the top 100 architecture firms. Placement conflict. |
| \*\*Parspec\*\* | $31.5M; Threshold-led A, Jul 2025 | Not monetised | No | Third parties publish $149 to $1,084/mo | 300+ customers, $30B quoted TTM, 4x growth. |
| \*\*RIB SpecLive\*\* | Schneider Electric | Yes, five modules | No | Not published (the \\\~$4,063/yr figure is SpecLink, the authoring tool) | 750+ manufacturers claimed. Quiet in the US. |
| \*\*Hubexo\*\* | TA Associates / Stirling Square | Launched Lattira in US, Feb 2026 | Unknown | None | Owns spec content and leads in North America. Watch. |
| \*\*Dodge\*\* | Clearlake + STG | Yes, SpecShare | No | \\\~$7,000/yr | S\\\&P selective default 2024, moved back to the CCC tier Dec 2024. PIK 2nd lien due 2029. |
| \*\*Anguleris\*\* | Independent | Yes, content side | No | None | Rolled up Modlar, ClubDesign, Concora. Launched Gaudi. |
| \*\*Building Radar\*\* | \\\~$7.2M raised | Yes | Discovery only | \\\~$500 to $2,000/mo est. | Europe-weighted, no US review footprint. |
| \*\*ARCAT\*\* | Independent | Yes, paid listings | No | \\\~$16,500/yr UNVERIFIED | 2M+ visits/yr, free to users. |

  

## B.2 Acelab: the closest thing to a direct competitor, and why it is not one

*Every figure in B.2 is sourced to the Acelab deep dive in Drive under SpecIndex \> Competitor \> Acelab, and to Acelab’s own marketing pages. None of it is disclosed or audited.*

Founded 2021, Manhattan. Product is Material Hub, an AI platform where architects research, compare and specify materials, launched March 2025, with bidirectional Revit integration so selections sync live and keynotes generate against MasterFormat divisions. Catalogue claims 250,000+ products, 10,000+ brands, 2,000+ certifications, 200+ performance metrics. Distribution claims 20,000+ design firms and 80% of the top 100 architecture firms, with Gensler, AECOM, Stantec and CannonDesign named. Investors: Navitas Capital (lead), JLL Spark, DivcoWest, Pillar VC, Draper Associates, PJC, Transcend Partners. Industry angels include a BIG partner and a SHoP founding principal, which is a credibility play worth copying on the manufacturer side.

Their manufacturer pricing ladder is demo-gated at every tier: Starter (free brand page), Market (AI search boosting, unlimited rep seats, basic analytics), Accelerate (pipeline dashboard, sales intelligence, architect engagement portal), Growth (priority placement in recommendations, CRM API integration, market and competitive intelligence reports). Three readings. Competitive intelligence prices highest, which says brand-versus-brand belongs at the top of our own ladder, not as an add-on. CRM API sits behind the top tier, which confirms the buyer wants this data inside their own systems. And the intelligence product and the advertising product are the same subscription, which is a conflict architects will eventually notice.

The structural blind spot: Acelab sees a project only when an Acelab-using architect opens a material research session inside the tool. Coverage is a subset skewed to the largest firms, and most US commercial square footage is not designed by the top 100. Timing is later than claimed, typically design development or construction documents, which is often after the basis of design has been named. There is no market-wide project index anywhere in their product surface, and their lead investor describes them as the system of record for materials data. Materials, not projects.

**The line to use:** Acelab tells a manufacturer what happened inside Acelab. SpecIndex tells them what is happening in the market. Their object is a product catalogue; ours is a project index. Do not turn that into a count comparison, because ConstructConnect claims 825,000 projects and Dodge claims hundreds of thousands a year, and volume is a frame we lose. The obvious objection, why would Acelab simply add public permit data, has an honest answer: it is off-thesis, because a neutral market-wide index surfaces thousands of projects where they have no influence to sell. Companies rarely build the thing that devalues their own inventory. That is a reason for speed, not a permanent guarantee.

**Reliability flag.** Getlatka lists $32.1M ARR and a 2019 founding date for Acelab. Both are wrong and the record is scraped. Do not cite it. A $13.5M Series A from this syndicate implies low single-digit millions of ARR.

## B.3 Parspec: adjacent, better funded, and the clearest phase story we have

Raised $31.5M ($11.5M seed led by Innovation Endeavors, Feb 2024; $20M Series A led by Threshold, Jul 2025). Built a crawled catalogue of 3.2M+ cut sheets across roughly 4,000 manufacturer websites, starting from submittal packages, the most mechanical and most hated document chore in the channel. 300+ distributor and rep-agency customers, $30B quoted in the twelve months to July 2025, 4x revenue growth over the same period. Note that their own public figures for catalogue size disagree with each other across pages, so cite the 3.2M cut sheets and nothing else. In March 2026 they launched a sales management product for lighting rep agencies, a direct collision with our chosen channel. They still have no project data and no monetised manufacturer product.

|  |  |
| :-: | :-: |
| \*\*Phase\*\* | \*\*Who covers it\*\* |
| \*\*Project announced, funded, permitted\*\* | SpecIndex |
| \*\*Design, CSI spec written, basis of design named\*\* | SpecIndex |
| \*\*RFQ issued, quote, alternates, submittal\*\* | Parspec |
| \*\*Order, fulfilment, change orders, close-out\*\* | Parspec |

  

Put that table in the deck. It makes the category legible to an investor who already knows Parspec, and it converts the best-funded neighbour from a threat into evidence that the adjacent workflow is worth $31.5M. Hold the caveat internally: their manufacturer page already promises that your products win more specs, and with that catalogue and that quote flow they are one data partnership from the front half of the funnel. Assume a twelve to twenty four month window.

**Their published pricing, which we should partly copy.** Unlimited users per subscription, metered on platform credits: one per submittal, one per priced quote, revisions free. Third parties publish the tiers Parspec will not: Silver $149/mo (240 credits), Gold $349, Platinum $559, Diamond $1,084, then Enterprise. Note that Silver is exactly the $149 that was our illustrative seat price, except theirs buys the whole agency.

**Six things worth stealing.** Start with the chore rather than the intelligence, and ship a free ungated spec-book extractor. Go unlimited seats and meter the expensive verbs. Publish the price with a start-free button, because they cannot. Build the programmatic search surface over our project pages, since nobody in this category ranks and they sit on 3.2M documents with seven blog posts. Run a design council on the model of their sixteen-agency steering committee. And use their trade press list: Electrical Trends, tEDmag, EdisonReport, inside.lighting, US Lighting Trends, Distribution Strategy Group.

**Fundraising consequence.** Building Ventures and Heartland are on our target list and are both Parspec investors, so they will understand us in ninety seconds and will have a Parspec-shaped prior. Lead with the phase table. Innovation Endeavors and Threshold have written the cheque that says they believe in this supply chain and hold no project-data position. Innovation Endeavors’ own memo carries a citable stat: the average cost of sale of construction products from manufacturer to builder is 21% of final sale price, more than twice comparable industries.

## B.4 What not to copy

Do not scrape ConstructConnect, Dodge, Blue Book or BuildingConnected. Their acceptable use policy explicitly prohibits scraping for machine learning and prohibits using the service to build competing services. There is no record of enforcement, but with a former VP of Product as founder this is the worst available optic. Do not demo-gate everything, which is coherent for six-figure enterprise deals and incoherent for a self-serve product. Do not run two verticals at once: Parspec spent roughly four years in lighting and electrical before broadening, and lighting and HVAC have different rep structures, divisions, press and trade shows. Do not contradict our own numbers the way Parspec’s homepage and about page do on the same day. And do not drift toward a verification army; Dodge advertises 400+ field reporters, which in 2026 is a cost liability.

# C. Product

## C.1 Five layers

|  |  |  |
| :-: | :-: | :-: |
| \*\*Layer\*\* | \*\*What it is\*\* | \*\*Free or paid\*\* |
| \*\*1. Public project record\*\* | Permanent, indexable page per project. Permanent SpecIndex ID. Every fact linked to a public document with a retrieval date. | Free forever |
| \*\*2. Specification position\*\* | Basis of design, listed alternate or absent, per CSI division, with a page-level citation into the project manual. | Paid |
| \*\*3. Addenda and substitution ledger\*\* | Every approved and rejected substitution from public addenda, naming who was displaced, with dates. | Paid |
| \*\*4. Delivery\*\* | Weekly territory digest, alerts, CRM push, API. Unlimited seats. | Paid |
| \*\*5. Tracked projects and notes\*\* | Track, notes, contacts, activity, and an exportable spec-registration record. | Paid |

  

Mocks for layers one to four are in SpecIndex-Product-Mocks.html. A homepage rebuild against this strategy is in SpecIndex-Homepage-Mock.html.

## C.2 The record template

A project page is one instance of a template, not a design. Eight fixed slots, each with a defined populated state and a defined empty state: identity, spec position, actions, fact grid, scope by division, who to call, sources, activity. Slot order never varies. Spec position and actions always render, on every record, including records with nothing parsed. Fact-grid cards are omitted rather than showing "Not reported". Missing location parts drop with their separators. All confidence language lives in Sources only.

**The two rules that drive most of the work: never render an empty field, and never claim wider than the evidence.** Those are not layout rules. The first is the wedge made structural, so position cannot quietly vanish from records where extraction failed. The second is the citation graph expressed as a user interface constraint. The empty-state proof is the important part: a permit-only record with zero documents parsed renders the same eight slots at about half the height, invents nothing, and still opens with an actionable position ("No documents parsed yet, spec window open and unread") and a notify action.

## C.3 Defects on the live detail page, to fix before a design partner sees it

Square footage reads "Not reported" while the brief four inches below states 175,000 GSF across five stories, so the data is on the page but not in the field. Location renders as ", Georgia" with an empty city and a dangling separator. A title fused Executive Order 14398 into a building name as "Eo 14398". SOURCES VARY fires thirteen times on one record, once directly under "Verified construction team", on a page claiming links are live-checked while the attributions that would earn trust are not links. And a real bug: source data pulled reads 26 July 2025 against a 29 July 2026 page update. The last two are the dangerous ones. A product whose entire differentiation is cited evidence cannot ship a page that performs confidence while failing to link its sources.

## C.4 Interface constraints that come from competitor patents

Lead the paid product with alerts, digests and an API rather than a dashboard. If a dashboard ships, use a filter sidebar driving a single results view, or read-only charts, and never cross-filter multiple charts. Never render a chart that bins permits into cost ranges with counts. Never call any output a submittal register or organise extracted data by submittal category. Ship one-directional citation only, from an extracted fact to its source page, with no reciprocal link back. Rationale and patent numbers in Appendix G.

# D. Pricing

## D.1 The card

|  |  |  |  |
| :-: | :-: | :-: | :-: |
| \*\*SKU\*\* | \*\*Price\*\* | \*\*Unit\*\* | \*\*Seats\*\* |
| \*\*Public Index\*\* | $0 | Unlimited search | Unlimited |
| \*\*Territory Starter\*\* | $2,490/yr | One metro. Alerts and digest only, no ledger | Unlimited |
| \*\*Territory\*\* | $499/mo or $4,990/yr | Per state or top-50 metro | Unlimited |
| \*\*Region\*\* | $24,990/yr | Per Census region, up to 12 states | Unlimited |
| \*\*National (territory SKU)\*\* | $79,990/yr | All 50 states and metros | Unlimited |
| \*\*Brand\*\* | $45,000/yr | One brand, one CSI division, all US | Unlimited |
| \*\*Brand Enterprise\*\* | $120,000/yr and up | Multi-brand, multi-division | Unlimited |

  

Add-ons: additional CSI division $15,000/yr, additional brand $25,000/yr. Annual billing gets two months free. Volume ladder, published rather than negotiated: territory one at 100%, two to five at 70%, six to twelve at 50%, thirteen and up at 35%. Metered: spec-book extraction $12 per document, bulk brand check $0.05 per project scanned, historical back-file export $2,500 per division per year of history.

## D.2 The anchors

|  |  |  |
| :-: | :-: | :-: |
| \*\*Product\*\* | \*\*Price\*\* | \*\*Basis\*\* |
| \*\*ConstructConnect Project Intelligence Pro\*\* | $199/mo per market per licence | Published |
| \*\*Dodge Construction Network\*\* | \\\~$7,000/yr | BBB complaint records |
| \*\*Archbase\*\* | from $1,000/mo billed annually plus deployment fee | Published |
| \*\*Parspec\*\* | $149 to $1,084/mo, unlimited users, metered credits | Third-party review sites |
| \*\*ARCAT manufacturer listing\*\* | \\\~$16,500/yr | UNVERIFIED |
| \*\*RIB SpecLink\*\* | \\\~$4,063/yr first seat | Reported |
| \*\*CoStar Suite, all markets\*\* | list \\\~$71,000/yr, median paid \\\~$40,000/yr | PriceLevel |
| \*\*Repfabric (the rep CRM)\*\* | "roughly the cost of a cell phone plan per person" | Vendor stated |
| \*\*Acelab\*\* | No published price at any tier | Demo-gated |

  

**Worked example.** An eight-person NEMRA agency covering Georgia, Alabama and Tennessee pays $4,990 + $3,493 + $3,493 = $11,976 a year with unlimited seats. On ConstructConnect’s published unit of $199 per licence per market, eight licences in a single market is $19,104. Before using that head-to-head anywhere external, quote their pricing page verbatim on the unit, because the comparison inverts if a market licence turns out to cover a whole agency. The safe version of the claim needs no comparison at all: three states, unlimited seats, $11,976. The honest tension is that $11,976 still sits above the likely $6,000 to $10,000 total software budget for an agency that size, which is why the Starter rung exists and why the model assumes two territories per account in year one rather than three.

**On publishing prices.** Acelab demo-gates every tier and the Acelab analysis argues we should too, because this is a marketing-budget sale. Parspec also gates, and four review sites publish its prices anyway. We resolve it by splitting: publish the self-serve territory prices with a start-free button, because that is a positioning claim against the entire category, and gate Brand and Enterprise, which are a real sales conversation. Cap renewals at 5% in writing, which costs nothing and is the loudest thing we can say to anyone repriced 300% by ConstructConnect.

# E. Market sizing

## E.1 TAM

|  |  |  |  |
| :-: | :-: | :-: | :-: |
| \*\*Line\*\* | \*\*Accounts\*\* | \*\*ACV\*\* | \*\*Value\*\* |
| \*\*US building product manufacturers with a national territory sales org\*\* | 4,110 | $45,000 | $185.0M |
| \*\*US building product rep agencies\*\* | 2,450 | $9,860 | $24.2M |
| \*\*TAM\*\* |   |   | $209.1M |

  

Manufacturer count comes from four NAICS categories totalling roughly 4,200 establishments (lighting 1,100, HVAC 1,394, wood windows and doors 1,100, plumbing fixtures 600), all medium confidence and all from secondary aggregators of Census and D\&B data rather than raw Census. Two caveats matter. These are establishments and businesses rather than firms, so a multi-plant manufacturer is counted more than once, and NAICS 3351 is a four-digit code summed against five- and six-digit codes, so the granularity is mixed. That figure is then scaled 2.8x (ASSUMPTION) to cover roughly fifteen CSI-relevant product groups and filtered to 35% (ASSUMPTION) running a national spec motion. Both assumptions are the softest numbers in the model, and a Census SUSB 2022 pull at six-digit NAICS fixes the scale factor and the unit problem at once. Strip the 2.8x and TAM falls to about $90M.

## E.2 SAM and ARR

|  |  |  |  |
| :-: | :-: | :-: | :-: |
| \*\*Line\*\* | \*\*Accounts\*\* | \*\*ACV\*\* | \*\*Value\*\* |
| \*\*Lighting and HVAC manufacturers with a national sales org\*\* | 873 | $45,000 | $39.3M |
| \*\*Lighting, electrical and HVAC rep agencies\*\* | 750 | $9,860 | $7.4M |
| \*\*SAM\*\* |   |   | $46.7M |

  

|  |  |  |  |
| :-: | :-: | :-: | :-: |
| \*\*Case\*\* | \*\*Year 1\*\* | \*\*Year 2\*\* | \*\*Year 3\*\* |
| \*\*Conservative (0.55x accounts)\*\* | $191K | $773K | $2.02M |
| \*\*Base\*\* | $320K | $1.37M | $3.62M |
| \*\*Aggressive (1.85x accounts)\*\* | $607K | $2.52M | $6.70M |

  

*Multipliers are applied to account counts and rounded to whole accounts, so the case totals do not scale exactly by 0.55x and 1.85x.*

Base year three is 7.8% of SAM. The 750 agencies are NEMRA’s 400 plus 350 assumed HVAC and mechanical agencies. Rep agency accounts at year three are 20% of that 750, which is aggressive but reachable for the NEMRA half, since those are small, self-serve, sub-$15K and reachable through one organisation. The other 350 belong to no trade body at all and are a separate, unproven route to market. Manufacturer accounts are 3.7% of addressable beachhead manufacturers, which is conservative, and one Brand Enterprise deal moves year three by 3% on its own. The model deliberately assumes zero uplift from the CRM layer. Full derivation and live formulas in SpecIndex-TAM-SAM-ARR-Model.xlsx.

# F. Channel and go to market

Sell to rep agencies before manufacturer headquarters. They’re organised by territory, which is the pricing unit. They buy fast. They physically chase the project, and in the 2018 Egret survey over 80% of lighting reps said project business was their primary business. Their compensation rests on provable spec attribution and no system of record exists. And manufacturer deals follow the agencies rather than the reverse.

|  |  |  |
| :-: | :-: | :-: |
| \*\*Channel fact\*\* | \*\*Figure\*\* | \*\*Source\*\* |
| \*\*NEMRA member agencies\*\* | 400+ agencies, 200+ manufacturer members | NEMRA |
| \*\*NEMRA Lighting Division\*\* | Formed Nov 2024 (absorbed AAILA). Growing 15 to 20 members a month as of early 2026. Get the current count before quoting it. | Inside.Lighting, EW |
| \*\*NEMRA26 conference\*\* | 2,100 attendees, Orlando, Feb 2026 | EW |
| \*\*NEMRA27\*\* | Feb 1 to 4, 2027, Hilton Anatole, Dallas | NEMRA |
| \*\*Large lighting agency profile\*\* | 34.8 salespeople, 121 lines carried | Egret Consulting survey, 2018, via EW |
| \*\*Lighting rep commission rates\*\* | 11.4% to 13.3% blended | Egret Consulting survey, 2018, via EW |
| \*\*Line-card churn\*\* | 85% review the line card annually; 87% drop non-performing lines | Egret Consulting survey, 2018, via EW |
| \*\*Manufacturer-issued CRM licences\*\* | \\\~$1,500 per salesperson per year, usually one per rep firm | HVACR trade press |
| \*\*Rep software stack\*\* | Repfabric (multi-line CRM), OASIS by Ingen (quoting, spec registration), Repbox. None ingests external project data. | Vendor sites |

  

There is no national trade association for HVAC and mechanical rep agencies. AHRI is a manufacturer body, HARDI is distributors, MCAA is contractors. That makes lighting and electrical the cleaner beachhead. OASIS runs a formal certified integration programme with nine standardised integration types under a defined development contract, which is an institutional door rather than a cold email.

Public corpora worth harvesting, ranked by yield per unit of effort: the SAM.gov opportunities interface (full federal project manuals), UFGS via WBDG (Divisions 21 to 28, quarterly, public domain), VA PG-18-1 masters (predictable URLs, public domain), public university and state agency design standards (the underrated one, permanent URLs, and no incumbent appears to be harvesting it systematically), and roughly fifty state plus thousands of local procurement portals, which are the only source for addenda.

# G. Intellectual property

## G.1 The clock, and what it costs

The public repository at github.com/specindex/specindex has been readable since 25 July 2026 and contains the priority score formula, lead score source with constants, the extraction pipeline, the database schema and the source inventory. That is an enabling disclosure. The United States filing clock runs to 25 July 2027 and European and Chinese rights on everything described there are in all likelihood already gone, since the EPC has no general grace period. Two immediate actions cost nothing: adopt file-then-disclose so nothing technical becomes public before a provisional covers it, and review whether that repository should be public at all, given it also contains a document discussing separation and non-compete language. File as a small entity at $130, not micro entity: micro turns on each named inventor’s personal gross income against a $251,190 limit, which the founder’s 2025 income almost certainly clears.

## G.2 What is worth filing on

Three candidates, and the priority score is not one of them. It is a weighted sum, it is a business judgment about which projects a salesperson should call, and it is fully published. First and strongest: independent-source verification gating, where each machine-extracted assertion is re-verified through a second retrieval constrained to exclude the first document set, and the record is written to the index only on agreement and otherwise quarantined. The disjointness constraint is the mechanism and it is what a competitor would have to design around. Second: cross-source canonical project identity resolution, where field contribution to a match score is weighted by the historical reliability of that field from that source type and each surviving value retains a pointer to its originating record. That is what makes the citation guarantee true at field level and it is the technical foundation of the permanent identifier. Third: coverage-conditioned absence inference, which computes per project and per division whether the documents ingested were the kind that would have named a manufacturer, and emits an open-spec determination only above a threshold. That is the difference between absence of evidence and evidence of absence, made computable, and it is what makes the openness score trustworthy enough to sell.

## G.3 Freedom to operate

Nobody holds a patent on what we actually do. Dodge has none at all. ConstructConnect holds no claim on spec extraction: the branch that would have, US 2020/0159985 A1, was abandoned, and it is the only place in the family where named entity recognition and co-occurrence scoring appear in claims. Dead, unenforceable, and now useful prior art against anyone else. Its live family reads on faceted-search dashboards, which is why we don’t ship one. The closest MasterFormat classification art is expired or abandoned, so it works for us rather than against us.

|  |  |  |
| :-: | :-: | :-: |
| \*\*Patent\*\* | \*\*Holder\*\* | \*\*The constraint\*\* |
| \*\*US 9,633,012\*\* | iSqFt / ConstructConnect | Claim 1 has no interactivity requirement at all. Do not ship a chart that bins permits into cost ranges with counts. Lowest bar in the family. |
| \*\*US 9,946,715 / 9,785,638\*\* | iSqFt / ConstructConnect | Broad cross-filtering claims over spec documents. Do not cross-filter multiple charts over spec data. |
| \*\*US 12,242,990\*\* | Buildsite (submittal.com) | Bidirectional hyperlink between an extracted item and a spec-book location. Ship one-directional citation only. A continuation, US 2025/0182017, is pending and claims can be redrafted toward whatever we ship. Set a calendar reminder. |
| \*\*US 11,734,227\*\* | Autodesk (Pype) | Generic active-learning extraction loop, narrowed only by the phrase submittal register. Never use that word, never organise output by submittal category, never ship a rule-editing UI where a reviewer correction visibly updates a parsing rule. |
| \*\*US 2025/0252515\*\* | KOPE AI | Pending. The only live filing explicitly about matching building products to construction projects. Claim 1 requires a project model, which permit records are not, so not blocking today. Watch it. |

  

*Claim-scope reading, not legal advice. Confirm maintenance-fee status for US 9,946,715, whose 7.5-year grace period closed in April 2026, in USPTO Patent Center before relying on any of this, and get a freedom-to-operate opinion on the final interface before general availability.*

**Honest view on whether this matters.** For a pre-seed data and AI play the expected enforcement value is near zero. The real argument is narrower and it holds: we are destroying optionality every day the product is public and unfiled, permanently and irreversibly abroad, and preserving it costs $130 plus a few thousand dollars of attorney time. There is also one argument specific to us. Our competitive story includes the claim that ConstructConnect tried to patent AI spec extraction and abandoned it. Filing well on the layer they never claimed converts that from a talking point into a position.

# H. Risks and open questions

## H.1 What a sharp investor will press on

The product this strategy prices does not fully exist. The CRM half is a scope risk and the framing controls how bad it is; if tracked-project usage does not appear in phase two, phase five should not be built. The timing claim needs the announcement-versus-permit split quoted rather than the general statement. The founder overlap with ConstructConnect through July 2026 needs a clean story on non-compete scope and confidentiality before diligence. The live detail page currently contradicts the pitch, per Appendix C.3. And the empty-seat claim needs stating narrowly: Acelab is a funded United States startup selling specification influence to building product manufacturers, so the defensible version is that nobody sells observed, market-wide, cited spec position, not that the category is empty.

## H.2 Open questions only Asif can answer

Do Dodge SpecShare or ConstructConnect Analyze actually distinguish basis of design from listed alternate? Is the pipeline ingesting full specification documents or only permits, bids and awards? What share of the index entered at announcement stage versus permit stage? What did design partners actually say they would pay? Do manufacturers in lighting fund their agencies’ software, and would one accept a SpecIndex-exported registration record in place of its own web form? Has the maintenance fee on US 9,946,715 lapsed? And where is the filed Delaware certificate, since the copy in Drive is an unfiled template with placeholder fields?

## H.3 Facts still open in the canonical context

Design partner count and names, weekly active reps, beta signups, brand-mention accuracy, months worked on SpecIndex, and the raise amount. None of these should be estimated or filled with a plausible placeholder. They appear in the deck as bracketed tiles and nowhere else.

# I. Internal corrections (remove before this circulates externally)

*This section is a working list of edits to the canonical context file. It is not for investors and should be deleted from any external copy.*

The master context still says ConstructConnect is contractor-side and a different customer entirely. That is wrong: they sell a manufacturer product line today at a published $199 a month with specification share tracking by MasterFormat code, and Roper owns both ConstructConnect and Deltek Specpoint. Rewrite it as a named direct competitor and add RIB SpecLive, Parspec, Acelab and Hubexo. Change the pricing unit from roughly $149 per seat per month to territory pricing with unlimited seats. Use the locked AWS language: built Cloud Control API from zero into a top ten service, launched at re:Invent 2021, and ran product for CloudFormation across two million plus accounts, and drop the attributed revenue-impact figure, which invites a question that discounts every other number on the page. Dodge’s current public field-reporter figure is 400+, not 500+.

# J. Sources

**Competitors and products.** Acelab manufacturer pages and pricing tiers; Navitas Capital investment memo; Commercial Observer on the Series A; ENR on Materials Hub. Parspec about page, Series A and seed releases, knowledge-base pricing guide, Innovation Endeavors and Building Ventures memos, Capterra tiers, Graybar and SESCO case studies. Dodge SpecShare and Dodge One; S\&P Global on the selective default; Bloomberg Law on the debt talks; Dodge BBB profile. ConstructConnect Insight Analyze, pricing, master subscription agreement, acceptable use policy; Insight on TrustRadius; ConstructConnect BBB complaints; Roper FY2025 10-K. RIB SpecLive and its pricing page. Hubexo Lattira launch and North America unification. Anguleris and Gaudi. ARCAT. Building Radar.

**Precedent and channel.** Procore S-1 and S-1/A, pricing page, Construction Network, Q1 2026 transcript. CoStar via PriceLevel; ZoomInfo; Reonomy; LinkedIn Sales Navigator; PlanHub; Barbour ABI; Glenigan; Archbase; Cordell. NEMRA contracts whitepaper, marketing territories guideline, lighting division; Inside.Lighting on the AAILA absorption and on rep contract terms; Electrical Wholesaling on NEMRA26 and the Egret survey; EvoLucia rep agreement via Justia; OASIS specification registration and certified integration; Repfabric; HVACR Trends; MANA commission survey.

**Public data and standards.** SAM.gov opportunities API; UFGS via WBDG; VA PG-18-1 master specifications; Census C30 value of construction put in place; Census SUSB; CSI MasterFormat EULA; The Construction Standard pricing; Building Enclosure and Architect’s Newspaper on the CSI licensing revolt; AIA continuing education provider fees; Alexander Group sales benchmarks.

**Patents and law.** US 9,116,895; 9,529,868; 9,946,715; 9,785,638; 9,633,012; 10,540,401; US 2020/0159985 A1 (abandoned); US 12,242,990 and US 2025/0182017 (Buildsite); US 11,734,227, 11,249,942, 10,417,178 (Autodesk / Pype); US 2025/0252515 (KOPE AI); US 6,625,619 (expired); US 2014/0278268 (abandoned). USPTO fee schedule and subject-matter eligibility guidance; Examples 47 to 49; Recentive v. Fox; US Patent 7,679,637 LLC v. Google; Ex parte Desjardins; 37 CFR 1.29.

*Full URLs for every source above are held in the underlying research documents in Drive under SpecIndex \> Competitor and SpecIndex \> Patent.*