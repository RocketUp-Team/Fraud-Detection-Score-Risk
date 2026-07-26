"""Feature prep dùng feature contract thật từ An (parquet `model_ready`,
xem `data/ieee_cis/HANDOVER_TO_QUAN.md` và `DATA_DICTIONARY.md`).

Numeric imputation (median) và missing-category (`__MISSING__`) đã được An xử
lý trong pipeline Spark, chỉ train trên chronological training rows. Ở đây
chỉ còn việc encode 7 cột categorical (`config.CATEGORICAL_COLS`) thành số.

StringIndexer PHẢI fit trên `train_weighted`/`train_balanced` rồi áp dụng lại
(không refit) cho validation/holdout — xem mục "Leakage precautions" trong
HANDOVER_TO_QUAN.md. `extract_category_mappings()` xuất mapping đó ra dict
Python thuần để `score.py` encode 1 giao dịch lúc serving mà không cần khởi
động Spark.

PySpark chỉ được import bên trong từng hàm cần Spark (lazy), không ở
top-level: backend của Trung import `score.py` → `features.py` khi serving, và
đường serving (`encode_categoricals_pandas`) không cần Spark. Import
top-level sẽ buộc backend cài cả PySpark (~300MB) chỉ để chấm 1 giao dịch.
"""
from . import config


def fit_categorical_indexer(train_df):
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import StringIndexer

    cols = [c for c in config.CATEGORICAL_COLS if c in train_df.columns]
    indexers = [
        StringIndexer(inputCol=c, outputCol=f"{c}__idx", handleInvalid="keep") for c in cols
    ]
    return Pipeline(stages=indexers).fit(train_df)


def apply_categorical_indexer(indexer_model, df):
    df = indexer_model.transform(df)
    for stage in indexer_model.stages:
        col = stage.getInputCol()
        idx_col = stage.getOutputCol()
        if idx_col in df.columns:
            df = df.drop(col).withColumnRenamed(idx_col, col)
    return df


def extract_category_mappings(indexer_model) -> dict:
    """category value -> integer code, cho từng cột categorical đã fit."""
    return {
        stage.getInputCol(): {label: idx for idx, label in enumerate(stage.labels)}
        for stage in indexer_model.stages
    }


def encode_categoricals_pandas(row: dict, mappings: dict) -> dict:
    """Encode 1 giao dịch (dict tên_cột -> giá trị thô) bằng mapping đã fit
    trên train — dùng lúc serving (score.py), không cần Spark. Giá trị chưa
    từng thấy lúc train được gán code cuối cùng, khớp `handleInvalid="keep"`
    của StringIndexer."""
    encoded = dict(row)
    for col, mapping in mappings.items():
        if col in encoded:
            encoded[col] = mapping.get(encoded[col], len(mapping))
    return encoded


def to_pandas_xy(df, weight_col: str = config.WEIGHT_COL):
    """Convert Spark DataFrame sang pandas (X, y, sample_weight) — điểm
    chuyển giao duy nhất giữa xử lý phân tán (Spark) và train model in-memory
    (sklearn/LightGBM/XGBoost/CatBoost). `sample_weight` là None nếu dataset
    không có cột `class_weight` (validation/holdout/train_original)."""
    pdf = df.toPandas()
    y = pdf[config.TARGET_COL] if config.TARGET_COL in pdf.columns else None
    sample_weight = pdf[weight_col] if weight_col in pdf.columns else None

    drop_cols = {config.ID_COL, config.TIME_COL, config.TARGET_COL, weight_col}
    X = pdf.drop(columns=[c for c in drop_cols if c in pdf.columns])
    return X, y, sample_weight
