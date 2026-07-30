"""Package a frozen candidate with deterministic lineage and smoke evidence."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import joblib

from . import config
from .data import load_validation, split_validation_windows
from .features import to_pandas_xy_with_mappings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    required_paths = [
        config.TRAINING_FINAL_MODEL_PATH,
        config.TRAINING_METADATA_PATH,
        config.TRAINING_THRESHOLDS_PATH,
        config.TRAINING_VALIDATION_METRICS_PATH,
        config.TRAINING_HOLDOUT_METRICS_PATH,
        config.TRAINING_THRESHOLD_ANALYSIS_PATH,
    ]
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Candidate package is incomplete: {missing}")

    artifact = joblib.load(config.TRAINING_FINAL_MODEL_PATH)
    metadata = json.loads(config.TRAINING_METADATA_PATH.read_text(encoding="utf-8"))
    for key in [
        "model",
        "model_name",
        "model_version",
        "feature_columns",
        "category_mappings",
        "processing_version",
        "feature_schema_version",
        "calibrator",
        "threshold_config",
        "holdout_metrics",
        "holdout_mlflow_run_id",
    ]:
        if artifact.get(key) is None:
            raise ValueError(f"Final model artifact is missing required field: {key}")
    if artifact["model_version"] != config.TRAINING_MODEL_VERSION:
        raise ValueError(
            f"Artifact version {artifact['model_version']} does not match "
            f"training target {config.TRAINING_MODEL_VERSION}"
        )

    # Score one policy-window row using only frozen mappings/calibration.
    policy_sample = split_validation_windows(load_validation()).policy.limit(1)
    X_sample, _, _ = to_pandas_xy_with_mappings(
        policy_sample,
        artifact["category_mappings"],
    )
    raw_probability = float(artifact["model"].predict_proba(X_sample)[0, 1])
    probability = float(artifact["calibrator"].predict([raw_probability])[0])
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"Candidate probability is outside [0, 1]: {probability}")

    artifact_sha256 = _sha256(config.TRAINING_FINAL_MODEL_PATH)
    config.TRAINING_CHECKSUM_PATH.write_text(
        f"{artifact_sha256}  {config.TRAINING_FINAL_MODEL_PATH.name}\n",
        encoding="utf-8",
    )
    metadata["candidate_manifest"] = str(config.TRAINING_CANDIDATE_MANIFEST_PATH)
    metadata["artifact_sha256"] = artifact_sha256
    metadata["promotion_status"] = "pending_review"
    config.TRAINING_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    checksums = {path.name: _sha256(path) for path in required_paths}
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_version": config.TRAINING_MODEL_VERSION,
        "promotion_status": "pending_review",
        "data_root": str(config.PROCESSED_DATA_ROOT),
        "processing_version": artifact["processing_version"],
        "feature_schema_version": artifact["feature_schema_version"],
        "model_name": artifact["model_name"],
        "feature_count": len(artifact["feature_columns"]),
        "holdout_mlflow_run_id": artifact["holdout_mlflow_run_id"],
        "spark_master": os.environ.get("SPARK_MASTER_URL", "local[*]"),
        "artifact_load_smoke": "passed",
        "smoke_probability": probability,
        "artifact_sha256": artifact_sha256,
        "checksums": checksums,
        "required_files": [path.name for path in required_paths],
    }
    config.TRAINING_CANDIDATE_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
