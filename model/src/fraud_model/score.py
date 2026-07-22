"""Module đóng gói cuối cùng để Trung gọi từ backend (bàn giao Ngày 5, xem
docs/RISK_SCORING_PLAN.md mục 2 và 4).

Ưu tiên dùng `artifacts/final_model.joblib` (từ `tune_and_explain.py`, có
SHAP top-5 thật). Nếu chưa có — vd tuning trễ — dùng tạm
`artifacts/baseline_logreg.joblib` (Logistic Regression, không có SHAP) để
demo pipeline vẫn chạy được, đúng phương án dự phòng ở mục 5 ("Đóng gói
model trễ").
"""
import joblib
import pandas as pd

from . import config

_artifact = None
_explainer = None


def _load_artifact() -> dict:
    global _artifact
    if _artifact is None:
        if config.FINAL_MODEL_PATH.exists():
            _artifact = joblib.load(config.FINAL_MODEL_PATH)
        elif config.BASELINE_MODEL_PATH.exists():
            print("[score] final_model.joblib chưa có — dùng tạm baseline (xem docs mục 5).")
            _artifact = joblib.load(config.BASELINE_MODEL_PATH)
            _artifact.setdefault("model_name", "baseline_logreg")
        else:
            raise FileNotFoundError(
                "Chưa có model nào đã train. Chạy `uv run python -m fraud_model.train_baseline` "
                "(hoặc train_compare + tune_and_explain) trước."
            )
    return _artifact


def _get_explainer(model, model_name: str):
    global _explainer
    if _explainer is None:
        if model_name in config.TREE_MODEL_NAMES:
            import shap

            _explainer = shap.TreeExplainer(model)
        else:
            _explainer = False
    return _explainer


def score(features: dict) -> dict:
    """features: dict tên_cột -> giá trị cho 1 giao dịch.

    Trả về {"proba": float, "shap": [{"feature", "shap_value"}, ...] | None}.
    "shap" là None khi đang chạy fallback baseline (Logistic Regression).
    """
    artifact = _load_artifact()
    model = artifact["model"]
    columns = artifact["feature_columns"]
    model_name = artifact.get("model_name", "baseline_logreg")

    row = pd.DataFrame([{col: features.get(col, -999) for col in columns}], columns=columns)
    proba = float(model.predict_proba(row)[0, 1])

    explainer = _get_explainer(model, model_name)
    shap_top5 = None
    if explainer:
        shap_values = explainer.shap_values(row)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        contributions = sorted(
            zip(columns, shap_values[0]), key=lambda kv: abs(kv[1]), reverse=True
        )
        shap_top5 = [{"feature": name, "shap_value": float(val)} for name, val in contributions[:5]]

    return {"proba": proba, "shap": shap_top5}
