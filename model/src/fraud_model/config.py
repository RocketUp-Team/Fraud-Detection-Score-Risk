from pathlib import Path

MODEL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = MODEL_ROOT.parent
ARTIFACTS_DIR = MODEL_ROOT / "artifacts"

# Fallback (dev/test khi chưa có pipeline thật của An, xem synthetic_data.py)
RAW_DATA_DIR = MODEL_ROOT / "data" / "raw"
TRAIN_TRANSACTION_FILE = RAW_DATA_DIR / "train_transaction.csv"
TRAIN_IDENTITY_FILE = RAW_DATA_DIR / "train_identity.csv"

# Feature contract thật từ An — xem data/ieee_cis/HANDOVER_TO_QUAN.md,
# DATA_DICTIONARY.md. Tạo bằng: docker compose -f
# docker-compose.preprocessing.yml run --rm preprocess (chạy ở repo root).
MODEL_READY_DIR = REPO_ROOT / "data" / "processed" / "ieee_cis_fraud_risk" / "model_ready"

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
