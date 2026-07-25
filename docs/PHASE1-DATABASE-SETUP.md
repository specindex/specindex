# Phase 1 Database Setup — Step-by-Step Guide

**Purpose:** Put SpecIndex project data in PostgreSQL on Google Cloud, with a read API on Cloud Run.  
**Date created:** 2026-07-25  
**GCP project:** `specindex-ai`  
**Account:** `asif@specindex.ai`

Use this doc as your checklist while setting up, and as reference afterward.

---

## What you are building (plain English)

Today the website reads project data from JSON files in the repo at build time. That stays the same for the public site.

Phase 1 adds a **second copy** of that data in a real database:

```
JSON files (repo)          ← still powers the live website
       ↓
PostgreSQL (Cloud SQL)     ← new system of record (652 projects)
       ↓
Cloud Run API              ← new read-only API to query the database
```

| Thing | Name in GCP | What it does |
| --- | --- | --- |
| Database | Cloud SQL instance `specindex-db` | Stores all projects in Postgres |
| API | Cloud Run service `specindex-api` | HTTP endpoints: health, stats, list projects |
| Region | `us-central1` | Where both run |

**The live site does not change yet.** This is infrastructure you can test and build on.

---

## Before you start

Check each box:

- [ ] Mac with terminal access
- [ ] Repo cloned: `/Users/ahussain2373/Projects/specindex`
- [ ] Google account: `asif@specindex.ai`
- [ ] Firebase project `specindex-ai` exists (it does — same GCP project)
- [ ] **Billing enabled** on `specindex-ai` (Cloud SQL requires it — ~$10–15/mo for the smallest tier)
- [ ] About 15–20 minutes (first Cloud SQL create takes 5–10 min)

---

## Step 1 — Install the Google Cloud CLI

Open Terminal and run:

```bash
brew install google-cloud-sdk
```

If you don't use Homebrew, install from: https://cloud.google.com/sdk/docs/install

Verify:

```bash
gcloud --version
```

You should see a version number, not "command not found".

---

## Step 2 — Log in and select the project

```bash
gcloud auth login
```

A browser window opens. Sign in as **asif@specindex.ai**.

Then:

```bash
gcloud config set project specindex-ai
gcloud config get-value project
```

Expected output: `specindex-ai`

---

## Step 3 — Confirm billing is on

Cloud SQL will not create without billing.

1. Open https://console.cloud.google.com/billing/projects?project=specindex-ai
2. Confirm a billing account is linked to `specindex-ai`
3. If not, link one in the console

---

## Step 4 — Go to the repo and set a database password

```bash
cd /Users/ahussain2373/Projects/specindex
cp .env.example .env
```

Open `.env` in your editor. Set a strong password:

```
SPECINDEX_DB_PASSWORD=your-strong-password-here
```

Leave the other lines as-is unless you have a reason to change them.

**Important:** `.env` is gitignored. Never commit this file or paste the password in Slack/email.

Save the password somewhere safe (1Password, etc.) — you will need it if you reconnect manually later.

---

## Step 5 — Run the automated setup

One command does the rest:

```bash
npm run db:setup-gcp
```

### What this script does (for your notes)

| Step | Action | Time |
| --- | --- | --- |
| 1 | Enables Cloud SQL, Cloud Run, Cloud Build APIs | ~30 sec |
| 2 | Creates Postgres instance `specindex-db` (if new) | 5–10 min |
| 3 | Creates database `specindex` and user `specindex` | ~30 sec |
| 4 | Downloads Cloud SQL Auth Proxy to `.cache/` | ~10 sec |
| 5 | Applies `db/schema.sql` (creates `projects` table) | instant |
| 6 | Loads `data/national-commercial-projects.json` | ~30 sec |
| 7 | Verifies row count = **652** | instant |
| 8 | Deploys `api/` to Cloud Run as `specindex-api` | 2–5 min |
| 9 | Hits `/health` and `/v1/stats` to confirm | instant |

If the instance already exists from a previous attempt:

```bash
npm run db:setup-gcp -- --skip-sql-create
```

---

## Step 6 — Verify it worked

When the script finishes, it prints a **Service URL** like:

```
https://specindex-api-xxxxxxxx-uc.a.run.app
```

**Save this URL** in your setup log (template at bottom of this doc).

Run these in terminal (replace `YOUR_URL`):

```bash
curl YOUR_URL/health
```

Expected:

```json
{"ok": true, "database": "connected"}
```

```bash
curl YOUR_URL/v1/stats
```

Expected (numbers from live corpus):

```json
{"total": 652, "states": 50, "early_stage": ...}
```

```bash
curl 'YOUR_URL/v1/projects?state=GA&limit=3'
```

Expected: JSON with 3 Georgia projects.

**Also verify in GCP Console:**

- Cloud SQL: https://console.cloud.google.com/sql/instances?project=specindex-ai  
  → instance `specindex-db` should be green/running
- Cloud Run: https://console.cloud.google.com/run?project=specindex-ai  
  → service `specindex-api` should show the URL

---

## Optional — Test locally first (Docker)

If you want to try Postgres on your laptop before touching GCP:

```bash
cd /Users/ahussain2373/Projects/specindex
npm run db:up
pip install -r requirements-db.txt
npm run db:load
curl http://localhost:8080/health
curl http://localhost:8080/v1/stats
```

Stop local stack:

```bash
npm run db:down
```

Requires Docker Desktop installed.

---

## API reference (after setup)

| Endpoint | Example | Returns |
| --- | --- | --- |
| Health | `GET /health` | DB connection status |
| Stats | `GET /v1/stats` | Total projects, states, early-stage count |
| List | `GET /v1/projects?state=GA&limit=20` | Paginated project list |
| One project | `GET /v1/projects/ga-centennial-yards` | Single project by ID |

Query params for list: `state` (2-letter), `status`, `limit` (max 100), `offset`.

---

## Files in the repo (reference)

| Path | Role |
| --- | --- |
| `db/schema.sql` | Postgres table definition |
| `api/main.py` | FastAPI read API |
| `api/Dockerfile` | Container image for Cloud Run |
| `scripts/load-corpus-to-postgres.py` | Loads JSON → Postgres |
| `scripts/setup-phase1-gcp.sh` | Full GCP setup automation |
| `data/national-commercial-projects.json` | Source data (652 projects) |
| `.env` | Your password (local only, not in git) |
| `docs/DATABASE_DESIGN.md` | Full future schema (bids, products, etc.) |

---

## Common problems

### `gcloud: command not found`

Install: `brew install google-cloud-sdk`, then open a new terminal tab.

### `Set SPECINDEX_DB_PASSWORD in .env`

You skipped Step 4. Create `.env` from `.env.example` and set the password.

### Billing / quota errors

Enable billing on `specindex-ai` in GCP Console.

### Cloud SQL create fails: instance name taken

Instance already exists. Run:

```bash
npm run db:setup-gcp -- --skip-sql-create
```

### Row count mismatch (not 652)

Corpus may have changed. Check independently:

```bash
python3 -c "import json; print(len(json.load(open('data/national-commercial-projects.json'))['projects']))"
```

If that number differs from 652, the script is correct — update your expectation to match the file.

### Cloud Run deploy fails on DATABASE_URL

Password may contain special characters that break the URL. Use alphanumeric password in `.env` and re-run with `--skip-sql-create --skip-load` if data is already loaded.

### Reload data only (no new instance, no redeploy)

```bash
npm run db:setup-gcp -- --skip-sql-create --skip-deploy
```

### Redeploy API only (after editing `api/`)

```bash
gcloud run deploy specindex-api \
  --source ./api \
  --region us-central1 \
  --project specindex-ai
```

(Password and Cloud SQL connection are preserved if you don't change env vars.)

---

## What comes next (Phase 2+)

Not part of this setup — documented for context:

1. **Phase 2:** Ingest scripts write to Postgres first, then export JSON for the website build
2. **Phase 3:** BigQuery data warehouse synced from Postgres for heavy analytics
3. **Phase 4:** Firebase Auth in front of Cloud Run for paid reporting

See `docs/DATABASE_DESIGN.md` for the full schema.

---

## Setup log (fill in as you go)

Copy this block to your notes or paste completed values here:

```
Phase 1 setup log
-----------------
Date completed:
Completed by: asif@specindex.ai

GCP project:        specindex-ai
Region:             us-central1
Cloud SQL instance: specindex-db
Database name:      specindex
Database user:      specindex
Password stored in: (e.g. 1Password entry name: _____________)

Cloud Run service:  specindex-api
API URL:            https://___________________________

Verification:
  [ ] /health returned ok: true
  [ ] /v1/stats total = 652 (or current corpus count: ___)
  [ ] GA projects query returned data

Notes / issues:
-
-
```

---

## Quick command cheat sheet

```bash
# Full setup (first time)
cd /Users/ahussain2373/Projects/specindex
cp .env.example .env   # edit password
npm run db:setup-gcp

# Re-run after corpus update
npm run db:setup-gcp -- --skip-sql-create --skip-deploy

# Local Docker test
npm run db:up && pip install -r requirements-db.txt && npm run db:load

# Get API URL again later
gcloud run services describe specindex-api \
  --region us-central1 \
  --project specindex-ai \
  --format='value(status.url)'
```

---

## Related docs

- `docs/CLOUD-RUN-DATABASE.md` — technical details + manual gcloud commands
- `docs/DATABASE_DESIGN.md` — full Postgres schema and product rationale
- `docs/technical-architecture.md` — overall app architecture (some sections predate Postgres decision)
