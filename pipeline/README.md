# Pipeline container + Cloud Run Jobs

Runs the coverage pipeline off the laptop. Section 3 of
`coverage/docs/coverage-plan-v2.md`.

## Why

`pmset` shows repeated "Maintenance Sleep" and "Dark Wake Thermal Emergency"
through the window where **four separate jobs died** with *"server closed the
connection unexpectedly"* — the NYC backfill, the Legistar pull, the index
loader and portal registration. Cloud SQL was healthy throughout: 12 of 400
connections, 0.4s response, proxy up four days. **The machine was asleep.**
Reconnect logic treats the symptom; moving the work treats the cause.

## Prerequisites NOT yet met — this cannot deploy until they are

| | status |
|---|---|
| Artifact Registry | ✅ `cloud-run-source-deploy` in use |
| Cloud Run + WIF from Actions | ✅ proven by `api-deploy.yml` |
| Deploy IAM (`artifactregistry.writer`, run deploy) | ✅ already held |
| Cloud Run **Jobs** | ❌ none exist — these would be the first |
| **Secret Manager API** | ❌ **not enabled on the project** |
| The four secrets | ❌ cannot exist until the API is on |

Verified 2026-08-07: `secretmanager.googleapis.com` returns
*"API has not been used in project specindex-ai before or it is disabled"* — an
API-disabled 403, not a permissions artifact (the control was a successful
Cloud Run query with the same credential).

**To unblock, a human must:**

```bash
gcloud services enable secretmanager.googleapis.com --project=specindex-ai
for s in DATABASE_URL ANTHROPIC_API_KEY SAM_API_KEY LEGISTAR_TOKEN_NYC; do
  gcloud secrets create "$s" --replication-policy=automatic --project=specindex-ai
  # then add a version from the value in .env
done
gcloud projects add-iam-policy-binding specindex-ai \
  --member=serviceAccount:<runtime-sa> --role=roles/secretmanager.secretAccessor
```

## Also untested

**The image has never been built.** There is no Docker on this laptop, so
`pipeline/Dockerfile` is unexercised — Playwright's `install --with-deps
chromium` on `python:3.12-slim` is the most likely failure. The first CI run is
the real test, and GitHub Actions has been in major outage.

Nothing here should be assumed working until a job runs and a row lands.

## Design

One image, several jobs — the args differ, so a new job is a deploy flag rather
than a new container. Deploy is **by digest**, never by tag: a tag can move
between push and deploy, and you get an image you never tested. The workflow
ends by listing the jobs and failing if any is missing, because a deploy that
reports success and leaves nothing behind is the exact shape this repo keeps
hitting.
