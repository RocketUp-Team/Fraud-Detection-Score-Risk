"""Ngày 1-2: baseline Logistic Regression trên feature contract thật của An
(Quân).

Train trên `train_weighted` (dùng cột `class_weight` làm sample_weight thay
vì class_weight="balanced" tự đoán), đánh giá trên `validation`. KHÔNG chạm
`holdout` ở bước này — xem data/ieee_cis/HANDOVER_TO_QUAN.md mục leakage
precautions.

Chạy:
    uv run python -m fraud_model.train_baseline
"""
import joblib
import mlflow
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .data import DatasetNotFoundError, load_train_weighted, load_validation
from .features import (
    align_feature_columns,
    apply_categorical_indexer,
    extract_category_mappings,
    fit_categorical_indexer,
    to_pandas_xy,
)
from .tracking import log_dataset_params, training_run


def main() -> None:
    try:
        train_df = load_train_weighted()
        val_df = load_validation()
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    indexer = fit_categorical_indexer(train_df)
    train_df = apply_categorical_indexer(indexer, train_df)
    val_df = apply_categorical_indexer(indexer, val_df)

    X_train, y_train, w_train = to_pandas_xy(train_df)
    X_val, y_val, _ = to_pandas_xy(val_df)
    X_val = align_feature_columns(X_val, list(X_train.columns))

    with training_run("baseline"):
        log_dataset_params(len(X_train), len(X_val))
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        model.fit(X_train, y_train, logisticregression__sample_weight=w_train)
        val_proba = model.predict_proba(X_val)[:, 1]
        roc_auc = roc_auc_score(y_val, val_proba)
        pr_auc = average_precision_score(y_val, val_proba)
        mlflow.log_metrics({"validation_roc_auc": roc_auc, "validation_pr_auc": pr_auc})

    print(
        f"[baseline] validation ROC-AUC={roc_auc:.4f}  PR-AUC={pr_auc:.4f}  "
        f"n_train={len(X_train)}  n_val={len(X_val)}"
    )

    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "model_name": "baseline_logreg",
            "model_version": config.TRAINING_MODEL_VERSION,
            "feature_columns": list(X_train.columns),
            "category_mappings": extract_category_mappings(indexer),
            "validation_roc_auc": roc_auc,
            "validation_pr_auc": pr_auc,
        },
        config.TRAINING_BASELINE_MODEL_PATH,
    )
    print(f"[baseline] saved -> {config.TRAINING_BASELINE_MODEL_PATH}")


if __name__ == "__main__":
    main()
