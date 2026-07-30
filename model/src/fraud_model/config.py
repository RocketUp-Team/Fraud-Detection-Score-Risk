from pathlib import Path
import os

MODEL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = MODEL_ROOT.parent
ARTIFACTS_DIR = MODEL_ROOT / "artifacts"
V1_ARTIFACTS_DIR = ARTIFACTS_DIR / "v1"
V2_ARTIFACTS_DIR = ARTIFACTS_DIR / "v2"

# Fallback (dev/test khi chưa có pipeline thật của An, xem synthetic_data.py)
RAW_DATA_DIR = MODEL_ROOT / "data" / "raw"
TRAIN_TRANSACTION_FILE = RAW_DATA_DIR / "train_transaction.csv"
TRAIN_IDENTITY_FILE = RAW_DATA_DIR / "train_identity.csv"

# Feature contract thật từ An — xem data/ieee_cis/HANDOVER_TO_QUAN.md,
# DATA_DICTIONARY.md. Tạo bằng: docker compose -f
# docker-compose.preprocessing.yml run --rm preprocess (chạy ở repo root).
DEFAULT_PROCESSED_DATA_ROOT = (
    REPO_ROOT / "data" / "processed" / "ieee_cis_fraud_risk"
)
PROCESSED_DATA_ROOT = Path(
    os.environ.get("FRAUD_MODEL_DATA_ROOT", str(DEFAULT_PROCESSED_DATA_ROOT))
).expanduser().resolve()
MODEL_READY_DIR = PROCESSED_DATA_ROOT / "model_ready"

ID_COL = "TransactionID"
TIME_COL = "TransactionDT"
TARGET_COL = "isFraud"
WEIGHT_COL = "class_weight"

CATEGORICAL_COLS = ["ProductCD", "card4", "card6", "DeviceType", "device_family", "M4", "amount_band"]

# Giữ cho pipeline placeholder cũ (synthetic_data.py) — không dùng khi train
# bằng dữ liệu thật của An.
VAL_FRACTION = 0.2

BASELINE_MODEL_PATH = ARTIFACTS_DIR / "baseline_logreg.joblib"
COMPARISON_RESULTS_PATH = ARTIFACTS_DIR / "model_comparison.json"
FINAL_MODEL_PATH = ARTIFACTS_DIR / "final_model.joblib"

TREE_MODEL_NAMES = {"lightgbm", "xgboost", "catboost"}

# V2 passed offline holdout gates and is now the production default. Roll back
# without changing code by setting FRAUD_MODEL_SERVING_VERSION=v1.
SERVING_MODEL_VERSION = os.environ.get("FRAUD_MODEL_SERVING_VERSION", "v2")
TRAINING_MODEL_VERSION = os.environ.get("FRAUD_MODEL_TRAINING_VERSION", "v2")
RANDOM_SEED = int(os.environ.get("FRAUD_MODEL_RANDOM_SEED", "42"))


def _artifact_dir_for(version: str) -> Path:
    if version == "v1":
        return V1_ARTIFACTS_DIR
    if version == "v2":
        return V2_ARTIFACTS_DIR
    return ARTIFACTS_DIR / version


def _artifact_paths_for(version: str) -> dict[str, Path]:
    artifact_dir = _artifact_dir_for(version)
    return {
        "dir": artifact_dir,
        "baseline": artifact_dir / f"baseline_logreg_{version}.joblib",
        "comparison": artifact_dir / f"model_comparison_{version}.json",
        "final": artifact_dir / f"final_model_{version}.joblib",
        "metadata": artifact_dir / f"training_metadata_{version}.json",
        "calibration": artifact_dir / f"calibration_model_{version}.joblib",
        "thresholds": artifact_dir / f"threshold_config_{version}.json",
        "validation_metrics": artifact_dir / f"validation_metrics_{version}.csv",
        "holdout_metrics": artifact_dir / f"holdout_metrics_{version}.csv",
        "threshold_analysis": artifact_dir / f"threshold_analysis_{version}.csv",
        "candidate_manifest": artifact_dir / f"candidate_manifest_{version}.json",
        "checksum": artifact_dir / f"checksum_{version}.sha256",
        "promotion_decision": artifact_dir / f"promotion_decision_{version}.json",
    }


SERVING_ARTIFACT_PATHS = _artifact_paths_for(SERVING_MODEL_VERSION)
TRAINING_ARTIFACT_PATHS = _artifact_paths_for(TRAINING_MODEL_VERSION)

SERVING_ARTIFACTS_DIR = SERVING_ARTIFACT_PATHS["dir"]
SERVING_BASELINE_MODEL_PATH = SERVING_ARTIFACT_PATHS["baseline"]
SERVING_COMPARISON_RESULTS_PATH = SERVING_ARTIFACT_PATHS["comparison"]
SERVING_FINAL_MODEL_PATH = SERVING_ARTIFACT_PATHS["final"]

TRAINING_ARTIFACTS_DIR = TRAINING_ARTIFACT_PATHS["dir"]
TRAINING_BASELINE_MODEL_PATH = TRAINING_ARTIFACT_PATHS["baseline"]
TRAINING_COMPARISON_RESULTS_PATH = TRAINING_ARTIFACT_PATHS["comparison"]
TRAINING_FINAL_MODEL_PATH = TRAINING_ARTIFACT_PATHS["final"]
TRAINING_METADATA_PATH = TRAINING_ARTIFACT_PATHS["metadata"]
TRAINING_CALIBRATION_PATH = TRAINING_ARTIFACT_PATHS["calibration"]
TRAINING_THRESHOLDS_PATH = TRAINING_ARTIFACT_PATHS["thresholds"]
TRAINING_VALIDATION_METRICS_PATH = TRAINING_ARTIFACT_PATHS["validation_metrics"]
TRAINING_HOLDOUT_METRICS_PATH = TRAINING_ARTIFACT_PATHS["holdout_metrics"]
TRAINING_THRESHOLD_ANALYSIS_PATH = TRAINING_ARTIFACT_PATHS["threshold_analysis"]
TRAINING_CANDIDATE_MANIFEST_PATH = TRAINING_ARTIFACT_PATHS["candidate_manifest"]
TRAINING_CHECKSUM_PATH = TRAINING_ARTIFACT_PATHS["checksum"]
TRAINING_PROMOTION_DECISION_PATH = TRAINING_ARTIFACT_PATHS["promotion_decision"]

# Legacy names kept for backward compatibility with old tests/scripts. These
# now point to the CURRENT TRAINING target, not the currently served model.
BASELINE_MODEL_PATH = TRAINING_BASELINE_MODEL_PATH
COMPARISON_RESULTS_PATH = TRAINING_COMPARISON_RESULTS_PATH
FINAL_MODEL_PATH = TRAINING_FINAL_MODEL_PATH
