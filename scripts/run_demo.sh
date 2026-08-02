#!/usr/bin/env bash
set -Eeuo pipefail

# Start the local demo stack: PostgreSQL, FastAPI backend, frontend, and demo data.
#
# Usage:
#   bash scripts/run_demo.sh                 # build, start, and load demo data
#   DEMO_PER_BAND=20 bash scripts/run_demo.sh
#   bash scripts/run_demo.sh stop
#   bash scripts/run_demo.sh down
#   bash scripts/run_demo.sh logs

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.demo.yml)
DEMO_PER_BAND="${DEMO_PER_BAND:-10}"
DEMO_LIMIT="${DEMO_LIMIT:-100}"
API_URL="${DEMO_API_URL:-http://localhost:8000}"

log() {
  printf '[demo] %s\n' "$*"
}

fail() {
  printf '[demo] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

wait_for_api() {
  local attempts=60
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl --fail --silent "$API_URL/health" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  "${COMPOSE[@]}" ps
  "${COMPOSE[@]}" logs --tail=80 backend
  fail "Backend did not become ready at $API_URL"
}

load_from_processed_data() {
  local datasets job_id status response

  datasets="$(curl --fail --silent "$API_URL/datasets")"
  if ! python3 - "$datasets" <<'PY'
import json
import sys

try:
    datasets = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError):
    raise SystemExit(1)

raise SystemExit(0 if any(item.get("name") == "holdout" for item in datasets) else 1)
PY
  then
    return 1
  fi

  log "Loading $DEMO_PER_BAND transaction(s) per risk band from holdout"
  response="$(curl --fail --silent --show-error \
    -X POST "$API_URL/data/load" \
    -H 'Content-Type: application/json' \
    -d "{\"dataset\":\"holdout\",\"mode\":\"coverage\",\"per_band\":$DEMO_PER_BAND,\"reset\":true}")"
  job_id="$(python3 - "$response" <<'PY'
import json
import sys
print(json.loads(sys.argv[1])["id"])
PY
  )"

  while true; do
    response="$(curl --fail --silent --show-error "$API_URL/jobs/$job_id")"
    read -r status processed percent error <<EOF
$(python3 - "$response" <<'PY'
import json
import sys

job = json.loads(sys.argv[1])
error = (job.get("error") or "").replace(" ", "_")
print(job.get("status", "unknown"), job.get("processed", 0), job.get("percent", 0), error)
PY
)
EOF
    log "Data job: $status, processed=$processed, progress=${percent}%"
    case "$status" in
      done) return 0 ;;
      error|cancelled) fail "Data loading failed: ${error//_/ }" ;;
    esac
    sleep 2
  done
}

load_fallback_demo_data() {
  log "No processed Parquet found; seeding $DEMO_LIMIT deterministic synthetic transactions"
  "${COMPOSE[@]}" exec -T \
    -e SEED_DATASET=holdout \
    backend uv run python -m fraud_backend.seed --reset --limit "$DEMO_LIMIT"
}

start_demo() {
  require_command docker
  require_command curl
  require_command python3

  log "Building and starting PostgreSQL, backend, and frontend"
  "${COMPOSE[@]}" up --build -d db backend frontend
  wait_for_api

  if ! load_from_processed_data; then
    load_fallback_demo_data
  fi

  log "Demo is ready"
  log "Dashboard:  http://localhost:5173"
  log "API docs:   $API_URL/docs"
  log "API health: $API_URL/health"
  log "Database:   localhost:5433 (user/password/database: fraud/fraud/fraud)"
  log "Adminer:    ${COMPOSE[*]} --profile tools up -d adminer"
}

main() {
  case "${1:-start}" in
    start|run) start_demo ;;
    stop) require_command docker; "${COMPOSE[@]}" stop ;;
    down) require_command docker; "${COMPOSE[@]}" down ;;
    logs) require_command docker; "${COMPOSE[@]}" logs -f --tail=100 ;;
    *)
      echo "Usage: bash scripts/run_demo.sh [start|stop|down|logs]" >&2
      exit 2
      ;;
  esac
}

main "$@"
