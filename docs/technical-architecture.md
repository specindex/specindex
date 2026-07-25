# SpecIndex.ai — Technical Architecture

**Status:** MVP + Phase 1 backend live  
**Last updated:** 2026-07-25

---

## Goals

1. Ship a manufacturer-facing web product at **specindex.ai**
2. Host on **Firebase** (Hosting first; Firestore + Functions as data grows)
3. Seed with a **Georgia commercial project corpus** captured via AI-assisted research (Kimi) + curated public sources
4. Support core loops: project search → project detail / specs → brand mention check → visibility compare

---

## High-level architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Clients (Web)                          │
│         SpecIndex marketing + product UI (static)          │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼────────────────────────────────┐
│                 Firebase Hosting (CDN + SSL)               │
│              Custom domain: specindex.ai                   │
└───────────────────────────┬────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌────────────────────┐
│ Static assets │   │ Firestore     │   │ Cloud Functions    │
│ HTML/JS/CSS   │   │ projects,     │   │ ingest, brand NER, │
│ project JSON  │   │ brands, users │   │ alerts, Kimi jobs  │
└───────────────┘   └───────────────┘   └────────────────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │ External sources   │
                  │ News, public DRI,  │
                  │ owner/architect    │
                  │ releases, Kimi API │
                  └────────────────────┘
```

**MVP phase (now):** static Next.js export on Firebase Hosting, project data as versioned JSON in the repo (`data/`), client-side search/filter. No auth required for public browse.

**Phase 1 backend (built 2026-07-25):** Postgres (Cloud SQL) as a second, queryable system of record alongside the static JSON, fronted by a read-only FastAPI service on Cloud Run. The public site still reads from build-time JSON — this backend exists so later phases (ingest pipelines, spec extraction, manufacturer accounts) have a real database to write to instead of hand-editing JSON files. See "Backend infrastructure" below.

**Phase 2:** Firestore or continued Postgres expansion as system of record, Cloud Functions/ingest pipelines for automated refresh, manufacturer accounts, brand alerts.

---

## Backend infrastructure (Phase 1 — built)

```
┌──────────────────────────┐
│  data/national-commercial-  │
│  projects.json (652 rows)   │
└─────────────┬────────────┘
              │ scripts/load-corpus-to-postgres.py
              ▼
┌──────────────────────────┐
│  Cloud SQL — specindex-db   │
│  Postgres 16, db-f1-micro   │
│  project: specindex-ai      │
│  region: us-central1        │
└─────────────┬────────────┘
              │ Cloud SQL Auth Proxy / unix socket
              ▼
┌──────────────────────────┐
│  Cloud Run — specindex-api  │
│  FastAPI read API (api/)    │
│  GET /health, /v1/stats,    │
│  /v1/projects, /v1/projects/│
│  {id}                       │
└──────────────────────────┘
```

**Local dev:** `docker-compose.yml` runs Postgres + the API together (`npm run db:up`); requires Docker (not installed on this machine as of setup — GCP path was used directly instead).

**GCP setup automation:** `scripts/setup-phase1-gcp.sh` (invoked via `npm run db:setup-gcp`) creates the Cloud SQL instance, loads the corpus, and deploys the API to Cloud Run. Requires `--edition=ENTERPRISE` on `gcloud sql instances create` for the `db-f1-micro` tier (the `specindex-ai` project's default edition is Enterprise Plus, which doesn't support shared-core tiers) and `gcloud auth application-default login` (separate from `gcloud auth login`) before the Cloud SQL Auth Proxy step will authenticate. Full walkthrough in `docs/PHASE1-DATABASE-SETUP.md`.

**Status (2026-07-25): live and verified.** 652 rows loaded into `specindex-db`; `specindex-api` deployed to Cloud Run at `https://specindex-api-gmm6irqe4q-uc.a.run.app`, confirmed serving real queries (`/health`, `/v1/stats`, `/v1/projects`).

**Not yet wired up:** the Next.js site does not read from this API yet — it still builds from static JSON. Connecting the site (or a future ingest pipeline) to `specindex-api` is open work.

---

## Hosting decision

| Option | When |
|---|---|
| **Firebase Hosting (classic)** | MVP — static site / SPA, full control of build, custom domain |
| Firebase App Hosting | Later if we need Next.js SSR / server actions in production |

MVP uses **Hosting classic** with `output: 'export'` from Next.js (or equivalent static build), matching a simple deploy path and SSL on `specindex.ai`.

---

## Firebase project recommendation

Create a **new** Firebase project dedicated to SpecIndex (do not reuse `foundation-presales-demo` or `revere-demo-portal`).

Suggested IDs:

- `specindex-ai` (preferred)
- `specindex-prod` / `specindex-dev` if splitting environments early

Enable:

1. Hosting (+ custom domain `specindex.ai` / `www`)
2. Firestore (phase 2)
3. Cloud Functions / Cloud Run (phase 2)
4. Authentication (phase 2 — email / Google for manufacturer seats)
5. Secret Manager for `MOONSHOT_API_KEY` (never commit)

---

## Data model (v0 → v1)

### Project (core)

```ts
type Project = {
  id: string;                 // slug
  name: string;
  city: string;
  county: string;
  state: "GA";
  status: "planning" | "design" | "permitting" | "bidding" | "under_construction";
  projectType: string;
  estimatedValueUsd: number | null;
  squareFootage: number | null;
  owner: string;
  architect: string;
  generalContractor: string;
  description: string;
  keySpecs: string[];
  mentionedBrands: string[];  // detected brands
  competitorWatch: string[];  // product categories
  sources: { title: string; url: string }[];
  openFor: string;
  updatedAt: string;          // ISO
  geography: "Georgia";
};
```

### Brand profile (phase 2)

```ts
type Brand = {
  id: string;
  name: string;
  aliases: string[];
  categories: string[];       // e.g. lighting, HVAC
  manufacturerId: string;
};
```

### Brand mention (phase 2)

```ts
type BrandMention = {
  projectId: string;
  brandId: string;
  status: "mentioned" | "not_mentioned" | "unspecified";
  confidence: number;
  excerpts: { text: string; sourceUrl?: string }[];
  checkedAt: string;
};
```

### Collections (Firestore)

- `projects/{projectId}`
- `brands/{brandId}`
- `mentions/{projectId}_{brandId}`
- `manufacturers/{orgId}`
- `alerts/{alertId}`

MVP stores projects in `data/georgia-commercial-projects.json` and copies into `public/data/` at build time.

---

## Ingestion pipeline

```
Public sources ──► Research agent (Kimi + web) ──► Normalize JSON
                                              │
                                              ▼
                                    Human / rule QA
                                              │
                                              ▼
                         data/georgia-commercial-projects.json
                                              │
                         ┌────────────────────┴────────────────────┐
                         ▼                                         ▼
                  Static site build                        Firestore sync (later)
```

**Beachhead script:** `scripts/capture-georgia-projects.py`  
- Calls Moonshot `kimi-k3` to structure research  
- Writes `data/georgia-commercial-projects.json`  
- Key via env `MOONSHOT_API_KEY` (Secret Manager in prod)

**Refresh cadence (target):** weekly for Georgia; daily for hot projects once Functions exist.

---

## Application structure (MVP)

```
specindex/
  app/                    # Next.js App Router pages
  components/             # UI
  data/                   # Source corpus (JSON)
  public/data/            # Served corpus
  docs/                   # Strategy + architecture
  scripts/                # Capture / deploy helpers
  firebase.json
  .firebaserc
```

### Primary routes

| Route | Purpose |
|---|---|
| `/` | Brand hero + CTA into search |
| `/projects` | Search / filter Georgia open projects |
| `/projects/[id]` | Spec-oriented project detail |
| `/visibility` | Brand mention + compare (demo with seeded brands) |
| `/about` | Product story |

---

## Brand visibility (MVP approach)

1. Seed `mentionedBrands` from public coverage during capture
2. On `/visibility`, manufacturer selects a brand (or types one)
3. Client scans project corpus for mentions / category fit
4. Show coverage % and project list (mentioned vs opportunity)

Phase 2 upgrades to PDF/spec NER via Cloud Functions + Kimi, with confidence and excerpts.

---

## Security & compliance

- No secrets in git; `.env.local` / Secret Manager only
- Public project pages: only public-source-derived fields
- Do not scrape paywalled plan rooms without license
- Attribute sources on every project record
- Firestore rules (phase 2): public read for published projects; write admin-only; manufacturer private data scoped by auth

---

## CI/CD

GitHub Actions deploys Firebase Hosting automatically (set up 2026-07-25 via `firebase init hosting:github`):

- **PR preview:** `.github/workflows/firebase-hosting-pull-request.yml` — builds and deploys a temporary preview channel on every PR, posts the URL as a PR comment. Verified working on [specindex/specindex#1](https://github.com/specindex/specindex/pull/1).
- **Live deploy:** `.github/workflows/firebase-hosting-merge.yml` — builds and deploys to the live `specindex-ai` Hosting site on every push to `main`.
- Auth: a GCP service account (`github-action-<id>@specindex-ai.iam.gserviceaccount.com`) stored as the `FIREBASE_SERVICE_ACCOUNT_SPECINDEX_AI` secret in the GitHub repo.

Manual `npm run deploy` still works as a fallback.

**Repo:** `https://github.com/specindex/specindex` (migrated from `Influentialinternal219/specindex` on 2026-07-25; authenticated locally via `gh` CLI as the `specindex` GitHub account).

---

## Custom domain cutover

1. Deploy Hosting to Firebase default URL
2. Add custom domain `specindex.ai` in Firebase Hosting
3. Point DNS (A/AAAA or CNAME per Firebase instructions) at registrar
4. Wait for SSL provisioning
5. Optional: redirect `www` → apex

---

## Environments

| Env | Firebase project | Domain |
|---|---|---|
| Preview | hosting preview channels | `*.web.app` |
| Production | `specindex-ai` | `specindex.ai` |

---

## Near-term engineering milestones

1. ✅ Product strategy + this architecture doc
2. ✅ Georgia corpus v0 (Kimi-structured), expanded to 126 projects / 10 states
3. ✅ Static SpecIndex site + project search UI
4. ✅ Firebase Hosting init + first deploy — live at specindex.ai
5. ✅ Custom domain `specindex.ai`
6. ✅ GitHub Actions CI/CD (PR previews + live deploy on merge to `main`)
7. ✅ Phase 1 Postgres (Cloud SQL) + read API (Cloud Run) — live and verified; schema v2 (`db/migrations/002`, `003`) adds numeric surrogate keys, external ID crosswalk, and a `project_csi_divisions` fact table — see `docs/DATA_SCHEMA_V2.md`
8. 🔲 Complete corpus capture for remaining 40 states
9. ✅ Wire the Next.js site to `specindex-api` instead of static JSON — `lib/projects.ts` now paginates the live API at `next build` time (site stays a static export; verified with a full local build against the live API — 652 project pages + sitemap generated correctly)
10. 🚧 Spec book extraction pipeline (PyMuPDF → CSI division LLM pass → cited JSON) — see `docs/CONTEXT.md`. Built: `scripts/extract-spec-book.py`, parsing/chunking layer verified against a synthetic PDF. Not yet run against a real spec book or a live LLM call (see item 13).
11. 🔲 Firestore or Postgres-backed authenticated manufacturer seats
12. 🔲 Automated permit/press capture job + brand NER
13. 🔲 Source a real spec book PDF and run `scripts/extract-spec-book.py` end-to-end against the live Anthropic API — the LLM classification layer is built but has never been exercised (no `ANTHROPIC_API_KEY` in the dev environment used to build it)
14. 🔲 Wire `api/main.py` to expose the schema v2 columns (`project_sk`, `external_ids`, `csi_division_codes`, `status_code`) in API responses — the live API still only returns the v1 field shape
15. 🔲 Fix Chicago-style bundled-permit rows — at least one row conflates 60+ separate city permits into single `owner`/`architect`/`description` fields (see the Chicago sample in `docs/DATA_SOURCES.md`); needs either a per-permit split or a dedicated multi-permit representation

---

## Open decisions (need owner input)

1. **Auth timing:** waitlist-only at launch vs Google sign-in on day one?
2. **System of record:** converge on Postgres as the single source of truth (retiring hand-edited JSON) vs keeping JSON as the primary and Postgres as a read replica for API consumers?
