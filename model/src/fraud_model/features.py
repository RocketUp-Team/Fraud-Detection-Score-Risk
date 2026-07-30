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
import json

from . import config


CONTRACT_METADATA_COLS = {
    config.ID_COL,
    config.TARGET_COL,
    config.WEIGHT_COL,
    "split_name",
    "processing_version",
    "feature_schema_version",
    "generated_at",
}


def _canonical_feature_contract() -> dict | None:
    """Read the preprocessing feature contract when it is available."""
    path = config.MODEL_READY_DIR.parent / "artifacts" / "preprocessing" / "feature_order.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
        raise ValueError(f"Invalid feature contract: {path}")
    return payload


def _canonical_feature_columns() -> list[str] | None:
    payload = _canonical_feature_contract()
    return list(payload["feature_columns"]) if payload is not None else None


def feature_contract_metadata() -> dict:
    payload = _canonical_feature_contract()
    if payload is None:
        return {
            "processing_version": None,
            "feature_schema_version": None,
            "feature_columns": [],
            "required_features": [],
            "optional_features": [],
            "defaultable_features": [],
        }
    columns = list(payload["feature_columns"])
    return {
        "processing_version": payload.get("processing_version"),
        "feature_schema_version": payload.get("feature_schema_version"),
        "feature_columns": columns,
        "required_features": list(payload.get("required_features", columns)),
        "optional_features": list(payload.get("optional_features", [])),
        "defaultable_features": list(payload.get("defaultable_features", [])),
    }


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


def encode_categorical_frame(pdf, mappings: dict):
    """Apply a frozen train-fitted mapping to a pandas frame."""
    encoded = pdf.copy()
    for column, mapping in mappings.items():
        if column in encoded.columns:
            encoded[column] = (
                encoded[column]
                .map(mapping)
                .fillna(len(mapping))
                .astype("float64")
            )
    return encoded


def to_pandas_xy(df, weight_col: str = config.WEIGHT_COL):
    """Convert Spark DataFrame sang pandas (X, y, sample_weight) — điểm
    chuyển giao duy nhất giữa xử lý phân tán (Spark) và train model in-memory
    (sklearn/LightGBM/XGBoost/CatBoost). `sample_weight` là None nếu dataset
    không có cột `class_weight` (validation/holdout/train_original)."""
    pdf = df.toPandas()
    y = pdf[config.TARGET_COL] if config.TARGET_COL in pdf.columns else None
    sample_weight = pdf[weight_col] if weight_col in pdf.columns else None

    canonical_columns = _canonical_feature_columns()
    if canonical_columns is not None:
        missing = [c for c in canonical_columns if c not in pdf.columns]
        if missing:
            raise ValueError(
                "Model-ready dataset is missing required feature columns: "
                f"{missing[:20]}" + (" ..." if len(missing) > 20 else "")
            )
        # Select only the canonical feature vector. This excludes all contract
        # metadata (split/version/timestamp) and preserves training order.
        X = pdf[canonical_columns].copy()
    else:
        # Backward-compatible fallback for the synthetic/dev dataset only.
        drop_cols = CONTRACT_METADATA_COLS | {config.TIME_COL, weight_col}
        X = pdf.drop(columns=[c for c in drop_cols if c in pdf.columns])
    return X, y, sample_weight


def to_pandas_xy_with_mappings(
    df,
    mappings: dict,
    weight_col: str = config.WEIGHT_COL,
):
    """Convert a later temporal window with the mapping saved in the model
    artifact, without refitting Spark StringIndexer."""
    pdf = df.orderBy(config.TIME_COL, config.ID_COL).toPandas()
    y = pdf[config.TARGET_COL] if config.TARGET_COL in pdf.columns else None
    sample_weight = pdf[weight_col] if weight_col in pdf.columns else None
    canonical_columns = _canonical_feature_columns()
    if canonical_columns is None:
        raise ValueError("Canonical feature contract is required for model evaluation.")
    missing = [column for column in canonical_columns if column not in pdf.columns]
    if missing:
        raise ValueError(f"Model-ready dataset is missing required columns: {missing}")
    X = encode_categorical_frame(pdf.loc[:, canonical_columns], mappings)
    return X, y, sample_weight


def align_feature_columns(X, reference_columns: list[str]):
    """Align a validation/holdout frame without hiding missing contract fields."""
    missing = [c for c in reference_columns if c not in X.columns]
    if missing:
        raise ValueError(f"Missing required model features during alignment: {missing}")
    unexpected = [c for c in X.columns if c not in reference_columns]
    if unexpected:
        print(f"[features] ignoring non-contract columns: {unexpected[:20]}")
    return X.loc[:, reference_columns]
