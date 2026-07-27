#!/usr/bin/env bash
set -euo pipefail

# Full Docker training workflow for model v2.
# Run from repository root:
#   bash scripts/train_model_v2_full.sh
#
# Expected outputs:
#   model/artifacts/v2/baseline_logreg_v2.joblib
#   model/artifacts/v2/model_comparison_v2.json
#   model/artifacts/v2/final_model_v2.joblib
#   model/artifacts/v2/training_metadata_v2.json
#
# Notes:
# - This script follows the cluster-based training flow in docker-compose.yml.
# - If Spark cluster images cannot be pulled in your environment, use the
#   local Docker fallback service manually:
#     docker compose --profile training build model-training-local
#     docker compose --profile training run --rm model-training-local uv run python -m fraud_model.train_baseline
#     docker compose --profile training run --rm model-training-local uv run python -m fraud_model.train_compare
#     docker compose --profile training run --rm model-training-local uv run python -m fraud_model.tune_and_explain

# Fallback local Docker training when Spark cluster image is unavailable.
train_local() {
  echo "[v2] Falling back to local Docker training (Spark local[*])..."
  docker compose --profile training build model-training-local

  echo "[v2] Training baseline model (local)..."
  docker compose --profile training run --rm model-training-local \
    uv run python -m fraud_model.train_baseline

  echo "[v2] Training comparison models (local)..."
  docker compose --profile training run --rm model-training-local \
    uv run python -m fraud_model.train_compare

  echo "[v2] Training final tuned model (local)..."
  docker compose --profile training run --rm model-training-local \
    uv run python -m fraud_model.tune_and_explain
}

echo "[v2] Building Docker training image..."
docker compose --profile training build model-training

echo "[v2] Starting Spark training cluster..."
if docker compose --profile training up -d spark-master spark-worker; then
  echo "[v2] Training baseline model..."
  docker compose --profile training run --rm model-training \
    uv run python -m fraud_model.train_baseline

  echo "[v2] Training comparison models..."
  docker compose --profile training run --rm model-training \
    uv run python -m fraud_model.train_compare

  echo "[v2] Training final tuned model..."
  docker compose --profile training run --rm model-training \
    uv run python -m fraud_model.tune_and_explain
else
  train_local
fi

echo "[v2] Training completed. Expected artifacts:"
echo "  - model/artifacts/v2/baseline_logreg_v2.joblib"
echo "  - model/artifacts/v2/model_comparison_v2.json"
echo "  - model/artifacts/v2/final_model_v2.joblib"
echo "  - model/artifacts/v2/training_metadata_v2.json"
