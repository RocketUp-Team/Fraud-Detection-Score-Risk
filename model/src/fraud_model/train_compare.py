"""Ngày 3: so sánh Logistic Regression / LightGBM / XGBoost / CatBoost trên
feature contract thật của An (Quân). Ghi kết quả ra
`artifacts/<version>/model_comparison_<version>.json` để `tune_and_explain.py`
(Ngày 4) đọc lại.

Train trên `train_weighted` (sample_weight = cột `class_weight`), đánh giá
trên `validation`. KHÔNG chạm `holdout` ở bước so sánh model — chỉ đánh giá
holdout một lần sau khi đã chốt model (tune_and_explain.py).

Chạy:
    uv run python -m fraud_model.train_compare
"""
import json
import mlflow

from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from . import config
from .data import DatasetNotFoundError, load_train_weighted, load_validation
from .features import (
    align_feature_columns,
    apply_categorical_indexer,
    fit_categorical_indexer,
    to_pandas_xy,
)
from .tracking import log_dataset_params, training_run


def _fit_and_score(name, model, X_train, y_train, w_train, X_val, y_val):
    if name == "logreg":
        model.fit(X_train, y_train, logisticregression__sample_weight=w_train)
    else:
        model.fit(X_train, y_train, sample_weight=w_train)
    proba = model.predict_proba(X_val)[:, 1]
    return model, {
        "roc_auc": roc_auc_score(y_val, proba),
        "pr_auc": average_precision_score(y_val, proba),
    }


def main() -> dict:
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

    models = {
        "logreg": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "lightgbm": LGBMClassifier(n_estimators=300, verbosity=-1),
        "xgboost": XGBClassifier(n_estimators=300, eval_metric="aucpr"),
        "catboost": CatBoostClassifier(iterations=300, verbose=False),
    }

    with training_run("compare"):
        log_dataset_params(len(X_train), len(X_val))
        results = {}
        for name, model in models.items():
            _, results[name] = _fit_and_score(name, model, X_train, y_train, w_train, X_val, y_val)
            mlflow.log_metrics({f"{name}_validation_roc_auc": results[name]["roc_auc"], f"{name}_validation_pr_auc": results[name]["pr_auc"]})
            print(
                f"[compare] {name:10s} validation ROC-AUC={results[name]['roc_auc']:.4f}  "
                f"PR-AUC={results[name]['pr_auc']:.4f}"
            )

    best_name = max(results, key=lambda n: results[n]["pr_auc"])
    print(f"[compare] best model by validation PR-AUC: {best_name}")

    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.TRAINING_COMPARISON_RESULTS_PATH, "w") as f:
        json.dump(
            {
                "model_version": config.TRAINING_MODEL_VERSION,
                "results": results,
                "best_model": best_name,
            },
            f,
            indent=2,
        )
    print(f"[compare] saved -> {config.TRAINING_COMPARISON_RESULTS_PATH}")

    return {"results": results, "best_model": best_name}


if __name__ == "__main__":
    main()
