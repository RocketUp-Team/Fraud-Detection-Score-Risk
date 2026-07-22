"""Ngày 1: setup training env + chạy thử baseline pipeline (Quân).

Chạy:
    uv run python -m fraud_model.train_baseline
"""
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from . import config
from .data import DatasetNotFoundError, load_merged, time_based_split
from .features import prepare_baseline_features


def main() -> None:
    try:
        df = load_merged()
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    train_df, val_df = time_based_split(df)

    X_train = prepare_baseline_features(train_df)
    y_train = train_df[config.TARGET_COL]

    X_val = prepare_baseline_features(val_df)
    X_val = X_val.reindex(columns=X_train.columns, fill_value=-999)
    y_val = val_df[config.TARGET_COL]

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    val_proba = model.predict_proba(X_val)[:, 1]
    roc_auc = roc_auc_score(y_val, val_proba)
    pr_auc = average_precision_score(y_val, val_proba)

    print(
        f"[baseline] ROC-AUC={roc_auc:.4f}  PR-AUC={pr_auc:.4f}  "
        f"n_train={len(X_train)}  n_val={len(X_val)}"
    )

    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "feature_columns": list(X_train.columns)},
        config.BASELINE_MODEL_PATH,
    )
    print(f"[baseline] saved -> {config.BASELINE_MODEL_PATH}")


if __name__ == "__main__":
    main()
