#!/usr/bin/env bash
# Phase 1: Cloud SQL Postgres + load corpus + Cloud Run API
# Run from repo root: ./scripts/setup-phase1-gcp.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROJECT="${SPECINDEX_GCP_PROJECT:-specindex-ai}"
REGION="${SPECINDEX_GCP_REGION:-us-central1}"
INSTANCE="${SPECINDEX_DB_INSTANCE:-specindex-db}"
DB_NAME="${SPECINDEX_DB_NAME:-specindex}"
DB_USER="${SPECINDEX_DB_USER:-specindex}"
CONNECTION="${PROJECT}:${REGION}:${INSTANCE}"
PROXY_BIN="${ROOT}/.cache/cloud-sql-proxy"
PROXY_PORT="${CLOUD_SQL_PROXY_PORT:-9470}"
PROXY_PID=""

if [[ -f "${ROOT}/.env" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
fi

DB_PASSWORD="${SPECINDEX_DB_PASSWORD:-}"
SKIP_SQL_CREATE=0
SKIP_LOAD=0
SKIP_DEPLOY=0

usage() {
  cat <<EOF
Usage: ./scripts/setup-phase1-gcp.sh [options]

Options:
  --skip-sql-create   Assume Cloud SQL instance already exists
  --skip-load         Skip schema apply + corpus load
  --skip-deploy       Skip Cloud Run deploy
  -h, --help          Show this help

Environment (or .env):
  SPECINDEX_GCP_PROJECT   default: specindex-ai
  SPECINDEX_GCP_REGION    default: us-central1
  SPECINDEX_DB_PASSWORD   required for load + deploy

Prerequisites:
  gcloud CLI (logged in as asif@specindex.ai)
  python3 + pip
  curl
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-sql-create) SKIP_SQL_CREATE=1 ;;
    --skip-load) SKIP_LOAD=1 ;;
    --skip-deploy) SKIP_DEPLOY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need gcloud
need python3
need curl

if [[ -z "${DB_PASSWORD}" ]]; then
  echo "Set SPECINDEX_DB_PASSWORD in .env (copy from .env.example)" >&2
  exit 1
fi

echo "==> Project: ${PROJECT}  Region: ${REGION}  Instance: ${INSTANCE}"

gcloud config set project "${PROJECT}" >/dev/null
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"
echo "==> GCP account: ${ACTIVE_ACCOUNT}"

echo "==> Enabling APIs..."
gcloud services enable sqladmin.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  --project="${PROJECT}"

if [[ "${SKIP_SQL_CREATE}" -eq 0 ]]; then
  if gcloud sql instances describe "${INSTANCE}" --project="${PROJECT}" >/dev/null 2>&1; then
    echo "==> Cloud SQL instance '${INSTANCE}' already exists — skipping create"
  else
    echo "==> Creating Cloud SQL instance (5–10 min)..."
    gcloud sql instances create "${INSTANCE}" \
      --project="${PROJECT}" \
      --database-version=POSTGRES_16 \
      --edition=ENTERPRISE \
      --tier=db-f1-micro \
      --region="${REGION}" \
      --storage-size=10GB \
      --storage-auto-increase
  fi

  if ! gcloud sql databases describe "${DB_NAME}" --instance="${INSTANCE}" --project="${PROJECT}" >/dev/null 2>&1; then
    echo "==> Creating database ${DB_NAME}..."
    gcloud sql databases create "${DB_NAME}" --instance="${INSTANCE}" --project="${PROJECT}"
  fi

  echo "==> Setting database user password..."
  gcloud sql users create "${DB_USER}" \
    --instance="${INSTANCE}" \
    --project="${PROJECT}" \
    --password="${DB_PASSWORD}" 2>/dev/null || \
  gcloud sql users set-password "${DB_USER}" \
    --instance="${INSTANCE}" \
    --project="${PROJECT}" \
    --password="${DB_PASSWORD}"
fi

download_proxy() {
  mkdir -p "${ROOT}/.cache"
  local os arch url
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "${arch}" in
    x86_64) arch="amd64" ;;
    arm64|aarch64) arch="arm64" ;;
    *) echo "Unsupported arch: ${arch}" >&2; exit 1 ;;
  esac
  url="https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.${os}.${arch}"
  echo "==> Downloading Cloud SQL Auth Proxy..."
  curl -fsSL "${url}" -o "${PROXY_BIN}"
  chmod +x "${PROXY_BIN}"
}

start_proxy() {
  if [[ ! -x "${PROXY_BIN}" ]]; then
    download_proxy
  fi
  echo "==> Starting Cloud SQL Auth Proxy on port ${PROXY_PORT}..."
  "${PROXY_BIN}" "${CONNECTION}" --port "${PROXY_PORT}" &
  PROXY_PID=$!
  sleep 2
  if ! kill -0 "${PROXY_PID}" 2>/dev/null; then
    echo "Cloud SQL Auth Proxy failed to start" >&2
    exit 1
  fi
}

stop_proxy() {
  if [[ -n "${PROXY_PID}" ]] && kill -0 "${PROXY_PID}" 2>/dev/null; then
    kill "${PROXY_PID}" 2>/dev/null || true
    wait "${PROXY_PID}" 2>/dev/null || true
  fi
}
trap stop_proxy EXIT

expected_total() {
  python3 - <<'PY'
import json
from pathlib import Path
corpus = json.loads(Path("data/national-commercial-projects.json").read_text())
print(len(corpus.get("projects") or []))
PY
}

if [[ "${SKIP_LOAD}" -eq 0 ]]; then
  start_proxy
  export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:${PROXY_PORT}/${DB_NAME}"

  echo "==> Installing Python DB driver..."
  python3 -m pip install -q -r requirements-db.txt

  echo "==> Applying schema and loading corpus..."
  python3 scripts/load-corpus-to-postgres.py --apply-schema

  EXPECTED="$(expected_total)"
  ACTUAL="$(python3 - <<PY
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT count(*) FROM projects")
print(cur.fetchone()[0])
conn.close()
PY
)"
  echo "==> Row count: ${ACTUAL} (expected ${EXPECTED})"
  if [[ "${ACTUAL}" != "${EXPECTED}" ]]; then
    echo "ERROR: project count mismatch" >&2
    exit 1
  fi
  stop_proxy
  trap - EXIT
fi

if [[ "${SKIP_DEPLOY}" -eq 0 ]]; then
  SOCKET="/cloudsql/${CONNECTION}"
  RUN_DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=${SOCKET}"

  echo "==> Deploying Cloud Run service specindex-api..."
  gcloud run deploy specindex-api \
    --project="${PROJECT}" \
    --source ./api \
    --region "${REGION}" \
    --allow-unauthenticated \
    --add-cloudsql-instances "${CONNECTION}" \
    --set-env-vars "DATABASE_URL=${RUN_DATABASE_URL}"

  SERVICE_URL="$(gcloud run services describe specindex-api \
    --project="${PROJECT}" \
    --region "${REGION}" \
    --format='value(status.url)')"
  echo "==> Service URL: ${SERVICE_URL}"

  echo "==> Smoke tests..."
  curl -fsS "${SERVICE_URL}/health" | python3 -m json.tool
  curl -fsS "${SERVICE_URL}/v1/stats" | python3 -m json.tool

  STATS_TOTAL="$(curl -fsS "${SERVICE_URL}/v1/stats" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])")"
  EXPECTED="$(expected_total)"
  if [[ "${STATS_TOTAL}" != "${EXPECTED}" ]]; then
    echo "ERROR: API stats total ${STATS_TOTAL} != expected ${EXPECTED}" >&2
    exit 1
  fi

  echo ""
  echo "Phase 1 complete."
  echo "  API:    ${SERVICE_URL}"
  echo "  Health: ${SERVICE_URL}/health"
  echo "  Stats:  ${SERVICE_URL}/v1/stats"
  echo "  GA:     ${SERVICE_URL}/v1/projects?state=GA&limit=5"
fi
