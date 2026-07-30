"""Evaluate evidence gates without changing the serving model version."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime

import mlflow

from . import config
from .tracking import training_run


REFERENCE_V2_PR_AUC = 0.4582
MIN_ROC_AUC = 0.8746
MIN_PRECISION = 0.30


def _sha256(path=None) -> str:
    path = path or config.TRAINING_FINAL_MODEL_PATH
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(
        config.TRAINING_CANDIDATE_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    metadata = json.loads(config.TRAINING_METADATA_PATH.read_text(encoding="utf-8"))
    with config.TRAINING_HOLDOUT_METRICS_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        metrics = next(csv.DictReader(handle))
    numeric = {key: float(value) for key, value in metrics.items()}

    verification_path = config.PROCESSED_DATA_ROOT / "reports" / "verification_report.json"
    data_verification_status = "missing"
    if verification_path.is_file():
        data_verification_status = json.loads(
            verification_path.read_text(encoding="utf-8")
        ).get("status", "unknown")

    gates = {
        "holdout_pr_auc": numeric["pr_auc"] >= REFERENCE_V2_PR_AUC,
        "holdout_roc_auc": numeric["roc_auc"] >= MIN_ROC_AUC,
        "review_precision": numeric["precision"] >= MIN_PRECISION,
        "calibration_non_regression": (
            numeric["brier_score"] <= numeric["raw_brier_score"]
        ),
        "artifact_checksum": _sha256() == manifest["artifact_sha256"],
        "artifact_load_smoke": manifest.get("artifact_load_smoke") == "passed",
        "data_contract_verification": (
            data_verification_status == "ready_for_downstream_training"
        ),
        "version_match": (
            manifest.get("candidate_version") == config.TRAINING_MODEL_VERSION
            and metadata.get("model_version") == config.TRAINING_MODEL_VERSION
        ),
        "git_clean": manifest.get("git_dirty") == "false",
    }
    all_passed = all(gates.values())
    status = "eligible_for_promotion_review" if all_passed else "not_promoted"
    decision = {
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_version": config.TRAINING_MODEL_VERSION,
        "status": status,
        "automatic_promotion": False,
        "reference_v2_pr_auc": REFERENCE_V2_PR_AUC,
        "minimum_roc_auc": MIN_ROC_AUC,
        "minimum_precision": MIN_PRECISION,
        "data_verification_status": data_verification_status,
        "metrics": numeric,
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "serving_version_unchanged": True,
    }
    config.TRAINING_PROMOTION_DECISION_PATH.write_text(
        json.dumps(decision, indent=2),
        encoding="utf-8",
    )
    metadata["promotion_status"] = status
    metadata["promotion_decision"] = str(config.TRAINING_PROMOTION_DECISION_PATH)
    config.TRAINING_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    manifest["promotion_status"] = status
    manifest["promotion_decision"] = str(config.TRAINING_PROMOTION_DECISION_PATH)
    manifest.setdefault("checksums", {}).update(
        {
            config.TRAINING_METADATA_PATH.name: _sha256(
                config.TRAINING_METADATA_PATH
            ),
            config.TRAINING_PROMOTION_DECISION_PATH.name: _sha256(
                config.TRAINING_PROMOTION_DECISION_PATH
            ),
        }
    )
    config.TRAINING_CANDIDATE_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    with training_run("promotion_gate"):
        mlflow.log_params(
            {
                "reference_v2_pr_auc": REFERENCE_V2_PR_AUC,
                "minimum_roc_auc": MIN_ROC_AUC,
                "minimum_precision": MIN_PRECISION,
                "automatic_promotion": False,
            }
        )
        mlflow.log_metrics(
            {f"gate_{name}": float(passed) for name, passed in gates.items()}
        )
        mlflow.log_artifact(
            str(config.TRAINING_PROMOTION_DECISION_PATH),
            artifact_path="promotion",
        )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
