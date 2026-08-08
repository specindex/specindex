# SpecIndex demo — step by step, with talking points

Written 2026-08-07. Every number below was read from the live database or the
live API on that date; none is illustrative. Re-check the counts before a demo —
the corpus moves daily, and quoting a stale figure to a customer is the one
failure this document exists to prevent.

**Audience:** a building-product manufacturer's sales or specification team — a
Division 03 admixture rep, a Division 06 fastener rep, a Division 23 equipment
rep. Their job is to get their product named in the specification before the job
bids. Their fear is finding out after.

**Length:** 12 minutes of demo, then questions.

---

## Before you start (5 minutes, do not skip)

| check | how | if it fails |
|---|---|---|
| API is up | `curl -s https://specindex-api-gmm6irqe4q-uc.a.run.app/health` | stop; nothing else will work |
| The demo record loads | open the project URL below **signed in** | see "Signed out shows a teaser" |
| Numbers are current | run the count query in the appendix | update your script, do not round up |

**Sign in before the demo starts.** Signed out, the API returns a public teaser —
name, city, state, status, description, and nothing else. Documents, spec
citations and enrichment are all withheld. A signed-out window looks exactly like
an empty product, and it is the most likely way this demo fails.

---

## The demo record

**Maine State Prison Gatehouse Improvement Project** — BGS #3820, Warren, Maine.
Status: bidding. Owner: Maine Department of Corrections / Bureau of General
Services. Architect: Paul Designs Project PLLC.

<https://specindex.ai/projects/me-portal-maine-vertical-3820>

Use this one. It is the only record currently carrying every layer end to end.

---

## Step 1 — Open on the project record (2 min)

**Do:** land on the record. Point at the header: name, location, status, owner,
architect.

**Say:**
> "This is a live state job in Warren, Maine — bidding right now, bids due June
> 29th. The owner is the Maine Department of Corrections; the architect is Paul
> Designs Project PLLC. You could call them this afternoon."

**The point:** it is a real, current, actionable job — not an archive record.

**Do not say:** anything about how many projects we hold. Competitors claim more.
Volume is not the argument.

---

## Step 2 — The documents (2 min)

**Do:** scroll to the document list. Six documents:

| | |
|---|---|
| Specifications | 219 pages — the project manual |
| Addendum | the change record |
| Drawings | 37 pages |
| Bid Tabulation | who bid, and what they bid |
| Legal Ad | the advertisement |
| Notice To Contractors | the instructions to bidders |

**Say:**
> "These are the actual bid documents, pulled from Maine's own portal on the day
> they were posted. Not a summary of them — the documents."

**The point:** this is the thing a plan room charges for, sourced from the public
record.

**If asked where it comes from:** public government portals only. Maine's Bureau
of General Services publishes these openly. We never touch subscription plan-room
content.

---

## Step 3 — The spec citations (4 min — this is the demo)

**Do:** open the spec citations panel. Read two or three aloud with their page
numbers.

| manufacturer | division | section | page | position |
|---|---|---|---|---|
| Sika Corporation | 03 Concrete | 03 30 00 | 64 | named |
| Sika Corporation | 03 Concrete | 03 62 13 | 70 | named |
| Grainger | 05 Metals | 05 05 19 | 73 | approved vendor |
| McNICHOLS | 05 Metals | 05 51 00 | 87 | named |
| Simpson Strong-Tie | 06 Wood | 06 05 23 | 96 | basis of design |
| Simpson Strong-Tie, USP | 06 Wood | 06 10 00 | 100 | **"or approved equal"** |
| Canam Mass Timber | 06 Wood | 06 12 33 | 108 | fabricator |

**Say:**
> "Page 100 of the specification reads *'Simpson Strong-Tie, USP, or approved
> equal.'* If you sell structural connectors, that sentence is your whole
> quarter. Simpson is the basis of design. USP is already named as an equal. And
> 'or approved equal' means the door is open for a third — but only until the
> addenda close."
>
> "If you're Sika, you're specified in two sections. If you're a Sika competitor,
> you now know exactly which two sections to go after, and who to call."

**The point — say it in these words:**
> "We are not telling you a project exists. We are telling you **where you stand
> in the specification**, with the page number, so you can check us."

**The three positions, and why they matter:**

- **Locked / proprietary** — named with no substitution language. Displacing it
  means a formal substitution request.
- **Open to equals** — "or approved equal". The winnable ones.
- **Performance spec** — criteria, no manufacturer. Wide open.

**Every claim carries a page cite.** That is deliberate: the database refuses to
store a finding without a document and a page number, so an uncited claim about a
named company cannot exist in the product.

---

## Step 4 — The divisions (2 min)

**Do:** show the CSI divisions on the record — 16 for this project.

**Say:**
> "Set your territory to Division 06 and you see only the jobs where wood and
> connectors are actually in scope. Not every permit in Maine — the ones with
> your division in the specification."

**The point:** relevance filter, not a project firehose.

**If they don't know CSI divisions:** the UI leads with the trade name and keeps
the number secondary — "Wood, Plastics & Composites (06)". Say the trade, not the
number.

---

## Step 5 — Close (2 min)

**Say:**
> "Three things you can do with this that you can't do with a project feed:
> know which jobs name you, know which name your competitor with the door still
> open, and know it while the job is still bidding."

**Then stop talking.**

---

## Handling the honest questions

**"How many projects do you have?"**
> "597,284, but that's the least interesting number here and I'd rather not sell
> you on it — several competitors hold more. What they don't have is the page in
> the spec book where your product is named."

**"How many have this level of detail?"**
Answer straight. As of 2026-08-07: 589 CSI divisions across 16 states, 123
substitution-ledger rows. Depth is early and concentrated.
> "This is where we're thin and I won't pretend otherwise. Coverage is a
> state-by-division problem — a Division 23 rep in Texas would see a handful of
> projects today. Tell me your division and your states and I'll tell you exactly
> what you'd see, before you pay us anything."

That answer wins more than a dodge does, and a rep discovers the gap in week one
regardless.

**"Where does the data come from?"**
Public government sources — state facilities portals, DOT lettings, municipal
permit feeds, SAM.gov. Every document keeps its source URL and fetch date. No
plan-room content, ever.

**"Can you tell me who beat me on past jobs?"**
Only where the documents say so. Bid tabulations give bidders and prices. Do not
promise competitor win/loss analytics — we do not have that, and 166 of 597,284
projects carry any brand mention at all, mostly tenants rather than
manufacturers.

**"Is this real-time?"**
Documents are captured on a crawl cadence, not instantly. For 3820 the addendum
was captured the day it posted. Do not promise a latency number.

---

## What NOT to demo

- **Any Florida project value.** Miami-Dade reports $7.86B for a beauty-salon
  alteration. Never quote a Florida dollar figure.
- **A cross-filtering chart dashboard, and never a permit job-cost histogram.**
  Patent exposure (iSqFt, US 9,633,012). Lead with alerts, digests and the API.
- **Brand-vs-competitor visibility claims.** The data does not support it.
- **Any project you have not opened yourself in the last hour.** The Alabama
  ledger rows currently include case-variant duplicates (RECTORSEAL / RectorSeal)
  and some division misattributions — Eaton and Square D tagged Division 23 when
  they are electrical. Maine 3820 is clean. Demo Maine.

---

## Appendix — pre-demo verification

```bash
# API alive
curl -s https://specindex-api-gmm6irqe4q-uc.a.run.app/health

# The demo record returns the enriched name (signed out; teaser is expected)
curl -s https://specindex-api-gmm6irqe4q-uc.a.run.app/v1/projects/me-portal-maine-vertical-3820

# Current numbers -- read these, do not quote this file
psql "$DATABASE_URL" -c "
  SELECT (SELECT count(*) FROM projects)              AS projects,
         (SELECT count(*) FROM substitution_rulings)  AS ledger_rows,
         (SELECT count(*) FROM project_csi_divisions) AS divisions;"
```

**If the record looks empty:** check you are signed in before checking anything
else. That is the cause far more often than a data problem.

## Related

| file | |
|---|---|
| `PIPELINE_CONSOLIDATED.md` | how a record gets built — the 11 steps and the funnel |
| `COMPLIANCE_BRIEF.md` | **authoritative** on what may be claimed; read before improvising |
| `SPEC_DOCUMENT_COVERAGE.md` | which states and portals are live |
