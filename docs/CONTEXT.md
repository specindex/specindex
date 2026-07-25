# SpecIndex — Project Context

Last updated: 2026-07-24

This document captures the current state of the SpecIndex repository, product direction, data pipeline strategy, and work completed to date.

---

## What SpecIndex Is

SpecIndex is specification intelligence for **building product manufacturers**. It helps manufacturer reps find open commercial construction projects, check whether their brand is mentioned in public coverage, and identify category-fit opportunities before the spec window closes.

**Beachhead:** Georgia (54 projects, fully curated). Expanding nationwide.

**Live site:** [specindex.ai](https://specindex.ai) (Firebase Hosting, static Next.js export)

**Stack:**
- Next.js 15 (static export → `out/`)
- React 19, Tailwind 4
- Firebase Hosting
- Python scripts for data capture and document harvesting
- Client-side search/filtering over JSON corpus

---

## The Three Problems (Separate Pipelines)

LLMs fit differently into each layer. Do not conflate them.

### 1. Discovering Projects (Sourcing)

**The hard part is sourcing, not the LLM.**

Legitimate public feeds:
- Government permit / plan-review portals (county/city building departments)
- SAM.gov and state/local procurement boards (public work only)
- News and press releases (groundbreakings, CRE press, investor announcements)
- LinkedIn / trade-press signal

**Where the LLM earns its keep:** turning messy natural-language text (permit filing, news blurb, press release) into structured fields — project name, address, type, estimated value, stage, owner, architect of record. Classification/extraction task; LLMs are genuinely good at this vs. regex on noisy text.

**Legal boundary (critical):** ConstructConnect's Insight/plan-room data and Dodge's proprietary project database are **off the table**. No scraping either, no replicating internal methods from prior employment. Build the sourcing layer on **public data only**. Review separation agreement / non-compete language before architecting anything that touches plan-room-style data.

### 2. Spec Book Extraction (Highest Value, Build First)

This is where the "get my product specified" signal lives.

Construction spec books (CSI MasterFormat, Divisions 00–49) are almost always vector-text PDFs:

1. **Extract text/tables first** with a cheap deterministic parser (PyMuPDF, pdfplumber, or Azure Document Intelligence / AWS Textract for tabular schedules). Do not burn LLM tokens on OCR you don't need.
2. **Run a structured-extraction LLM pass** per section, prompted against CSI division schema (e.g. Division 09 Finishes, Division 23 HVAC). Pull basis-of-design product, approved manufacturers list, "or equal" substitution language, model numbers.
3. **Force structured output** (JSON schema / tool-use) so it drops into the data model.
4. **Store a page/section citation** with every extracted fact. "Your competitor is specified on this project" must be click-through-verifiable — one wrong extraction burns credibility permanently.

### 3. Engineering Drawings (Under-Scope for MVP)

Two cases:

| Type | Approach |
|------|----------|
| **Born-digital** (DWG/BIM/vector PDF) | Parse file structure (IFC schema, Revit API, vector-PDF text/block layer). Do not use vision LLM. |
| **Scanned/raster** | Vision LLM only for title blocks and schedule tables (door, equipment, finish schedules). Full-sheet floor-plan symbol counting is v2/v3, not MVP. |

---

## Sourcing Layer — Sequenced Priority

No single source covers everything. Rank for building SpecIndex's sourcing layer:

### Tier 1 — Best Starting Point: Municipal/County Building Permit Data

Three reasons it beats everything else for MVP:

1. **Legally clean** — permit records are public by law in the US. No scraping-a-competitor risk.
2. **Covers exactly what you want** — private commercial development, not just public bid work (unlike SAM.gov, which is federal-only).
3. **Deceptively tractable at scale** — thousands of municipalities look fragmented, but most run on a small handful of platforms. Build **one scraper/integration per platform**, not per city:

| Platform | Notes |
|----------|-------|
| Accela Citizen Access | Atlanta, many cities/counties |
| Tyler Technologies EnerGov | Common mid-size cities |
| CityView | Municipal permit systems |
| OpenGov | Growing municipal stack |

**Open-data bonus:** Larger cities run Socrata/CKAN portals with REST APIs — zero scraping:
- NYC Open Data
- LA GeoHub
- Chicago Data Portal

**Engineering priority:** permits first — legal, structured, scalable via platform reuse.

### Tier 2 — Early-Signal Complement: Local Business Journals + Press Releases

- American City Business Journals (ACBJ) — every major metro, dedicated RE/construction reporters
- PR Newswire / Business Wire — groundbreaking and topping-out announcements

Catches projects **before** permit records (Building Radar's "early-stage" edge). Noisier; needs heavier LLM classification to become usable records.

### Tier 3 — Evaluate, Don't Build (Yet)

**Dodge Construction Network** licenses/API-sells project data (~636K projects/year). If licensing is feasible at this stage, could buy years of crawler-building time. Worth a direct outreach call **in parallel** with building the permit pipeline — not instead of it.

### Off the Table

- ConstructConnect proprietary data
- Dodge plan-room data
- Anything that looks like scraping either or reusing internal ConstructConnect pipeline knowledge

---

## Practical Build Sequence

Given a small team:

1. **Spec book extraction** — highest signal-to-effort, plain text, directly answers "can I get specified here"
2. **Project sourcing/classification** — breadth (permits → press)
3. **Schedule/title-block extraction from drawings** — narrow scope
4. **Full drawing computer vision** — deferred; do not promise in v1

---

## Data Model

### Project Schema (`lib/types.ts`)

Each project record:

```json
{
  "id": "ga-troup-county-data-center",
  "name": "Troup County Data Center (DRI filed)",
  "state": "GA",
  "city": "Troup County",
  "county": "Troup",
  "status": "planning",
  "project_type": "industrial",
  "estimated_value_usd": null,
  "square_footage": null,
  "owner": "",
  "architect": "",
  "general_contractor": "",
  "opened_or_announced_date": "2026-07-22",
  "description": "...",
  "key_specs": [],
  "mentioned_brands": [],
  "competitor_watch": ["switchgear", "generators"],
  "sources": [{ "title": "...", "url": "..." }],
  "open_for": "Pre-development — early MEP specs."
}
```

### Corpus Structure

| Path | Purpose |
|------|---------|
| `data/states/{code}.json` | Per-state project files (lowercase code, e.g. `ga.json`) |
| `data/national-commercial-projects.json` | Merged national corpus |
| `public/data/national-commercial-projects.json` | Copy served to Next.js static site |
| `data/jurisdictions/state-template.json` | Template for new state files |
| `data/documents/georgia/` | Harvested HTML snapshots + PDFs per GA project |
| `data/documents/fulton-county/` | Fulton County forms + Centennial Yards site plan |

---

## Current Data Coverage (2026-07-24)

**10 / 50 states captured · 126 projects merged · 93 in last 90 days**

| State | Projects | Notes |
|-------|----------|-------|
| GA | 54 | Fully curated beachhead |
| FL | 13 | AL–FL batch |
| CA | 12 | |
| AL | 8 | |
| AZ | 8 | |
| CT | 8 | |
| CO | 7 | |
| AR | 6 | Thin — mega data-center/solar only |
| AK | 5 | Thin — few announcements in window |
| DE | 5 | Thin |

**Missing (40 states):** HI, ID, IL, IN, IA, KS, KY, LA, ME, MD, MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, OH, OK, OR, PA, RI, SC, SD, TN, TX, UT, VT, VA, WA, WV, WI, WY

**Date window:** 2026-04-26 to 2026-07-24 (last 90 days)

**Capture agents:** Parallel sub-agents assigned by state batch (HI–MD, MA–NJ, NM–SC, SD–WY). Re-run and merge when complete.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/merge-national-corpus.py` | Merge `data/states/*.json` → national corpus |
| `scripts/migrate-georgia-to-states.py` | One-time GA → `data/states/ga.json` migration |
| `scripts/capture-national-projects.py` | Orchestrator; `--status`, `--merge-only` |
| `scripts/expand-georgia-corpus.py` | Merge/enrich Georgia projects |
| `scripts/fetch-georgia-documents.py` | Crawl GA project source URLs → HTML + linked PDFs |
| `scripts/fetch-fulton-documents.py` | Fulton County forms + known project PDFs |
| `scripts/capture-georgia-projects.py` | Kimi API structuring from research notes |

**Typical workflow:**
```bash
python3 scripts/capture-national-projects.py --status
python3 scripts/merge-national-corpus.py
npm run build
npm run deploy   # requires Firebase auth + user approval
```

---

## Website (Completed Improvements)

### Navigation & UX
- Mobile hamburger menu in `SiteHeader.tsx`
- Projects + Visibility in main nav
- Demo form → functional `mailto:` submission with success state

### Search & Filters (`ProjectSearch.tsx`)
- Filter by **state**, county, status, type, product category
- Counties scoped to selected state
- Dynamic status dropdown from corpus

### Data-Driven UI
- Homepage stats from live corpus (project count, 90-day activity, state/county counts)
- `ProductMock` uses computed top counties + visibility snapshot
- Visibility panel uses brands actually in corpus (Hilton, Hyundai, Costco, etc.)

### SEO
- `app/sitemap.ts`, `app/robots.ts`
- Open Graph + Twitter metadata in `app/layout.tsx`

### Project Detail
- `opened_or_announced_date` display
- State name in location line
- Back navigation

---

## Document Harvesting (Georgia)

Downloaded to `data/documents/`:

| Category | Count / Notes |
|----------|---------------|
| HTML snapshots | Per-project source pages |
| Linked PDFs | From source URL crawls (often news/regulatory, not spec books) |
| Fulton County forms | Commercial plan review instructions, permit application checklist |
| Engineering drawings | **One site plan:** Centennial Yards (`centennial-yards-site-plan-pdf-cim-property-capsule.pdf`) |

**Finding:** Most project-specific architectural/engineering drawings live on city Accela portals (e.g. Atlanta Planning/Building), not county sites. Fulton County Public Works only handles the Fulton Industrial Business District; most Fulton corpus projects are in incorporated cities.

**Accela search targets documented in** `data/documents/fulton-county/index.json`:
- Teachers Village (Fairlie St)
- Motto Hilton (512 W Peachtree)
- Overlook at Garson
- Centennial Yards Elliott hotel

---

## Deployment

- **Hosting:** Firebase (`firebase.json` → `out/`)
- **Deploy:** GitHub Actions auto-deploys on push to `main` (PR previews on every PR); `npm run deploy` still works as a manual fallback
- **Git remote:** `https://github.com/specindex/specindex` (migrated from `Influentialinternal219/specindex` on 2026-07-25)
- **Branch:** `cursor/expand-corpus-filmore-site` (pushed; open as PR #1 into `main` for testing CI/CD)
- **Backend:** Postgres (Cloud SQL `specindex-db`) + FastAPI read API (Cloud Run `specindex-api`) — see `docs/PHASE1-DATABASE-SETUP.md`, not yet wired into the site build

---

## Legal & Competitive Notes

1. **Public permit data only** for automated sourcing MVP
2. **No ConstructConnect / Dodge plan-room scraping**
3. **Dodge licensing** — evaluate via direct outreach, parallel to building own pipeline
4. **Separation agreement** — review before any architecture touching proprietary competitor data or internal pipeline knowledge
5. **Spec citations** — every LLM-extracted spec fact needs page/section provenance for buyer trust

---

## Open Work

- [ ] Complete capture for remaining 40 states
- [ ] Re-sequence capture agents to **permits first** (Socrata APIs + Accela platform adapters), then press/news
- [ ] Build Tier 1 permit platform adapters (Accela, EnerGov, Socrata)
- [ ] Build Tier 2 press feed + LLM classification layer
- [ ] Build spec book extraction pipeline (PyMuPDF → CSI division LLM pass → cited JSON)
- [ ] Title-block / schedule extraction from drawings (MVP scope only)
- [ ] Wire spec extractions into project detail pages on site
- [ ] Wire the live site to `specindex-api` (Postgres) instead of build-time JSON
- [x] ~~GitHub push auth setup~~ — done 2026-07-25 via `gh` CLI, repo migrated to `specindex/specindex`

---

## Key File References

```
specindex/
├── app/                          # Next.js pages
├── components/                   # UI (ProjectSearch, VisibilityPanel, etc.)
├── lib/
│   ├── types.ts                  # Project + ProjectCorpus types
│   ├── projects.ts               # Loads national-commercial-projects.json
│   ├── stats.ts                  # State/county/visibility helpers
│   └── format.ts                 # stateName(), formatUsd, brandMentioned, etc.
├── data/
│   ├── states/                   # Per-state JSON (source of truth)
│   ├── national-commercial-projects.json
│   ├── jurisdictions/state-template.json
│   └── documents/                # Harvested PDFs and manifests
├── scripts/                      # Capture, merge, document fetch
└── docs/
    └── CONTEXT.md                # This file
```

---

## Reference Artifact

Pipeline architecture discussion reference (Claude artifact — may require login):
https://claude.ai/code/artifact/bbb25833-3961-4b09-8c91-820ab133d98d
