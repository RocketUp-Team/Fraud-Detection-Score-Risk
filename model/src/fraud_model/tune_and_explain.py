"""Tuning model tốt nhất (chọn từ `train_compare.py`) + SHAP, trên
feature contract thật của An (Quân).

Tuning bằng lưới tham số nhỏ, chọn theo PR-AUC trên `validation`. Holdout
được đánh giá riêng bởi `evaluate_holdout.py` sau calibration và threshold.

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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from . import config
from .data import (
    DatasetNotFoundError,
    load_train_balanced,
    load_train_weighted,
    load_validation,
    split_validation_windows,
)
from .evaluation import binary_metrics
from .features import (
    align_feature_columns,
    apply_categorical_indexer,
    extract_category_mappings,
    feature_contract_metadata,
    fit_categorical_indexer,
    to_pandas_xy,
)
from .tracking import log_completed_run

PARAM_GRIDS = {
    "logreg": [{"max_iter": 1000, "random_state": config.RANDOM_SEED}],
    "lightgbm": [
        {
            "n_estimators": n,
            "max_depth": d,
            "learning_rate": lr,
            "verbosity": -1,
            "random_state": config.RANDOM_SEED,
            "deterministic": True,
            "force_col_wise": True,
        }
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
    "xgboost": [
        {
            "n_estimators": n,
            "max_depth": d,
            "learning_rate": lr,
            "eval_metric": "aucpr",
            "random_state": config.RANDOM_SEED,
        }
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
    "catboost": [
        {
            "iterations": n,
            "depth": d,
            "learning_rate": lr,
            "verbose": False,
            "random_seed": config.RANDOM_SEED,
        }
        for n, d, lr in itertools.product([200, 400], [4, 6], [0.05, 0.1])
    ],
}

MODEL_CLASSES = {
    "logreg": LogisticRegression,
    "lightgbm": LGBMClassifier,
    "xgboost": XGBClassifier,
    "catboost": CatBoostClassifier,
}


def _load_best_model_name() -> tuple[str, str]:
    if not config.TRAINING_COMPARISON_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Chưa có {config.TRAINING_COMPARISON_RESULTS_PATH}. Chạy "
            "`uv run python -m fraud_model.train_compare` trước."
        )
    with open(config.TRAINING_COMPARISON_RESULTS_PATH) as f:
        payload = json.load(f)
        best = payload["best_model"]
        return best.split("__", 1)[0], "balanced" if best.endswith("__balanced") else "weighted"


def main() -> None:
    best_name, dataset_variant = _load_best_model_name()
    if best_name not in config.TREE_MODEL_NAMES and best_name != "logreg":
        raise SystemExit(f"Model tốt nhất '{best_name}' không có trainer tương ứng")

    try:
        indexer_train_df = load_train_weighted()
        train_df = indexer_train_df
        if dataset_variant == "balanced":
            train_df = load_train_balanced()
        validation_windows = split_validation_windows(load_validation())
        val_df = validation_windows.selection
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    # Category vocabulary always comes from the complete weighted training
    # population, even when the selected estimator trains on undersampled data.
    indexer = fit_categorical_indexer(indexer_train_df)
    train_df = apply_categorical_indexer(indexer, train_df)
    val_df = apply_categorical_indexer(indexer, val_df)

    X_train, y_train, w_train = to_pandas_xy(train_df)
    X_val, y_val, _ = to_pandas_xy(val_df)
    X_val = align_feature_columns(X_val, list(X_train.columns))

    model_cls = MODEL_CLASSES[best_name]
    best_model, best_pr_auc, best_params = None, -1.0, None
    for params in PARAM_GRIDS[best_name]:
        model = model_cls(**params)
        if best_name == "logreg":
            model = make_pipeline(StandardScaler(), model)
            model.fit(X_train, y_train, logisticregression__sample_weight=w_train)
        else:
            model.fit(X_train, y_train, sample_weight=w_train)
        proba = model.predict_proba(X_val)[:, 1]
        pr_auc = average_precision_score(y_val, proba)
        if pr_auc > best_pr_auc:
            best_model, best_pr_auc, best_params = model, pr_auc, params

    val_roc_auc = roc_auc_score(y_val, best_model.predict_proba(X_val)[:, 1])
    print(f"[tune] best {best_name} params={best_params}")
    print(f"[tune] validation ROC-AUC={val_roc_auc:.4f}  PR-AUC={best_pr_auc:.4f}")
    validation_metrics = binary_metrics(y_val, best_model.predict_proba(X_val)[:, 1], 0.5)

    if best_name in config.TREE_MODEL_NAMES:
        explainer = shap.TreeExplainer(best_model)
        shap_values = explainer.shap_values(X_val)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        importance = np.abs(shap_values).mean(axis=0)
        importance_name = "mean_abs_shap"
    else:
        coefficients = best_model[-1].coef_[0]
        importance = np.abs(coefficients)
        importance_name = "abs_coefficient"
    top5_idx = np.argsort(importance)[::-1][:5]
    top5_global_features = [
        {"feature": X_val.columns[i], importance_name: float(importance[i])} for i in top5_idx
    ]
    print(f"[tune] top-5 feature (SHAP trung bình |giá trị|): {top5_global_features}")

    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    contract = feature_contract_metadata()
    import pandas as pd
    pd.DataFrame([validation_metrics]).to_csv(config.TRAINING_VALIDATION_METRICS_PATH, index=False)
    joblib.dump(
        {
            "model": best_model,
            "model_name": best_name,
            "model_version": config.TRAINING_MODEL_VERSION,
            "feature_columns": list(X_train.columns),
            "category_mappings": extract_category_mappings(indexer),
            "val_roc_auc": val_roc_auc,
            "val_pr_auc": best_pr_auc,
            "top5_global_features": top5_global_features,
            "processing_version": contract["processing_version"],
            "feature_schema_version": contract["feature_schema_version"],
            "required_features": contract["required_features"],
            "optional_features": contract["optional_features"],
            "defaultable_features": contract["defaultable_features"],
            "validation_window": "selection",
        },
        config.TRAINING_FINAL_MODEL_PATH,
    )
    with open(config.TRAINING_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model_version": config.TRAINING_MODEL_VERSION,
                "training_dataset": dataset_variant,
                "best_model": best_name,
                "artifact_path": str(config.TRAINING_FINAL_MODEL_PATH),
                "comparison_path": str(config.TRAINING_COMPARISON_RESULTS_PATH),
                "validation_roc_auc": val_roc_auc,
                "validation_pr_auc": best_pr_auc,
                "feature_count": len(X_train.columns),
                "processing_version": contract["processing_version"],
                "feature_schema_version": contract["feature_schema_version"],
                "validation_window": "selection",
                "validation_window_counts": validation_windows.counts,
                "selection_boundary": validation_windows.selection_boundary,
                "calibration_boundary": validation_windows.calibration_boundary,
                "promotion_status": "candidate_training",
            },
            f,
            indent=2,
        )
    run_id = log_completed_run(
        "tune_validation",
        metrics={
            "validation_roc_auc": val_roc_auc,
            "validation_pr_auc": best_pr_auc,
        },
        params={"best_model": best_name, "training_dataset": dataset_variant, "best_params": json.dumps(best_params, sort_keys=True)},
        artifacts=[config.TRAINING_METADATA_PATH, config.TRAINING_VALIDATION_METRICS_PATH],
    )
    print(f"[mlflow] tune run_id={run_id}")
    print(f"[tune] saved -> {config.TRAINING_FINAL_MODEL_PATH}")


if __name__ == "__main__":
    main()
