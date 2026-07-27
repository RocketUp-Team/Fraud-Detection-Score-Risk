"""Ngày 4: tuning model tốt nhất (chọn từ `train_compare.py`) + SHAP, trên
feature contract thật của An (Quân).

Tuning bằng lưới tham số nhỏ, chọn theo PR-AUC trên `validation` (không
cross-validation đầy đủ — phù hợp giới hạn 8 ngày). Sau khi chốt tham số,
đánh giá model cuối trên `holdout` ĐÚNG MỘT LẦN — xem
data/ieee_cis/HANDOVER_TO_QUAN.md mục leakage precautions ("Select the model
and threshold on validation; evaluate holdout only once after selection").

Nếu model tốt nhất không phải mô hình cây, dừng lại và dùng tạm baseline cho
demo (docs/RISK_SCORING_PLAN.md mục 5, rủi ro "Đóng gói model trễ").

Chạy:
    uv run python -m fraud_model.train_compare   # trước, để có model_comparison_<version>.json
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
from .data import DatasetNotFoundError, load_holdout, load_train_weighted, load_validation
from .features import (
    align_feature_columns,
    apply_categorical_indexer,
    extract_category_mappings,
    fit_categorical_indexer,
    to_pandas_xy,
)

PARAM_GRIDS = {
    "lightgbm": [
        {"n_estimators": n, "max_depth": d, "learning_rate": lr, "verbosity": -1}
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
    "xgboost": [
        {"n_estimators": n, "max_depth": d, "learning_rate": lr, "eval_metric": "aucpr"}
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
    "catboost": [
        {"iterations": n, "depth": d, "learning_rate": lr, "verbose": False}
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
}

MODEL_CLASSES = {
    "lightgbm": LGBMClassifier,
    "xgboost": XGBClassifier,
    "catboost": CatBoostClassifier,
}


def _load_best_model_name() -> str:
    if not config.TRAINING_COMPARISON_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Chưa có {config.TRAINING_COMPARISON_RESULTS_PATH}. Chạy "
            "`uv run python -m fraud_model.train_compare` trước."
        )
    with open(config.TRAINING_COMPARISON_RESULTS_PATH) as f:
        return json.load(f)["best_model"]


def main() -> None:
    best_name = _load_best_model_name()
    if best_name not in config.TREE_MODEL_NAMES:
        raise SystemExit(
            f"Model tốt nhất '{best_name}' không phải mô hình cây — bỏ qua tuning/SHAP, "
            "dùng tạm baseline Logistic Regression để demo (xem docs mục 5)."
        )

    try:
        train_df = load_train_weighted()
        val_df = load_validation()
        holdout_df = load_holdout()
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    indexer = fit_categorical_indexer(train_df)
    train_df = apply_categorical_indexer(indexer, train_df)
    val_df = apply_categorical_indexer(indexer, val_df)
    holdout_df = apply_categorical_indexer(indexer, holdout_df)

    X_train, y_train, w_train = to_pandas_xy(train_df)
    X_val, y_val, _ = to_pandas_xy(val_df)
    X_val = align_feature_columns(X_val, list(X_train.columns))
    X_holdout, y_holdout, _ = to_pandas_xy(holdout_df)
    X_holdout = align_feature_columns(X_holdout, list(X_train.columns))

    model_cls = MODEL_CLASSES[best_name]
    best_model, best_pr_auc, best_params = None, -1.0, None
    for params in PARAM_GRIDS[best_name]:
        model = model_cls(**params)
        model.fit(X_train, y_train, sample_weight=w_train)
        proba = model.predict_proba(X_val)[:, 1]
        pr_auc = average_precision_score(y_val, proba)
        if pr_auc > best_pr_auc:
            best_model, best_pr_auc, best_params = model, pr_auc, params

    val_roc_auc = roc_auc_score(y_val, best_model.predict_proba(X_val)[:, 1])
    print(f"[tune] best {best_name} params={best_params}")
    print(f"[tune] validation ROC-AUC={val_roc_auc:.4f}  PR-AUC={best_pr_auc:.4f}")

    # Đánh giá holdout đúng một lần, sau khi đã chốt model + tham số trên validation.
    holdout_proba = best_model.predict_proba(X_holdout)[:, 1]
    holdout_roc_auc = roc_auc_score(y_holdout, holdout_proba)
    holdout_pr_auc = average_precision_score(y_holdout, holdout_proba)
    print(f"[tune] holdout (đánh giá 1 lần) ROC-AUC={holdout_roc_auc:.4f}  PR-AUC={holdout_pr_auc:.4f}")

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

    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": best_model,
            "model_name": best_name,
            "model_version": config.TRAINING_MODEL_VERSION,
            "feature_columns": list(X_train.columns),
            "category_mappings": extract_category_mappings(indexer),
            "val_roc_auc": val_roc_auc,
            "val_pr_auc": best_pr_auc,
            "holdout_roc_auc": holdout_roc_auc,
            "holdout_pr_auc": holdout_pr_auc,
            "top5_global_features": top5_global_features,
        },
        config.TRAINING_FINAL_MODEL_PATH,
    )
    with open(config.TRAINING_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model_version": config.TRAINING_MODEL_VERSION,
                "best_model": best_name,
                "artifact_path": str(config.TRAINING_FINAL_MODEL_PATH),
                "comparison_path": str(config.TRAINING_COMPARISON_RESULTS_PATH),
                "validation_roc_auc": val_roc_auc,
                "validation_pr_auc": best_pr_auc,
                "holdout_roc_auc": holdout_roc_auc,
                "holdout_pr_auc": holdout_pr_auc,
                "feature_count": len(X_train.columns),
            },
            f,
            indent=2,
        )
    print(f"[tune] saved -> {config.TRAINING_FINAL_MODEL_PATH}")


if __name__ == "__main__":
    main()
