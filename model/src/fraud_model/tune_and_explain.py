"""Ngày 4: tuning model tốt nhất (chọn từ `train_compare.py`) + sinh giải
thích SHAP (Quân).

Chỉ tuning bằng lưới tham số nhỏ trên 1 tập validation theo thời gian (không
cross-validation đầy đủ) — phù hợp giới hạn 8 ngày, xem
docs/RISK_SCORING_PLAN.md mục 1. Nếu model tốt nhất không phải mô hình cây
(vd logreg thắng), dừng lại và dùng tạm baseline cho demo (mục 5, rủi ro
"Đóng gói model trễ").

Chạy:
    uv run python -m fraud_model.train_compare   # trước, để có model_comparison.json
    uv run python -m fraud_model.tune_and_explain
"""
import itertools
import json

import joblib
import numpy as np
import shap
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier

from . import config
from .data import DatasetNotFoundError, load_merged, time_based_split
from .features import prepare_baseline_features, to_pandas_xy

PARAM_GRIDS = {
    "lightgbm": [
        {"n_estimators": n, "max_depth": d, "learning_rate": lr, "class_weight": "balanced", "verbosity": -1}
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
    "xgboost": [
        {"n_estimators": n, "max_depth": d, "learning_rate": lr, "eval_metric": "aucpr"}
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
    "catboost": [
        {"iterations": n, "depth": d, "learning_rate": lr, "auto_class_weights": "Balanced", "verbose": False}
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
}

MODEL_CLASSES = {
    "lightgbm": LGBMClassifier,
    "xgboost": XGBClassifier,
    "catboost": CatBoostClassifier,
}


def _load_best_model_name() -> str:
    if not config.COMPARISON_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Chưa có {config.COMPARISON_RESULTS_PATH}. Chạy "
            "`uv run python -m fraud_model.train_compare` trước."
        )
    with open(config.COMPARISON_RESULTS_PATH) as f:
        return json.load(f)["best_model"]


def main() -> None:
    try:
        df = load_merged()
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    best_name = _load_best_model_name()
    if best_name not in config.TREE_MODEL_NAMES:
        raise SystemExit(
            f"Model tốt nhất '{best_name}' không phải mô hình cây — bỏ qua tuning/SHAP, "
            "dùng tạm baseline Logistic Regression để demo (xem docs mục 5)."
        )

    train_df, val_df = time_based_split(df)
    X_train, y_train = to_pandas_xy(prepare_baseline_features(train_df))
    X_val, y_val = to_pandas_xy(prepare_baseline_features(val_df))
    X_val = X_val.reindex(columns=X_train.columns, fill_value=-999)

    model_cls = MODEL_CLASSES[best_name]
    best_model, best_pr_auc, best_params = None, -1.0, None
    for params in PARAM_GRIDS[best_name]:
        model = model_cls(**params)
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_val)[:, 1]
        pr_auc = average_precision_score(y_val, proba)
        if pr_auc > best_pr_auc:
            best_model, best_pr_auc, best_params = model, pr_auc, params

    roc_auc = roc_auc_score(y_val, best_model.predict_proba(X_val)[:, 1])
    print(f"[tune] best {best_name} params={best_params}")
    print(f"[tune] ROC-AUC={roc_auc:.4f}  PR-AUC={best_pr_auc:.4f}")

    explainer = shap.TreeExplainer(best_model)
    shap_values = explainer.shap_values(X_val)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    top5_idx = np.argsort(mean_abs_shap)[::-1][:5]
    top5_global_features = [
        {"feature": X_val.columns[i], "mean_abs_shap": float(mean_abs_shap[i])} for i in top5_idx
    ]
    print(f"[tune] top-5 feature (SHAP trung bình |giá trị|): {top5_global_features}")

    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": best_model,
            "model_name": best_name,
            "feature_columns": list(X_train.columns),
            "val_roc_auc": roc_auc,
            "val_pr_auc": best_pr_auc,
            "top5_global_features": top5_global_features,
        },
        config.FINAL_MODEL_PATH,
    )
    print(f"[tune] saved -> {config.FINAL_MODEL_PATH}")


if __name__ == "__main__":
    main()
