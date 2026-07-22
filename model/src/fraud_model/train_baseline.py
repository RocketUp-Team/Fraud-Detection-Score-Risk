"""Ngày 1: setup training env + chạy thử baseline pipeline (Quân).

Load/merge/split dữ liệu chạy phân tán bằng Spark (`data.py`, `features.py`);
convert sang pandas ngay trước khi train (Logistic Regression của sklearn
không đọc Spark DataFrame). Có StandardScaler vì các cột V-columns của
IEEE-CIS chênh lệch scale rất lớn — thiếu bước này khiến solver `lbfgs`
không hội tụ và train chậm bất thường trên dữ liệu thật (590k dòng).

Chạy:
    uv run python -m fraud_model.train_baseline
"""
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .data import DatasetNotFoundError, load_merged, time_based_split
from .features import prepare_baseline_features, to_pandas_xy


def main() -> None:
    try:
        df = load_merged()
    except DatasetNotFoundError as e:
        print(e)
        raise SystemExit(1)

    train_df, val_df = time_based_split(df)

    X_train, y_train = to_pandas_xy(prepare_baseline_features(train_df))
    X_val, y_val = to_pandas_xy(prepare_baseline_features(val_df))
    X_val = X_val.reindex(columns=X_train.columns, fill_value=-999)

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
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
