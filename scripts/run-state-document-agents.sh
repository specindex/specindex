#!/usr/bin/env bash
# One document-discovery worker per state, run as background bash rather than
# Agent-tool agents.
#
# WHY NOT AGENTS. The agent runner kills a subagent after 600s with no output,
# and a state sweep is hours of mostly-quiet HTTP probing behind a deliberate
# rate limit. Agents were tried for long captures before and died mid-run,
# losing the work silently. Background bash survives, writes a log per state and
# a sentinel on clean exit, so progress is inspectable and a crash is loud.
#
# CONCURRENCY IS CAPPED ON PURPOSE. Each worker talks to government hosts. The
# cap here is about not getting banned -- a ban is permanent loss of a source --
# and measured uplink saturates around 3 large transfers anyway.
#
# Usage:
#   scripts/run-state-document-agents.sh GA                 # one state
#   scripts/run-state-document-agents.sh GA FL TX           # several
#   MAX_PARALLEL=4 MIN_VALUE=100000 scripts/run-state-document-agents.sh ALL
set -uo pipefail
cd "$(dirname "$0")/.."

MAX_PARALLEL="${MAX_PARALLEL:-3}"
MIN_VALUE="${MIN_VALUE:-100000}"
SINCE="${SINCE:-2025-01-01}"
LIMIT="${LIMIT:-400}"          # per state; grounded search bills per query
PAUSE="${PAUSE:-1.2}"
MODEL="${MODEL:-gemini-3.6-flash}"

mkdir -p logs/state-docs
STAMP="$(date +%Y%m%dT%H%M%S)"
SUMMARY="logs/state-docs/summary-${STAMP}.txt"

set -a; [ -f .env ] && . ./.env; set +a

if [ "${1:-}" = "ALL" ]; then
  STATES=$(python3 - <<'PY'
import sys; sys.path.insert(0,"scripts")
from specindex.db import connect
cur=connect().cursor()
cur.execute("""select p.state, count(*) n from projects p
  where not exists(select 1 from project_document_files f where f.project_sk=p.project_sk)
    and p.opened_or_announced_date>='2025-01-01' and p.state is not null
  group by 1 order by n desc""")
print(" ".join(r[0] for r in cur.fetchall() if r[0] and len(r[0])==2))
PY
)
else
  STATES="$*"
fi

echo "[fleet] states: $STATES" | tee -a "$SUMMARY"
echo "[fleet] limit=$LIMIT/state min_value=$MIN_VALUE model=$MODEL parallel=$MAX_PARALLEL" | tee -a "$SUMMARY"

run_state() {
  local st="$1"
  local log="logs/state-docs/${st}.log"
  local sentinel="logs/state-docs/${st}.done"
  rm -f "$sentinel"
  python3 scripts/find-project-documents.py \
      --state "$st" --limit "$LIMIT" --min-value "$MIN_VALUE" \
      --since "$SINCE" --pause "$PAUSE" --model "$MODEL" \
      --sentinel "$sentinel" >"$log" 2>&1
  local rc=$?
  local line
  line="$(grep -E '^\[done\]' "$log" | tail -1)"
  printf '%-4s rc=%s  %s\n' "$st" "$rc" "${line:-NO SUMMARY LINE}" | tee -a "$SUMMARY"
}

for st in $STATES; do
  while [ "$(jobs -rp | wc -l)" -ge "$MAX_PARALLEL" ]; do sleep 5; done
  echo "[start] $st" | tee -a "$SUMMARY"
  run_state "$st" &
done
wait

echo "[fleet] complete $(date)" | tee -a "$SUMMARY"
grep -hE '^\[done\]' logs/state-docs/*.log 2>/dev/null \
  | awk '{for(i=1;i<=NF;i++){if($i~/^documents_stored=/){split($i,a,"=");s+=a[2]}}} END{print "[fleet] documents stored across all states:", s+0}' \
  | tee -a "$SUMMARY"
