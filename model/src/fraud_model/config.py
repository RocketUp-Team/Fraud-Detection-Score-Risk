from pathlib import Path

MODEL_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = MODEL_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = MODEL_ROOT / "data" / "processed"
ARTIFACTS_DIR = MODEL_ROOT / "artifacts"

TRAIN_TRANSACTION_FILE = RAW_DATA_DIR / "train_transaction.csv"
TRAIN_IDENTITY_FILE = RAW_DATA_DIR / "train_identity.csv"

ID_COL = "TransactionID"
TIME_COL = "TransactionDT"
TARGET_COL = "isFraud"

# Holdout theo thời gian (20% giao dịch cuối theo TransactionDT) — tránh
# leakage, xem docs/RISK_SCORING_PLAN.md mục 5.
VAL_FRACTION = 0.2

BASELINE_MODEL_PATH = ARTIFACTS_DIR / "baseline_logreg.joblib"
COMPARISON_RESULTS_PATH = ARTIFACTS_DIR / "model_comparison.json"
FINAL_MODEL_PATH = ARTIFACTS_DIR / "final_model.joblib"

TREE_MODEL_NAMES = {"lightgbm", "xgboost", "catboost"}
