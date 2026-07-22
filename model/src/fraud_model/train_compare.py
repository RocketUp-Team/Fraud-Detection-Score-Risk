"""Ngày 3: so sánh Logistic Regression / LightGBM / XGBoost / CatBoost theo
PR-AUC/ROC-AUC (Quân). Ghi kết quả ra `artifacts/model_comparison.json` để
`tune_and_explain.py` (Ngày 4) đọc lại.

Load/merge/split dữ liệu chạy phân tán bằng Spark (`data.py`, `features.py`);
convert sang pandas ngay trước khi train (không thư viện model nào ở đây đọc
Spark DataFrame trực tiếp).

Chạy:
    uv run python -m fraud_model.train_compare
"""
import json

from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from . import config
from .data import DatasetNotFoundError, load_merged, time_based_split
from .features import prepare_baseline_features, to_pandas_xy


def _build_models(scale_pos_weight: float) -> dict:
    return {
        "logreg": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")
        ),
        "lightgbm": LGBMClassifier(n_estimators=300, class_weight="balanced", verbosity=-1),
        "xgboost": XGBClassifier(
            n_estimators=300, eval_metric="aucpr", scale_pos_weight=scale_pos_weight
        ),
        "catboost": CatBoostClassifier(
            iterations=300, auto_class_weights="Balanced", verbose=False
        ),
    }


def main() -> dict:
    try:
        df = load_merged()
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    train_df, val_df = time_based_split(df)

    X_train, y_train = to_pandas_xy(prepare_baseline_features(train_df))
    X_val, y_val = to_pandas_xy(prepare_baseline_features(val_df))
    X_val = X_val.reindex(columns=X_train.columns, fill_value=-999)

    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    results = {}
    for name, model in _build_models(scale_pos_weight).items():
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_val)[:, 1]
        results[name] = {
            "roc_auc": roc_auc_score(y_val, proba),
            "pr_auc": average_precision_score(y_val, proba),
        }
        print(
            f"[compare] {name:10s} ROC-AUC={results[name]['roc_auc']:.4f}  "
            f"PR-AUC={results[name]['pr_auc']:.4f}"
        )

    best_name = max(results, key=lambda n: results[n]["pr_auc"])
    print(f"[compare] best model by PR-AUC: {best_name}")

    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.COMPARISON_RESULTS_PATH, "w") as f:
        json.dump({"results": results, "best_model": best_name}, f, indent=2)
    print(f"[compare] saved -> {config.COMPARISON_RESULTS_PATH}")

    return {"results": results, "best_model": best_name}


if __name__ == "__main__":
    main()
