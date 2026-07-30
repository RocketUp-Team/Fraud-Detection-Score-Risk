"""Final holdout evaluation. Run only after model and threshold are frozen."""
from __future__ import annotations

import csv
import json

import joblib
import mlflow

from . import config
from .data import load_holdout, load_train_weighted
from .evaluation import binary_metrics
from .features import _canonical_feature_columns, apply_categorical_indexer, fit_categorical_indexer
from .tracking import training_run


def main() -> None:
    artifact = joblib.load(config.TRAINING_FINAL_MODEL_PATH)
    train_df = load_train_weighted()
    holdout_df = load_holdout()
    indexer = fit_categorical_indexer(train_df)
    pdf = apply_categorical_indexer(indexer, holdout_df).toPandas()
    columns = _canonical_feature_columns() or artifact["feature_columns"]
    y = pdf[config.TARGET_COL].to_numpy()
    proba = artifact["model"].predict_proba(pdf.loc[:, columns])[:, 1]
    if artifact.get("calibrator") is not None:
        proba = artifact["calibrator"].predict(proba)
    threshold = artifact.get("threshold_config", {}).get("review_threshold", 0.5)
    metrics = binary_metrics(y, proba, threshold)
    with config.TRAINING_HOLDOUT_METRICS_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)
    metadata = json.loads(config.TRAINING_METADATA_PATH.read_text(encoding="utf-8"))
    metadata["holdout_metrics"] = metrics
    metadata["calibration_method"] = artifact.get("calibration_method")
    config.TRAINING_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with training_run("holdout_final"):
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.log_artifact(str(config.TRAINING_HOLDOUT_METRICS_PATH), artifact_path="reports")
        mlflow.log_artifact(str(config.TRAINING_METADATA_PATH), artifact_path="metadata")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
