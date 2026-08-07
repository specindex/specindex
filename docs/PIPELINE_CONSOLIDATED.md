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
| **2. Documents** | pull every attachment | % with ≥1 document |
| **3. Classify** | detect true spec books, extract divisions | % with a confirmed spec doc |
| **4. Gap-fill** | targeted search **only where stage 3 found nothing** | recovery rate |

**Stage 1.5 exists because it was missed.** Austin had 2,000 records on disk and
zero rows in `projects`. An adapter that writes a file has not added a project.

**Search is stage 4, not stage 2.** Running it early cost a 0% hit rate over 10
projects; crawling once per source beats searching once per project by roughly
$17,000 at 494,327 document-less projects.

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
| **IV — The moat** | **11** | **Substitution ledger — REQUIRED wherever addenda exist** |

**Steps 8–11 are the ones that get skipped**, and they are the entire product.
Steps 1–7 produce a permit row; steps 8–11 produce a cited manufacturer claim.

## 4. How they compose

```
A1–A8 adapters ──▶ Stage 1 (projects)
                   Stage 1.5 (load into index)   ← the seam that keeps breaking
                   Stage 2 (documents)      = 11-step step 8
                   Stage 3 (classify)       = 11-step steps 9–10
                   Stage 4 (gap-fill)       = 11-step step 6, applied late
                                              11-step step 11 = the ledger
```

**Which to use:**

- Adding a **source platform** → build an adapter, judged by the checker.
- Adding a **jurisdiction on an existing platform** → a YAML config.
- Asking **"is this jurisdiction done?"** → the 11 steps, and steps 8–11 decide.
- Asking **"is the product real?"** → the funnel, measured at stage 3.

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

**A step succeeds into a place nothing reads from.** Four instances in one
session:

| seam | looked like | actually |
|---|---|---|
| Adapters → index | "pulled 2,000" | 0 rows in `projects` |
| Capture → database | 229 books in GCS | 0 visible to the classifier |
| Extraction → classifier | 269 docs flagged done | 0 divisions |
| Documents → record page | "no documents held" | document existed in another table |

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
