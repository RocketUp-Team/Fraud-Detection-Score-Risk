"""Fit calibration and choose operating thresholds using validation only."""
from __future__ import annotations

import json

import joblib
import mlflow
import numpy as np
from sklearn.isotonic import IsotonicRegression

from . import config
from .data import load_validation, split_validation_windows
from .evaluation import choose_recall_first_threshold, threshold_table
from .features import to_pandas_xy_with_mappings
from .tracking import training_run


def main() -> None:
    artifact = joblib.load(config.TRAINING_FINAL_MODEL_PATH)
    mappings = artifact.get("category_mappings")
    if not mappings:
        raise ValueError("Final artifact is missing train-fitted category_mappings.")

    windows = split_validation_windows(load_validation())
    X_calibration, y_calibration, _ = to_pandas_xy_with_mappings(
        windows.calibration,
        mappings,
    )
    X_policy, y_policy, _ = to_pandas_xy_with_mappings(
        windows.policy,
        mappings,
    )
    y_calibration = y_calibration.to_numpy()
    y_policy = y_policy.to_numpy()
    raw_calibration = artifact["model"].predict_proba(X_calibration)[:, 1]
    raw_policy = artifact["model"].predict_proba(X_policy)[:, 1]

    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        raw_calibration,
        y_calibration,
    )
    calibrated_policy = np.asarray(calibrator.predict(raw_policy), dtype=float)
    table = threshold_table(y_policy, calibrated_policy)
    thresholds = choose_recall_first_threshold(table, min_precision=0.30)
    thresholds.update(
        {
            "calibration_window": "validation_calibration",
            "policy_window": "validation_policy",
            "selection_boundary": windows.selection_boundary,
            "calibration_boundary": windows.calibration_boundary,
        }
    )

    artifact["calibrator"] = calibrator
    artifact["threshold_config"] = thresholds
    artifact["calibration_method"] = "isotonic"
    joblib.dump(artifact, config.TRAINING_FINAL_MODEL_PATH)
    joblib.dump(calibrator, config.TRAINING_CALIBRATION_PATH)
    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(config.TRAINING_THRESHOLD_ANALYSIS_PATH, index=False)
    config.TRAINING_THRESHOLDS_PATH.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    raw_brier = float(np.mean((raw_policy - y_policy) ** 2))
    calibrated_brier = float(np.mean((calibrated_policy - y_policy) ** 2))
    metrics = {
        "raw_policy_brier_score": raw_brier,
        "calibration_brier_score": calibrated_brier,
        "calibration_improved": float(calibrated_brier <= raw_brier),
        "selected_review_threshold": thresholds["review_threshold"],
        "selected_reject_threshold": thresholds["reject_threshold"],
    }
    metadata = json.loads(config.TRAINING_METADATA_PATH.read_text(encoding="utf-8"))
    metadata.update(
        {
            "calibration_method": "isotonic",
            "threshold_config": thresholds,
            "policy_metrics": metrics,
            "validation_window_counts": windows.counts,
        }
    )
    config.TRAINING_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    with training_run("threshold_and_calibration"):
        mlflow.log_params(
            {
                "calibration_method": "isotonic",
                "calibration_rows": len(y_calibration),
                "policy_rows": len(y_policy),
                "validation_window_counts": json.dumps(windows.counts, sort_keys=True),
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.log_artifact(str(config.TRAINING_THRESHOLD_ANALYSIS_PATH), artifact_path="reports")
        mlflow.log_artifact(str(config.TRAINING_THRESHOLDS_PATH), artifact_path="metadata")
    print(json.dumps(metrics | thresholds, indent=2))


if __name__ == "__main__":
    main()
