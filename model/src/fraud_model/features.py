"""Feature prep tạm thời cho baseline (Ngày 1-2).

Chỉ dùng cột số (fillna) + encode thô cột danh mục, KHÔNG có aggregation
theo card/email/device. Sẽ được thay bằng feature pipeline chính thức bàn
giao từ An (Ngày 3, xem docs/RISK_SCORING_PLAN.md mục 2 và 3).
"""
import pandas as pd

from . import config

NON_FEATURE_COLS = {config.ID_COL, config.TARGET_COL, config.TIME_COL}


def prepare_baseline_features(df: pd.DataFrame) -> pd.DataFrame:
    X = df.drop(columns=[c for c in NON_FEATURE_COLS if c in df.columns]).copy()

    numeric_cols = X.select_dtypes(include="number").columns
    categorical_cols = X.select_dtypes(exclude="number").columns

    X[numeric_cols] = X[numeric_cols].fillna(-999)
    for col in categorical_cols:
        X[col] = X[col].astype("category").cat.codes

    return X
