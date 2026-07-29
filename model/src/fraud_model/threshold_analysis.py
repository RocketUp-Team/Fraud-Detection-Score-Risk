"""Fit calibration and choose operating thresholds using validation only."""
from __future__ import annotations

import json

import joblib
import mlflow
import numpy as np
from sklearn.isotonic import IsotonicRegression

from . import config
from .data import load_train_weighted, load_validation
from .evaluation import choose_recall_first_threshold, threshold_table
from .features import apply_categorical_indexer, fit_categorical_indexer, _canonical_feature_columns
from .tracking import training_run


def _xy(df, indexer):
    df = apply_categorical_indexer(indexer, df).orderBy(config.TIME_COL)
    pdf = df.toPandas()
    columns = _canonical_feature_columns() or [c for c in pdf.columns if c not in {config.ID_COL, config.TIME_COL, config.TARGET_COL, config.WEIGHT_COL}]
    return pdf.loc[:, columns], pdf[config.TARGET_COL].to_numpy()


def main() -> None:
    artifact = joblib.load(config.TRAINING_FINAL_MODEL_PATH)
    train_df = load_train_weighted()
    val_df = load_validation()
    indexer = fit_categorical_indexer(train_df)
    X_val, y_val = _xy(val_df, indexer)
    raw_proba = artifact["model"].predict_proba(X_val)[:, 1]

    split = max(1, len(y_val) // 2)
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(raw_proba[:split], y_val[:split])
    calibrated = np.asarray(calibrator.predict(raw_proba), dtype=float)
    table = threshold_table(y_val[split:], calibrated[split:])
    thresholds = choose_recall_first_threshold(table, min_precision=0.30)

    artifact["calibrator"] = calibrator
    artifact["threshold_config"] = thresholds
    artifact["calibration_method"] = "isotonic"
    joblib.dump(artifact, config.TRAINING_FINAL_MODEL_PATH)
    joblib.dump(calibrator, config.TRAINING_CALIBRATION_PATH)
    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(config.TRAINING_THRESHOLD_ANALYSIS_PATH, index=False)
    config.TRAINING_THRESHOLDS_PATH.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    metadata = json.loads(config.TRAINING_METADATA_PATH.read_text(encoding="utf-8"))
    metadata.update({"calibration_method": "isotonic", "threshold_config": thresholds})
    config.TRAINING_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    metrics = {
        "calibration_brier_score": float(np.mean((calibrated[split:] - y_val[split:]) ** 2)),
        "selected_review_threshold": thresholds["review_threshold"],
        "selected_reject_threshold": thresholds["reject_threshold"],
    }
    with training_run("threshold_and_calibration"):
        mlflow.log_params({"calibration_method": "isotonic", "calibration_rows": split, "threshold_rows": len(y_val) - split})
        mlflow.log_metrics(metrics)
        mlflow.log_artifact(str(config.TRAINING_THRESHOLD_ANALYSIS_PATH), artifact_path="reports")
        mlflow.log_artifact(str(config.TRAINING_THRESHOLDS_PATH), artifact_path="metadata")
    print(json.dumps(metrics | thresholds, indent=2))


if __name__ == "__main__":
    main()
