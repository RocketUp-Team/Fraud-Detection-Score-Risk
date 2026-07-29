"""Module đóng gói cuối cùng để Trung gọi từ backend (bàn giao Ngày 5, xem
docs/RISK_SCORING_PLAN.md mục 2 và 4).

Mặc định serving dùng model hiện hành `v2`. Artifact cũ được gom logic dưới
nhãn `v1`; các lần train mới nên ghi sang version riêng để không đè lên model
đang phục vụ. `score()` ưu tiên model cuối của serving version hiện tại, rồi
mới fallback sang baseline cùng version. Với `v1`, code còn hỗ trợ legacy root
artifact để tương thích ngược.
"""
import joblib
import pandas as pd

from . import config
from .features import encode_categoricals_pandas

_artifact = None
_explainer = None


def _candidate_paths(kind: str) -> list:
    version = config.SERVING_MODEL_VERSION
    if kind == "final":
        primary = config.SERVING_FINAL_MODEL_PATH
        legacy = config.ARTIFACTS_DIR / "final_model.joblib"
    else:
        primary = config.SERVING_BASELINE_MODEL_PATH
        legacy = config.ARTIFACTS_DIR / "baseline_logreg.joblib"
    if version == "v1":
        return [primary, legacy]
    return [primary]


def _load_artifact() -> dict:
    global _artifact
    if _artifact is None:
        for candidate in _candidate_paths("final"):
            if candidate.exists():
                _artifact = joblib.load(candidate)
                break
        if _artifact is None:
            baseline_candidates = _candidate_paths("baseline")
            existing_baseline = next((p for p in baseline_candidates if p.exists()), None)
            if existing_baseline is not None:
                print("[score] final model chưa có — dùng tạm baseline cùng serving version.")
                _artifact = joblib.load(existing_baseline)
                _artifact.setdefault("model_name", "baseline_logreg")
                _artifact.setdefault("model_version", config.SERVING_MODEL_VERSION)
            else:
                raise FileNotFoundError(
                    "Chưa có model nào cho serving version hiện tại. Chạy training cho version đó trước."
                )
        if _artifact.get("model_version") is None:
            _artifact["model_version"] = config.SERVING_MODEL_VERSION
            _artifact.setdefault("model_name", "baseline_logreg")
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
        "processing_version": artifact.get("processing_version"),
        "feature_schema_version": artifact.get("feature_schema_version"),
        "threshold": artifact.get("threshold", artifact.get("threshold_config", {}).get("review_threshold")),
        "threshold_config": artifact.get("threshold_config"),
        "risk_band_policy_version": artifact.get("risk_band_policy_version"),
        "explainability": model_name in config.TREE_MODEL_NAMES,
        "n_features": len(artifact["feature_columns"]),
        "required_features": artifact.get("required_features", artifact.get("feature_columns", [])),
        "optional_features": artifact.get("optional_features", []),
        "defaultable_features": artifact.get("defaultable_features", []),
    }


def feature_columns() -> list[str]:
    """Danh sách cột feature model mong đợi, đúng thứ tự lúc train.

    Backend cần để (1) sinh file CSV mẫu có đúng header, (2) báo cho người dùng
    file họ upload khớp bao nhiêu cột trong tổng số.
    """
    return list(_load_artifact()["feature_columns"])


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
    required_features = set(artifact.get("required_features", columns))
    defaultable_features = set(artifact.get("defaultable_features", []))
    optional_features = set(artifact.get("optional_features", []))

    missing_required = sorted(
        feature
        for feature in required_features
        if feature not in features and feature not in defaultable_features and feature not in optional_features
    )
    if missing_required:
        raise ValueError(
            "Thiếu required features cho full-feature scoring: "
            + ", ".join(missing_required[:10])
            + ("..." if len(missing_required) > 10 else "")
        )

    encoded = encode_categoricals_pandas(features, mappings)
    # Cột THIẾU và cột CÓ nhưng giá trị None đều phải thành -999. Chỉ dùng
    # `.get(col, -999)` là không đủ: giá trị None vẫn đi qua, làm cột đó thành
    # dtype object và LightGBM báo "pandas dtypes must be int, float or bool".
    # Gặp ngay khi nhập CSV có ô trống — dữ liệu thật lúc nào cũng có ô trống.
    row = pd.DataFrame(
        [{col: (-999 if encoded.get(col) is None else encoded.get(col)) for col in columns}],
        columns=columns,
    )
    proba = float(model.predict_proba(row)[0, 1])
    calibrator = artifact.get("calibrator")
    if calibrator is not None:
        proba = float(calibrator.predict([proba])[0])

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

    scoring_mode = "full_feature" if len(set(features).intersection(columns)) >= len(columns) else "partial_demo"
    return {
        "proba": max(0.0, min(1.0, proba)),
        "shap": shap_top5,
        "scoring_mode": scoring_mode,
        "threshold_config": artifact.get("threshold_config"),
    }
