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
from .features import encode_categoricals_pandas

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


def model_info() -> dict:
    """Metadata model đang phục vụ, cho backend trả về `GET /meta` và gắn
    `model_version` vào từng bản ghi đã chấm điểm.

    `explainability` = False khi đang chạy fallback baseline (không có SHAP),
    để frontend biết mà hiển thị đúng thay vì tưởng model lỗi.
    """
    artifact = _load_artifact()
    model_name = artifact.get("model_name", "baseline_logreg")
    return {
        "model_name": model_name,
        "model_version": artifact.get("model_version", model_name),
        "explainability": model_name in config.TREE_MODEL_NAMES,
        "n_features": len(artifact["feature_columns"]),
    }


def warm_up() -> dict:
    """Load model + explainer sẵn lúc startup để request đầu tiên không phải
    chịu chi phí load joblib/SHAP. Trả về `model_info()`."""
    artifact = _load_artifact()
    _get_explainer(artifact["model"], artifact.get("model_name", "baseline_logreg"))
    return model_info()


def score(features: dict) -> dict:
    """features: dict tên_cột -> giá trị thô cho 1 giao dịch (cột categorical
    như `ProductCD`/`card4`... nhận giá trị string gốc, vd "W"/"visa").

    Trả về {"proba": float, "shap": [{"feature", "shap_value"}, ...] | None}.
    "shap" là None khi đang chạy fallback baseline (Logistic Regression).
    """
    artifact = _load_artifact()
    model = artifact["model"]
    columns = artifact["feature_columns"]
    model_name = artifact.get("model_name", "baseline_logreg")
    mappings = artifact.get("category_mappings", {})

    encoded = encode_categoricals_pandas(features, mappings)
    row = pd.DataFrame([{col: encoded.get(col, -999) for col in columns}], columns=columns)
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
