#!/usr/bin/env bash
set -euo pipefail

# One training entrypoint. Every execution creates new MLflow runs while the
# model artifact directory is refreshed under the selected training version.
# Usage: bash scripts/train_model.sh [local|cluster] [0.0.10]
MODE="${1:-local}"
TRAINING_VERSION="${2:-}"

if [[ -z "$TRAINING_VERSION" ]]; then
  max_patch=0
  shopt -s nullglob
  for artifact_dir in model/artifacts/*; do
    version_name="$(basename "$artifact_dir")"
    if [[ "$version_name" =~ ^[0-9]+\.[0-9]+\.([0-9]+)$ ]]; then
      patch="${BASH_REMATCH[1]}"
      (( patch > max_patch )) && max_patch="$patch"
    fi
  done
  TRAINING_VERSION="0.0.$((max_patch + 1))"
fi

run_stage() {
  local service="$1"
  local module="$2"
  echo "[training] $module ($service, version=$TRAINING_VERSION)"
  docker compose --profile training run --rm \
    -e "FRAUD_MODEL_TRAINING_VERSION=$TRAINING_VERSION" \
    -e "MLFLOW_EXPERIMENT=fraud-detection-training" \
    "$service" uv run python -m "fraud_model.$module"
}

run_workflow() {
  local service="$1"
  for module in validate_data train_baseline train_compare tune_and_explain threshold_analysis evaluate_holdout; do
    run_stage "$service" "$module"
  done
}

run_local() {
  echo "[training] Building local Spark Docker image..."
  docker compose --profile training build model-training-local
  run_workflow model-training-local
}

if [[ "$MODE" == "cluster" ]] && \
   docker compose --profile training build model-training && \
   docker compose --profile training up -d spark-master spark-worker; then
  run_workflow model-training
else
  if [[ "$MODE" == "cluster" ]]; then
    echo "[training] Spark cluster unavailable; falling back to Spark local[*]."
  fi
  run_local
fi

echo "[training] Completed successfully."
echo "[training] Model artifacts: model/artifacts/$TRAINING_VERSION/"
echo "[training] MLflow history: model/artifacts/mlruns/"
