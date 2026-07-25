# Cloud Run + PostgreSQL test setup

Minimal read API in front of Postgres. The static site keeps using JSON at build
time; this stack is for testing the database path before paid reporting.

**Start here:** [`docs/PHASE1-DATABASE-SETUP.md`](./PHASE1-DATABASE-SETUP.md) — step-by-step
guide with checklist and setup log template.

## Local test (Docker)

```bash
docker compose up --build -d
pip install -r requirements-db.txt
python3 scripts/load-corpus-to-postgres.py
curl http://localhost:8080/health
curl http://localhost:8080/v1/stats
curl 'http://localhost:8080/v1/projects?state=GA&limit=5'
```

Stop: `docker compose down` (add `-v` to wipe the database volume).

## GCP: Cloud SQL + Cloud Run (one command)

```bash
cp .env.example .env
# Edit .env — set SPECINDEX_DB_PASSWORD to a strong password

npm run db:setup-gcp
```

The script enables APIs, creates Cloud SQL (if missing), loads 652 projects,
deploys `specindex-api` to Cloud Run, and verifies counts match the JSON corpus.

Partial reruns:

```bash
npm run db:setup-gcp -- --skip-sql-create    # instance already exists
npm run db:setup-gcp -- --skip-deploy         # only load data
```

## GCP: Cloud SQL + Cloud Run (manual)

Project: **specindex-ai**. Pick a region (example: `us-central1`).

### 1. Enable APIs

```bash
gcloud config set project specindex-ai
gcloud services enable sqladmin.googleapis.com run.googleapis.com
```

### 2. Create Cloud SQL (Postgres 16)

```bash
gcloud sql instances create specindex-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-size=10GB \
  --storage-auto-increase

gcloud sql databases create specindex --instance=specindex-db
gcloud sql users create specindex \
  --instance=specindex-db \
  --password='CHOOSE_A_STRONG_PASSWORD'
```

Apply schema (from Cloud Shell or any machine with Cloud SQL Auth Proxy):

```bash
cloud-sql-proxy specindex-ai:us-central1:specindex-db &
export DATABASE_URL="postgresql://specindex:PASSWORD@127.0.0.1:5432/specindex"
python3 scripts/load-corpus-to-postgres.py --apply-schema
```

### 3. Deploy API to Cloud Run

```bash
gcloud run deploy specindex-api \
  --source ./api \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances specindex-ai:us-central1:specindex-db \
  --set-env-vars "DATABASE_URL=postgresql://specindex:PASSWORD@/specindex?host=/cloudsql/specindex-ai:us-central1:specindex-db"
```

Cloud Run mounts the Cloud SQL socket at `/cloudsql/...`; the `host=` query param
tells psycopg2 to use it.

### 4. Smoke test

```bash
SERVICE_URL=$(gcloud run services describe specindex-api --region us-central1 --format='value(status.url)')
curl "$SERVICE_URL/health"
curl "$SERVICE_URL/v1/stats"
curl "$SERVICE_URL/v1/projects?state=GA&limit=3"
```

Compare `/v1/stats` `total` against an independent count from
`data/national-commercial-projects.json` before treating numbers as authoritative.

## API surface

| Route | Description |
| --- | --- |
| `GET /health` | DB connectivity check |
| `GET /v1/stats` | Total projects, states, early-stage count |
| `GET /v1/projects` | List with `state`, `status`, `limit`, `offset` |
| `GET /v1/projects/{id}` | Single project |

## Next steps

- Move ingest scripts to write Postgres first, then export JSON for the static build.
- Add Firebase Auth in front of Cloud Run for gated reporting.
- Grow schema toward `docs/DATABASE_DESIGN.md` (companies, bids, installed products).
