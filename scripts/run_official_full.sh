#!/usr/bin/env bash
set -Eeuo pipefail

# Official end-to-end run:
#   raw IEEE-CIS -> Spark preprocessing 2.1.0 -> official V2 training
#   -> packaging/gates -> tests -> Docker application -> smoke checks.
#
# This script intentionally does not create semantic candidate versions.
# The only training/serving version used here is v2.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_DIR="${OFFICIAL_RUN_DIR:-$ROOT_DIR/reports/official-run}"
TRAINING_VERSION="v2"
DATA_ROOT_IN_CONTAINER="/data/processed/ieee_cis_fraud_risk"

mkdir -p "$RUN_DIR"

log() {
  printf '[official] %s\n' "$*"
}

fail() {
  printf '[official] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

run_logged() {
  local name="$1"
  shift
  log "$name"
  "$@" 2>&1 | tee "$RUN_DIR/$name.log"
}

run_training_stage() {
  local stage="$1"
  log "training stage: $stage"
  docker compose --profile training run --rm \
    -e "FRAUD_MODEL_TRAINING_VERSION=$TRAINING_VERSION" \
    -e "FRAUD_MODEL_DATA_ROOT=$DATA_ROOT_IN_CONTAINER" \
    -e "FRAUD_GIT_COMMIT=$GIT_COMMIT" \
    -e "FRAUD_GIT_DIRTY=$GIT_DIRTY" \
    -e "MLFLOW_EXPERIMENT=fraud-detection-training" \
    model-training-local \
    uv run python -m "fraud_model.$stage" \
    2>&1 | tee "$RUN_DIR/training-$stage.log"
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-60}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl --fail --silent --show-error "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

require_command docker
require_command curl
require_command git

[[ -f data/data/ieee-fraud-detection/train_transaction.csv ]] || \
  fail "Missing raw train_transaction.csv"
[[ -f data/data/ieee-fraud-detection/train_identity.csv ]] || \
  fail "Missing raw train_identity.csv"
[[ -f data/data/ieee-fraud-detection/test_transaction.csv ]] || \
  fail "Missing raw test_transaction.csv"
[[ -f data/data/ieee-fraud-detection/test_identity.csv ]] || \
  fail "Missing raw test_identity.csv"

docker compose config >/dev/null
docker compose -f docker-compose.preprocessing.yml config >/dev/null

GIT_COMMIT="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  GIT_DIRTY="true"
else
  GIT_DIRTY="false"
fi

log "git commit: $GIT_COMMIT"
log "git dirty: $GIT_DIRTY"
log "official training version: $TRAINING_VERSION"

run_logged preprocessing bash scripts/run_preprocessing.sh

[[ -f data/processed/ieee_cis_fraud_risk/manifest.json ]] || \
  fail "Preprocessing did not produce manifest.json"
[[ -f data/processed/ieee_cis_fraud_risk/reports/verification_report.json ]] || \
  fail "Preprocessing did not produce verification_report.json"

cp data/processed/ieee_cis_fraud_risk/manifest.json "$RUN_DIR/manifest.json"
cp data/processed/ieee_cis_fraud_risk/reports/verification_report.json \
  "$RUN_DIR/verification_report.json"
cp data/processed/ieee_cis_fraud_risk/reports/split_summary.csv \
  "$RUN_DIR/split_summary.csv"
cp data/processed/ieee_cis_fraud_risk/artifacts/preprocessing/feature_order.json \
  "$RUN_DIR/feature_order.json"

log "building official local Spark training image"
docker compose --profile training build model-training-local \
  2>&1 | tee "$RUN_DIR/training-build.log"

for stage in \
  validate_data \
  train_baseline \
  train_compare \
  tune_and_explain \
  threshold_analysis \
  evaluate_holdout \
  package_candidate \
  promotion_gate
do
  run_training_stage "$stage"
done

for artifact in \
  training_metadata_v2.json \
  validation_metrics_v2.csv \
  holdout_metrics_v2.csv \
  threshold_config_v2.json \
  candidate_manifest_v2.json \
  promotion_decision_v2.json \
  checksum_v2.sha256
do
  [[ -f "model/artifacts/v2/$artifact" ]] || \
    fail "Missing official V2 artifact: model/artifacts/v2/$artifact"
  cp "model/artifacts/v2/$artifact" "$RUN_DIR/$artifact"
done

log "running model lint and tests in the official training image"
{
  docker compose --profile training run --rm model-training-local \
    uv run ruff check .
  docker compose --profile training run --rm model-training-local \
    uv run pytest -q
} 2>&1 | tee "$RUN_DIR/model-quality.log"

log "building and starting application stack"
docker compose up --build -d 2>&1 | tee "$RUN_DIR/application-build.log"
docker compose ps 2>&1 | tee "$RUN_DIR/application-ps.log"

wait_for_http http://localhost:8000/health || \
  fail "Backend health endpoint did not become ready"
wait_for_http http://localhost:5173 || \
  fail "Frontend did not become ready"

curl --fail --silent --show-error http://localhost:8000/health \
  | tee "$RUN_DIR/health.json"
printf '\n'
curl --fail --silent --show-error http://localhost:8000/meta \
  | tee "$RUN_DIR/meta.json"
printf '\n'

docker compose exec -T backend \
  uv run python -m fraud_backend.seed --limit 300 \
  2>&1 | tee "$RUN_DIR/seed.log"

log "official end-to-end run completed"
log "evidence directory: $RUN_DIR"
