# The SpecIndex pipeline, consolidated

**One map of how data gets from a public portal to a cited manufacturer claim.**
Three overlapping frameworks existed — the 11-step jurisdiction process, the
4-stage spec funnel, and the A1–A8 adapters. This file shows how they fit and
which to use when.

---

## The short version

They are not competing. They operate at different levels:

| | answers | unit of work |
|---|---|---|
| **A1–A8 adapters** | *Where does data come from?* | a source platform |
| **4-stage funnel** | *What state is a project in?* | a project |
| **11-step process** | *How is a jurisdiction taken to done?* | a jurisdiction |

**Adapters feed the funnel. The 11-step process is the depth discipline applied
to any jurisdiction.**

---

## 1. Adapters — the supply line (A1–A8)

Scale by **platform, not jurisdiction**. One Accela adapter reaches 900+
agencies; one Legistar adapter reached 15 including all five NYC boroughs.

| # | Adapter | Covers | Status |
|---|---|---|---|
| **A1** | Socrata generic (SODA, YAML per dataset) | Austin, Seattle + 27 metro feeds | **built, verified** |
| **A2** | ArcGIS FeatureServer generic | Denver, Raleigh + 10 metros | **built, verified** |
| **A3** | Tier-1 state bid portals | 23 adapters, 19 states | **built, verified** |
| **A4** | SAM.gov Get Opportunities v2 | federal — GSA, VA, USACE | **built; 80 spec books from 200 solicitations** |
| **A5** | Accela Citizen Access | Dallas, King County + 900 agencies | **built, verified** |
| A6 | Bid Express | ~20 DOT states | **skipped** — no anonymous read path exists |
| A7 | Euna/Bonfire + OpenGov | universities, K-12, hospitals | not built |
| A8 | One-offs — Philadelphia Carto, Boston CKAN | remaining feeds | not built |

**Rules every adapter follows** (`docs/PORTAL_ADAPTER_CONTRACT.md`):
content-check never status-check · browser headers before declaring a source
dead · rate-limit ≥1s/host · emit rate and ETA · assert the next step can see
the output.

**Done means `check-portal-adapters.py` prints PASS**, not that an agent said so.
It must download a real document containing CSI or DOT SS/SP structure.

## 2. The 4-stage funnel — per project

| Stage | Does | Metric |
|---|---|---|
| **1. Projects** | enumerate solicitations/permits | projects indexed |
| **1.5 Load** | write into the index | **rows in `projects`** |
| **2. Documents** | pull every attachment | **% of LISTED attachments captured** |
| **3. Classify** | detect true spec books, extract divisions | % with a confirmed spec doc |
| **4. Gap-fill** | targeted search **only where stage 3 found nothing** | recovery rate |

**Stage 1.5 exists because it was missed.** Austin had 2,000 records on disk and
zero rows in `projects`. An adapter that writes a file has not added a project.

**Search is stage 4, not stage 2.** Running it early cost a 0% hit rate over 10
projects; crawling once per source beats searching once per project by roughly
$17,000 at 494,327 document-less projects.

**Stage 2's metric changed, because the old one caused data loss.** It used to be
"% with ≥1 document", and the capture runner carried a matching `break   # one
confirmed document per project is the funnel unit`. Maine 3820 listed six
documents — specification, addendum, drawings, legal ad, notice to contractors,
bid tabulation — and we kept one. The adapter had enumerated all six correctly;
the metric threw five away. **A metric that is satisfied by one document will be
implemented as one document.** Measure captured-against-listed.

## 3. The 11-step process — per jurisdiction

The depth discipline. **A jurisdiction is not done at step 5.**

| Phase | Step | |
|---|---|---|
| **I — Source discovery** | 1 | Discovery — Gemini, with context |
| | 2 | Verification — always live, never trusted |
| | 3 | Feedback loop |
| | 4 | Institutional memory |
| **II — Acquisition** | 5 | Provider wiring |
| | 6 | Direct project-level research fallback |
| | 7 | Data-quality gate / dedup |
| **III — Processing** | **8** | **Project-document pull — REQUIRED** |
| | **9** | **Document text extraction** |
| | **10** | **Project enrichment — REQUIRED** |
| **IV — The moat** | **11** | **Substitution ledger — REQUIRED wherever ANY spec document exists** |

**Steps 8–11 are the ones that get skipped**, and they are the entire product.
Steps 1–7 produce a permit row; steps 8–11 produce a cited manufacturer claim.

**Step 11 no longer says "wherever addenda exist" — that was wrong.** Measured on
Maine 3820 (2026-08-07): the addendum was one page, 563 characters of native
text, and contained zero occurrences of *substitution*, *or equal*, *approved* or
*rejected* — its entire content was a bid-date extension. All 8 cited findings
came from the **base spec book**: Sika (div 03, p64/p70), Grainger and McNICHOLS
(div 05, p73/p87), Simpson Strong-Tie + USP with an explicit "or approved equal"
(div 06, p100), Canam Mass Timber (div 06, p108).

Basis-of-design attribution is present in the base specification **at bid time**.
Addenda still matter — a *displaced* manufacturer is only visible there — but
expect a low hit rate per addendum, and never read "no addenda captured" as "no
rulings available".

## 4. The merged model — one stage list

The 11 steps and the 4 stages are not two processes. They are **procedure** and
**metrics** for the same work, in two vocabularies, which is why they read as
duplicates and why a stage's metric could drift from its step's instruction until
one of them destroyed data (see stage **S5** below).

They differ in **scope and frequency**, and that difference must survive the
merge:

- **11-steps 1–7 run ONCE per jurisdiction.** Onboarding a source.
- **11-steps 8–11 run FOREVER, per project.** This is what the funnel measures.

Flattening them into one sequence puts a one-time setup beside a continuous loop,
and then nobody knows which to re-run. So the merge is a single stage list where
each stage owns **exactly one metric and exactly one checker**.

### Loop A — onboard a source (once per jurisdiction)

| | stage | was | done when |
|---|---|---|---|
| **S1** | Discover + verify the source | steps 1–2 | a live probe returns a product-specific signature, baselined against a nonsense path |
| **S2** | Feed back + record | steps 3–4 | outcome sent to Gemini; a memory note exists |
| **S3** | Wire the provider | steps 5, 7 | `check-portal-adapters.py` **PASS** + document count matches the listing row |

### Loop B — run the corpus (continuously, per project)

| | stage | was | **the one metric** |
|---|---|---|---|
| **S4** | Enumerate + load | funnel 1 + 1.5 | **rows in `projects`** — never "records pulled" |
| **S5** | Capture documents | step 8, funnel 2 | **% of LISTED attachments captured** — never "% with ≥1" |
| **S6** | Extract + classify | steps 9–10, funnel 3 | divisions on a project; pages joinable **from the project** |
| **S7** | Ledger | step 11 | **cited findings per project** |
| **S8** | Gap-fill by search | funnel 4 (= step 6, late) | recovery rate, **only where S6 found nothing** |

**S5's metric is the whole reason to do this merge.** Funnel stage 2 said "% with
≥1 document" while step 8 said "pull every attachment". The runner implemented the
metric, not the step — `break` after the first document — and Maine 3820 lost five
of six documents including the addendum. One stage, one metric, no second
vocabulary to drift from.

### Where the efficiency actually is

Not in fewer stages — in **fewer reads of the same PDF**. S5, S6 and S7 each
fetch and re-parse the document today, so a 219-page spec book crosses the wire
and through a parser three times. Merge them into **one pass per document**:
fetch once, extract pages once, and run classification and ledger extraction off
that single in-memory text. Everything downstream already works off
`document_pages`; only the entry points differ.

The second win is **S8 stays last**. Searching before crawling cost a 0% hit rate
over 10 projects and would cost roughly $17,000 at corpus scale.

### Chaining rule (this is what keeps breaking)

**Each stage's exit check is the next stage's entry query.** Not a similar query —
the same one. Every seam in §6 below is a stage that verified its own write in its
own terms while the next stage read somewhere else: pages written to
`reference_documents` and read from `project_document_files`; documents written to
a fresh pull log and read from the biggest one.

**Which to use:**

- Adding a **source platform** → Loop A, judged by the checker.
- Adding a **jurisdiction on an existing platform** → a YAML config, then Loop A **S3**.
- Asking **"is this jurisdiction done?"** → Loop B, and **S5–S7** decide.
- Asking **"is the product real?"** → **S7**. Cited findings, not projects.

## 5. Where it actually stands

| | |
|---|---|
| Projects | 597,284 |
| Documents | 23,000+ |
| Extracted pages | 124,000+ |
| Portal spec books | 229 |
| Federal (SAM.gov) spec books | 80 |
| **CSI divisions** | **589** |
| **Divisions on a project** | **469** |
| States with spec detail | 16 |

**The honest gap:** coverage is a *state × division* cell problem. 469 divisions
spread over 16 states means a Div 23 rep in Texas sees ~4 projects. Depth per
state, not more states, is the work.

## 6. The failure mode this pipeline keeps hitting

**A step succeeds into a place nothing reads from.** Seven instances so far:

| seam | looked like | actually |
|---|---|---|
| Adapters → index | "pulled 2,000" | 0 rows in `projects` |
| Capture → database | 229 books in GCS | 0 visible to the classifier |
| Extraction → classifier | 269 docs flagged done | 0 divisions |
| Documents → record page | "no documents held" | document existed in another table |
| Spec book → its own pages | 219 pages extracted | 0 joinable from the project (**207 of 207 books**) |
| Config → step 11 | "ledger is empty, need more addenda" | the step had **never run once** — `Settings.from_env()` raised on a required key nothing read |
| Capture → extractor | spec book present and skipped | class re-derived from `title`, which the loader sets to the project *number* |

**The tell is a clean zero, and often the clock.** None of these errored. The
third was caught only because a run finished in 0.6 seconds: *0 findings from 1
document in 0.6s* is a bug, *0 findings from 1 document in 80s* is a fact. Check
elapsed time and input count before believing any zero.

**Run the whole pipeline on one known-good project.** All three of the newest
seams were found by taking Maine 3820 through all 11 steps — not by running one
step across many projects, which is how they stayed hidden.

**Every step now ends by reading back what it wrote.** A run is not finished when
it exits — only when its output has been read.

## 7. Related files

| file | |
|---|---|
| `AGENT_STRATEGY.md` | the 11 steps in full, with incident history |
| `SPEC_DOCUMENT_COVERAGE.md` | the funnel + 100 link-checked state portals |
| `PORTAL_ADAPTER_CONTRACT.md` | the five rules every adapter follows |
| `COMPLIANCE_BRIEF.md` | authoritative; **read before adding a source** |
| `.claude/skills/spec-pull/SKILL.md` | the runnable skill |
