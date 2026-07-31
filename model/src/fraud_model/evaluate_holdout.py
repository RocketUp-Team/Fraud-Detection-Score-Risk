"""Final holdout evaluation. Run only after model and threshold are frozen."""
from __future__ import annotations

import csv
import json

import joblib
import mlflow
import numpy as np

from . import config
from .data import load_holdout
from .evaluation import binary_metrics
from .features import to_pandas_xy_with_mappings
from .tracking import training_run


def main() -> None:
    artifact = joblib.load(config.TRAINING_FINAL_MODEL_PATH)
    mappings = artifact.get("category_mappings")
    calibrator = artifact.get("calibrator")
    threshold_config = artifact.get("threshold_config")
    if not mappings:
        raise ValueError("Final artifact is missing train-fitted category_mappings.")
    if calibrator is None:
        raise ValueError("Holdout evaluation requires a frozen calibrator.")
    if not threshold_config:
        raise ValueError("Holdout evaluation requires a frozen threshold policy.")

    X_holdout, y_holdout, _ = to_pandas_xy_with_mappings(
        load_holdout(),
        mappings,
    )
    y = y_holdout.to_numpy()
    raw_proba = artifact["model"].predict_proba(X_holdout)[:, 1]
    proba = np.asarray(calibrator.predict(raw_proba), dtype=float)
    threshold = threshold_config["review_threshold"]
    metrics = binary_metrics(y, proba, threshold)
    metrics.update(
        {
            "raw_brier_score": float(np.mean((raw_proba - y) ** 2)),
            "brier_score": float(np.mean((proba - y) ** 2)),
        }
    )

    metadata = json.loads(config.TRAINING_METADATA_PATH.read_text(encoding="utf-8"))
    metadata["holdout_metrics"] = metrics
    metadata["calibration_method"] = artifact.get("calibration_method")
    metadata["promotion_status"] = "pending_review"

    with training_run("holdout_final") as run:
        run_id = run.info.run_id
        metadata["holdout_mlflow_run_id"] = run_id
        artifact["holdout_metrics"] = metrics
        artifact["holdout_roc_auc"] = metrics["roc_auc"]
        artifact["holdout_pr_auc"] = metrics["pr_auc"]
        artifact["holdout_mlflow_run_id"] = run_id
        artifact["promotion_status"] = "pending_review"
        joblib.dump(artifact, config.TRAINING_FINAL_MODEL_PATH)
        with config.TRAINING_HOLDOUT_METRICS_PATH.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.DictWriter(f, fieldnames=list(metrics))
            writer.writeheader()
            writer.writerow(metrics)
        config.TRAINING_METADATA_PATH.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.log_artifact(str(config.TRAINING_HOLDOUT_METRICS_PATH), artifact_path="reports")
        mlflow.log_artifact(str(config.TRAINING_METADATA_PATH), artifact_path="metadata")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
