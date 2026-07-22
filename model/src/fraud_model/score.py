"""Module đóng gói cuối cùng để Trung gọi từ backend (bàn giao Ngày 5,
xem docs/RISK_SCORING_PLAN.md mục 2 và 4).

Hiện tại (Ngày 1) chỉ là stub dùng baseline Logistic Regression và không
trả SHAP thật — sẽ được thay bằng model tốt nhất (LightGBM/XGBoost/CatBoost)
đã tuning + giải thích SHAP thật sau Ngày 4.
"""
import joblib
import pandas as pd

from . import config

_artifact = None


def _load_artifact():
    global _artifact
    if _artifact is None:
        if not config.BASELINE_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Chưa có model đã train tại {config.BASELINE_MODEL_PATH}. "
                "Chạy `uv run python -m fraud_model.train_baseline` trước."
            )
        _artifact = joblib.load(config.BASELINE_MODEL_PATH)
    return _artifact


def score(features: dict) -> dict:
    """features: dict tên_cột -> giá trị cho 1 giao dịch.

    Trả về {"proba": float, "shap": None}. "shap" sẽ được điền top-5
    feature importance thật sau khi model cuối được đóng gói.
    """
    artifact = _load_artifact()
    model = artifact["model"]
    columns = artifact["feature_columns"]

    row = pd.DataFrame([{col: features.get(col, -999) for col in columns}], columns=columns)
    proba = float(model.predict_proba(row)[0, 1])

    return {"proba": proba, "shap": None}
