# SpecIndex.ai — Product Strategy

**Working title:** SpecIndex  
**Domain:** [specindex.ai](https://specindex.ai)  
**One-liner:** The brand-visibility and project-intel layer for building-product manufacturers.

---

## Problem

Building-product manufacturers (HVAC, lighting, glazing, flooring, doors, hardware, MEP equipment, finishes) win work when they are **named in the spec** early — or when they can still influence an open project before bidding closes.

Today that intelligence is fragmented across:

- Plan rooms and bid boards
- Spec PDFs buried in SharePoint / email
- Dodge / ConstructConnect-style databases that optimize for contractors, not manufacturers
- Manual “are we written in?” chasing by reps

Manufacturers need a single place to **find open projects**, **read the relevant specs**, **see if their brand is mentioned**, and **compare visibility vs competitors**.

---

## Vision

SpecIndex becomes the default **specification intelligence platform** for manufacturers:

1. **Discover** open commercial projects by market, type, stage, and trade.
2. **Inspect** project detail: owner, design team, GC, value, schedule stage, and key spec sections.
3. **Detect** brand mentions (own brand + competitors) across specs and public project coverage.
4. **Compare** share-of-spec / brand visibility within a geography or vertical.

Beachhead: **commercial projects in Georgia**, then expand state-by-state across the Southeast and nationally.

---

## Target users

| Persona | Job to be done |
|---|---|
| Manufacturer sales / territory rep | Find open projects where my products can still win |
| Spec / marketing manager | Measure brand mention rate vs competitors |
| Product manager | Spot which CSI divisions and project types we miss |
| Agency / independent rep firm | Cover a multi-brand book of business across a state |

Primary buyer: mid-market and enterprise building-product manufacturers with active A&E specification programs.

---

## Core product loops

### 1. Project search
Filter open commercial projects by geography, status (planning / design / bidding / permitting / under construction), project type, value, and trade relevance.

### 2. Spec detail
Project page with structured fields + linked source docs. Highlight CSI divisions and product categories manufacturers care about.

### 3. Brand mention detection
For a selected brand (and competitor set), show:

- Mentioned / not mentioned / unspecified
- Where mentioned (section, product type)
- Confidence + source excerpt

### 4. Visibility compare
Market-level dashboard: mention rate, competitive share, trend by county / project type / stage.

---

## Beachhead: Georgia commercial

**Why Georgia first**

- Dense commercial pipeline (Atlanta metro + Savannah / Augusta / Columbus)
- Strong industrial, healthcare, education, mixed-use activity
- Manageable geography for manual + AI-assisted capture while product proves value

**MVP data goal:** capture and refresh **all open commercial projects in Georgia** that manufacturers can still influence (specs not locked, bidding open, or substitutions still possible).

Initial capture method: AI-assisted web research (Kimi) + curated public sources, normalized into SpecIndex project records.

---

## Positioning

**Category:** Spec & brand intelligence for building products  
**Not:** full plan-room replacement, full estimating suite, or contractor bid management

**Promise:** “Know which Georgia projects are open, what’s specified, and whether your brand is in — before the window closes.”

---

## Differentiation

| Capability | Plan rooms | Dodge-style | SpecIndex |
|---|---|---|---|
| Open project discovery | Partial | Strong | Strong (manufacturer lens) |
| Spec detail for reps | Weak | Medium | Strong |
| Brand mention detection | Rare | Rare | Core |
| Competitive visibility | No | Limited | Core |
| Manufacturer workflow | No | Bolt-on | Native |

---

## Go-to-market (phase 1)

1. Seed Georgia commercial project corpus
2. Launch manufacturer-facing site on Firebase Hosting at **specindex.ai**
3. Offer free Georgia visibility scan for first 10 manufacturers (lead magnet)
4. Convert to paid seats: search + brand alerts + competitor compare
5. Expand to FL / NC / SC / TN / TX after retention signal

---

## Monetization (initial)

- **Free:** limited Georgia project browse + one brand check / week
- **Pro:** unlimited Georgia search, brand alerts, competitor compare
- **Team:** multi-brand books, territory seats, export / CRM sync
- Later: national coverage, API, white-label for rep agencies

---

## Success metrics (90 days)

- ≥ 200 open Georgia commercial projects with structured records
- ≥ 50 manufacturer waitlist / trial signups
- ≥ 10 weekly active manufacturer users returning for brand checks
- Qualitative: reps say SpecIndex replaced at least one manual search habit

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Spec PDFs hard to obtain legally | Start with public coverage + owner/architect releases; add licensed feeds later |
| Stale project status | Refresh cadence + source timestamps + “verify” UX |
| Brand NER false positives | Human-in-loop review for beachhead; confidence scores |
| Data licensing | Prefer public sources; clear attribution; no scrape of paywalled plan rooms |

---

## Near-term roadmap

**Now (this kickoff)**

- Product strategy + technical architecture
- Georgia project corpus v0 via Kimi research
- Marketing + product MVP site on Firebase → custom domain specindex.ai

**Next**

- Brand profiles + mention scoring
- Alerts (email) when a brand appears / disappears on a project
- Spec document upload + AI extraction pipeline
- Southeast expansion

---

## Brand principles (site)

- Authoritative, industrial-modern — not purple-glow SaaS cliché
- Brand name **SpecIndex** is hero-level on first viewport
- One job per section; search is the primary action
- Real project data as the visual/product proof, not abstract gradients alone
