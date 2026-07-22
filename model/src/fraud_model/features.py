"""Feature prep tạm thời cho baseline (Ngày 1-2), chạy phân tán bằng Spark.

Chỉ dùng cột số (fillna) + StringIndexer cho cột danh mục, KHÔNG có
aggregation theo card/email/device. Sẽ được thay bằng feature pipeline
chính thức bàn giao từ An (Ngày 3, xem docs/RISK_SCORING_PLAN.md mục 2 và 3).

`sklearn`/LightGBM/XGBoost/CatBoost không đọc trực tiếp Spark DataFrame —
dùng `to_pandas_xy()` để convert sang pandas ngay trước bước train, sau khi
Spark đã làm xong phần xử lý phân tán (fillna, encode).
"""
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer
from pyspark.sql import DataFrame

from . import config

DROP_COLS = {config.ID_COL, config.TIME_COL}
NUMERIC_TYPES = {"double", "integer", "long", "float", "short", "byte"}


def prepare_baseline_features(df: DataFrame) -> DataFrame:
    df = df.drop(*[c for c in DROP_COLS if c in df.columns])

    feature_cols = [c for c in df.columns if c != config.TARGET_COL]
    numeric_cols = [
        f.name for f in df.schema.fields if f.name in feature_cols and f.dataType.typeName() in NUMERIC_TYPES
    ]
    categorical_cols = [c for c in feature_cols if c not in numeric_cols]

    if numeric_cols:
        df = df.fillna(-999, subset=numeric_cols)

    if categorical_cols:
        indexers = [
            StringIndexer(inputCol=c, outputCol=f"{c}__idx", handleInvalid="keep")
            for c in categorical_cols
        ]
        df = Pipeline(stages=indexers).fit(df).transform(df)
        for c in categorical_cols:
            df = df.drop(c).withColumnRenamed(f"{c}__idx", c)

    return df


def to_pandas_xy(df: DataFrame):
    """Convert Spark DataFrame đã feature-engineered sang pandas (X, y) —
    điểm chuyển giao duy nhất giữa xử lý phân tán (Spark) và train model
    in-memory (sklearn/LightGBM/XGBoost/CatBoost)."""
    pdf = df.toPandas()
    y = pdf[config.TARGET_COL] if config.TARGET_COL in pdf.columns else None
    X = pdf.drop(columns=[config.TARGET_COL]) if config.TARGET_COL in pdf.columns else pdf
    return X, y
