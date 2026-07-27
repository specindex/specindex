#!/usr/bin/env bash
# Daily NJ DCA incremental job wrapper.
# Loads .env, runs the pipeline, appends to pipeline.log, emails on finish.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PIPELINE_DIR="$ROOT/data/pipeline/nj-dca"
LOG_FILE="${NJ_DCA_LOG_FILE:-$PIPELINE_DIR/pipeline.log}"
mkdir -p "$PIPELINE_DIR"

# Load .env into the environment (do not print secrets)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

# Optional venv
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  :
elif [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
elif [[ -f "$ROOT/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONUNBUFFERED=1

{
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) NJ DCA pipeline start ====="
  "$PYTHON_BIN" "$ROOT/scripts/nj_dca_pipeline/main.py" \
    --lookback-days "${NJ_DCA_LOOKBACK_DAYS:-30}" \
    --notify \
    ${NJ_DCA_MERGE_STATE:+--merge-state} \
    ${NJ_DCA_SKIP_LLM:+--skip-llm} \
    ${NJ_DCA_LIMIT:+--limit "$NJ_DCA_LIMIT"}
  status=$?
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) NJ DCA pipeline end status=$status ====="
  exit $status
} >>"$LOG_FILE" 2>&1
