# SpecIndex.ai — Technical Architecture

**Status:** Kickoff / MVP  
**Last updated:** 2026-07-23

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

**Phase 2:** Firestore as system of record, Cloud Functions for refresh/ingest, manufacturer accounts, brand alerts.

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
2. ✅ Georgia corpus v0 (Kimi-structured)  
3. 🔲 Static SpecIndex site + project search UI  
4. 🔲 Firebase Hosting init + first deploy  
5. 🔲 Custom domain `specindex.ai`  
6. 🔲 Firestore + authenticated manufacturer seats  
7. 🔲 Automated weekly capture job + brand NER  

---

## Open decisions (need owner input)

1. **Firebase project:** create new `specindex-ai` vs reuse an existing project?  
2. **DNS:** who controls `specindex.ai` registrar access for Firebase verification?  
3. **Auth timing:** waitlist-only at launch vs Google sign-in on day one?
