#!/usr/bin/env python3
"""IEEE-CIS distributed preprocessing pipeline.
Generated together with the matching Jupyter notebook.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import platform
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import Iterable

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from IPython.display import Markdown, display
except ImportError:
    Markdown = None
    display = print

try:
    from pyspark import StorageLevel
    from pyspark.ml import Pipeline
    from pyspark.ml.classification import DecisionTreeClassifier
    from pyspark.ml.evaluation import BinaryClassificationEvaluator
    from pyspark.ml.feature import Imputer, StringIndexer, VectorAssembler
    from pyspark.ml.functions import vector_to_array
    from pyspark.ml.pipeline import PipelineModel
    from pyspark.sql import DataFrame, SparkSession, Window
    from pyspark.sql import functions as F
    from pyspark.sql import types as T
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "PySpark is not installed in the active environment. Install the requirements or run the supplied Docker image."
    ) from exc

from pipeline.contract_utils import (
    FEATURE_SCHEMA_VERSION,
    PIPELINE_VERSION,
    PROCESSING_VERSION,
    atomic_write_json,
    atomic_write_text,
    schema_hash,
    sha256_file,
    utc_now_iso,
)
from pipeline.temporal_features import (
    add_point_in_time_history,
    calculate_temporal_boundaries,
    split_by_boundaries,
)

SEED = int(os.getenv("PIPELINE_SEED", "42"))
np.random.seed(SEED)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ieee_cis_pipeline")

WINDOWS_PROJECT_ROOT = Path(r"D:\MSE\16. Big Data\Fraud-Detection-Score-Risk")
WINDOWS_RAW_DATA_DIR = Path(r"D:\MSE\16. Big Data\Fraud-Detection-Score-Risk\data\data\ieee-fraud-detection")
REQUIRED_FILES = [
    "train_transaction.csv",
    "train_identity.csv",
    "test_transaction.csv",
    "test_identity.csv",
]
OPTIONAL_FILES = ["sample_submission.csv"]
RAW_SCHEMA_ARTIFACTS = {
    "train_transaction": "raw_train_transaction_schema.json",
    "train_identity": "raw_train_identity_schema.json",
    "test_transaction": "raw_test_transaction_schema.json",
    "test_identity": "raw_test_identity_schema.json",
}


def _existing_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.exists() else None


def resolve_project_root() -> Path:
    env_root = _existing_path(os.getenv("PROJECT_ROOT"))
    if env_root:
        return env_root
    if os.name == "nt" and WINDOWS_PROJECT_ROOT.exists():
        return WINDOWS_PROJECT_ROOT.resolve()
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".git").exists() or (candidate / "docker-compose.yml").exists() or (candidate / "docker-compose.preprocessing.yml").exists():
            return candidate
    return cwd


def contains_required_files(directory: Path) -> bool:
    return directory.is_dir() and all((directory / name).is_file() for name in REQUIRED_FILES)


def candidate_raw_data_dirs(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    env_raw = os.getenv("IEEE_CIS_DATA_DIR")
    if env_raw:
        candidates.append(Path(env_raw).expanduser())
    candidates.extend([
        project_root / "data" / "data" / "ieee-fraud-detection",
        project_root / "data" / "ieee-fraud-detection",
        project_root / "data" / "raw" / "ieee-fraud-detection",
        project_root / "data" / "raw",
        Path("/app/data/raw"),
    ])
    if os.name == "nt":
        candidates.append(WINDOWS_RAW_DATA_DIR)
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate_str not in seen:
            deduped.append(candidate)
            seen.add(candidate_str)
    return deduped


def resolve_raw_data_dir(project_root: Path) -> Path:
    candidates = candidate_raw_data_dirs(project_root)
    for candidate in candidates:
        candidate = candidate.resolve()
        if contains_required_files(candidate):
            return candidate
    preferred = candidates[0].resolve() if candidates else (project_root / "data" / "data" / "ieee-fraud-detection").resolve()
    return preferred


def resolve_output_dir(project_root: Path) -> Path:
    env_output = os.getenv("IEEE_CIS_OUTPUT_DIR")
    output = Path(env_output).expanduser() if env_output else project_root / "data" / "processed" / "ieee_cis_spark"
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    return output


PROJECT_ROOT = resolve_project_root()
RAW_DATA_DIR = resolve_raw_data_dir(PROJECT_ROOT)
OUTPUT_DIR = resolve_output_dir(PROJECT_ROOT)
REPORTS_DIR = OUTPUT_DIR / "reports"
EDA_REPORTS_DIR = REPORTS_DIR / "eda"
FIGURES_DIR = REPORTS_DIR / "figures"
FEATURE_STORE_DIR = OUTPUT_DIR / "feature_store"
MODEL_READY_DIR = OUTPUT_DIR / "model_ready"
CURATED_DIR = OUTPUT_DIR / "curated"
SPLITS_DIR = OUTPUT_DIR / "splits"
ARTIFACTS_DIR = OUTPUT_DIR / "artifacts"
PREPROCESSING_ARTIFACTS_DIR = ARTIFACTS_DIR / "preprocessing"
SCHEMA_ARTIFACTS_DIR = ARTIFACTS_DIR / "schema"
MODEL_DIR = ARTIFACTS_DIR / "demo_model"
DEMO_DIR = OUTPUT_DIR / "demo"
QUARANTINE_DIR = OUTPUT_DIR / "quarantine"
SPARK_LOCAL_DIR = OUTPUT_DIR / "spark-local"
for directory in [
    REPORTS_DIR,
    EDA_REPORTS_DIR,
    FIGURES_DIR,
    FEATURE_STORE_DIR,
    CURATED_DIR,
    SPLITS_DIR,
    MODEL_READY_DIR,
    ARTIFACTS_DIR,
    PREPROCESSING_ARTIFACTS_DIR,
    SCHEMA_ARTIFACTS_DIR,
    MODEL_DIR,
    DEMO_DIR,
    QUARANTINE_DIR,
    SPARK_LOCAL_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

RUN_FULL_PROFILE = os.getenv("RUN_FULL_PROFILE", "true").lower() in {"1", "true", "yes"}
RUN_MODEL_DEMO = os.getenv("RUN_MODEL_DEMO", "true").lower() in {"1", "true", "yes"}
WRITE_WIDE_FEATURE_STORE = os.getenv("WRITE_WIDE_FEATURE_STORE", "true").lower() in {"1", "true", "yes"}
IMBALANCE_RATIO = float(os.getenv("IMBALANCE_RATIO", "4.0"))
PROFILE_BATCH_SIZE = int(os.getenv("PROFILE_BATCH_SIZE", "40"))
TRAIN_RATIO = float(os.getenv("TRAIN_RATIO", "0.70"))
VALIDATION_RATIO = float(os.getenv("VALIDATION_RATIO", "0.15"))
HOLDOUT_RATIO = float(os.getenv("HOLDOUT_RATIO", "0.15"))
SPLIT_RELATIVE_ERROR = float(os.getenv("SPLIT_RELATIVE_ERROR", "0.001"))
OUTLIER_QUANTILES = [
    float(value)
    for value in os.getenv(
        "OUTLIER_QUANTILES",
        "0.01,0.05,0.25,0.50,0.75,0.95,0.99",
    ).split(",")
    if value.strip()
]
OUTLIER_RELATIVE_ERROR = float(os.getenv("OUTLIER_RELATIVE_ERROR", "0.01"))
OUTLIER_TRANSFORM_RELATIVE_ERROR = float(
    os.getenv("OUTLIER_TRANSFORM_RELATIVE_ERROR", "0.001")
)
if not np.isclose(TRAIN_RATIO + VALIDATION_RATIO + HOLDOUT_RATIO, 1.0):
    raise ValueError(
        "TRAIN_RATIO + VALIDATION_RATIO + HOLDOUT_RATIO must equal 1.0; "
        f"received {TRAIN_RATIO}, {VALIDATION_RATIO}, {HOLDOUT_RATIO}"
    )
if not 0.0 < TRAIN_RATIO < TRAIN_RATIO + VALIDATION_RATIO < 1.0:
    raise ValueError("Chronological split ratios must create three non-empty windows.")
if any(not 0.0 <= quantile <= 1.0 for quantile in OUTLIER_QUANTILES):
    raise ValueError(f"OUTLIER_QUANTILES must be in [0, 1]: {OUTLIER_QUANTILES}")
PARQUET_EXPORT_ENABLED = (
    os.name != "nt"
    or os.getenv("ENABLE_WINDOWS_PARQUET", "false").lower() in {"1", "true", "yes"}
)

print(json.dumps({
    "project_root": str(PROJECT_ROOT),
    "raw_data_dir": str(RAW_DATA_DIR),
    "output_dir": str(OUTPUT_DIR),
    "run_full_profile": RUN_FULL_PROFILE,
    "run_model_demo": RUN_MODEL_DEMO,
    "write_wide_feature_store": WRITE_WIDE_FEATURE_STORE,
    "imbalance_ratio_legit_to_fraud": IMBALANCE_RATIO,
    "split_ratios": {
        "train": TRAIN_RATIO,
        "validation": VALIDATION_RATIO,
        "holdout": HOLDOUT_RATIO,
    },
    "outlier_quantiles": OUTLIER_QUANTILES,
    "parquet_export_enabled": PARQUET_EXPORT_ENABLED,
    "seed": SEED,
}, indent=2))

def create_spark_session() -> SparkSession:
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    master = os.getenv("SPARK_MASTER", "local[*]")
    shuffle_partitions = os.getenv("SPARK_SHUFFLE_PARTITIONS", str(max(16, (os.cpu_count() or 4) * 2)))
    builder = (
        SparkSession.builder
        .appName("IEEE-CIS-Fraud-Preprocessing")
        .master(master)
        .config("spark.pyspark.python", sys.executable)
        .config("spark.pyspark.driver.python", sys.executable)
        .config("spark.sql.shuffle.partitions", shuffle_partitions)
        .config("spark.default.parallelism", os.getenv("SPARK_DEFAULT_PARALLELISM", str(max(8, os.cpu_count() or 4))))
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.execution.arrow.pyspark.enabled", "false")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.local.dir", str(SPARK_LOCAL_DIR))
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "8g"))
        .config("spark.driver.maxResultSize", os.getenv("SPARK_DRIVER_MAX_RESULT_SIZE", "1g"))
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
    return spark


spark = create_spark_session()
print("Spark version:", spark.version)
print("Spark master:", spark.sparkContext.master)
print("Default parallelism:", spark.sparkContext.defaultParallelism)
print("Shuffle partitions:", spark.conf.get("spark.sql.shuffle.partitions"))
print("Spark UI:", spark.sparkContext.uiWebUrl or "not available")


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def spark_path(path: Path) -> str:
    path = path.resolve()
    if os.name == "nt":
        # Hadoop on native Windows interprets encoded file URIs incorrectly.
        return path.as_posix()
    return str(path)


def read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def validate_source_files(raw_dir: Path) -> dict[str, Path]:
    missing = [name for name in REQUIRED_FILES if not (raw_dir / name).is_file()]
    if missing:
        checked = "\n".join(f"  - {candidate.resolve()}" for candidate in candidate_raw_data_dirs(PROJECT_ROOT))
        expected = "\n".join(f"  - {raw_dir / name}" for name in REQUIRED_FILES)
        raise FileNotFoundError(
            f"Missing IEEE-CIS files: {missing}\nExpected files:\n{expected}\n"
            f"Checked candidate directories:\n{checked}\n"
            "For Docker, run from the project root so ./data/data/ieee-fraud-detection is mounted to /app/data/raw."
        )
    result = {Path(name).stem: raw_dir / name for name in REQUIRED_FILES}
    for name in OPTIONAL_FILES:
        if (raw_dir / name).is_file():
            result[Path(name).stem] = raw_dir / name
    return result


def write_json(payload: dict, path: Path) -> None:
    atomic_write_json(payload, path)


def schema_to_records(schema: T.StructType) -> list[dict[str, str]]:
    return [{"name": field.name, "type": field.dataType.simpleString(), "nullable": field.nullable} for field in schema.fields]


def write_schema_artifact(name: str, schema: T.StructType) -> None:
    records = schema_to_records(schema)
    write_json(
        {
            "schema_name": name,
            "schema_version": FEATURE_SCHEMA_VERSION,
            "generated_at": utc_now_iso(),
            "columns": records,
            "schema_hash": schema_hash(records),
        },
        SCHEMA_ARTIFACTS_DIR / RAW_SCHEMA_ARTIFACTS[name],
    )


def write_single_csv(df: DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # Reports are deliberately small; avoid Hadoop permission operations.
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        df.toPandas().to_csv(tmp_path, index=False)
        tmp_path.replace(path)
        return
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(spark_path(path))


def normalize_identity_columns(columns: list[str]) -> list[str]:
    """Normalize Kaggle test identity headers (id-01) to train names (id_01)."""
    return [re.sub(r"^id-(\d+)$", r"id_\1", column) for column in columns]


def write_parquet(df: DataFrame, path: Path, partition_cols: list[str] | None = None) -> None:
    if not PARQUET_EXPORT_ENABLED:
        logger.warning(
            "Skipping Parquet export on native Windows: %s. "
            "Run the supplied Docker Linux pipeline for full Parquet output.",
            path,
        )
        return
    writer = df.write.mode("overwrite")
    if partition_cols:
        writer.partitionBy(*partition_cols).parquet(spark_path(path))
    else:
        writer.parquet(spark_path(path))

def build_transaction_schema(columns: list[str]) -> T.StructType:
    categorical = {
        "ProductCD", "card1", "card2", "card3", "card4", "card5", "card6", "addr1", "addr2",
        "P_emaildomain", "R_emaildomain", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
    }
    fields: list[T.StructField] = []
    for name in columns:
        if name == "TransactionID":
            dtype = T.LongType()
        elif name == "isFraud":
            dtype = T.IntegerType()
        elif name == "TransactionDT":
            dtype = T.LongType()
        elif name == "TransactionAmt" or name in {"dist1", "dist2"} or re.fullmatch(r"[CDV]\d+", name):
            dtype = T.DoubleType()
        elif name in categorical:
            dtype = T.StringType()
        else:
            dtype = T.StringType()
        fields.append(T.StructField(name, dtype, True))
    return T.StructType(fields)


def build_identity_schema(columns: list[str]) -> T.StructType:
    categorical = {
        "id_12", "id_15", "id_16", "id_23", "id_27", "id_28", "id_29", "id_30", "id_31",
        "id_33", "id_34", "id_35", "id_36", "id_37", "id_38", "DeviceType", "DeviceInfo",
    }
    fields: list[T.StructField] = []
    for name in columns:
        if name == "TransactionID":
            dtype = T.LongType()
        elif name in categorical:
            dtype = T.StringType()
        elif name.startswith("id_"):
            dtype = T.DoubleType()
        else:
            dtype = T.StringType()
        fields.append(T.StructField(name, dtype, True))
    return T.StructType(fields)


def read_with_schema(path: Path, schema: T.StructType) -> DataFrame:
    return (
        spark.read.format("csv")
        .option("header", True)
        .option("mode", "PERMISSIVE")
        .option("nullValue", "")
        .option("nanValue", "NaN")
        .option("ignoreLeadingWhiteSpace", True)
        .option("ignoreTrailingWhiteSpace", True)
        .schema(schema)
        .load(spark_path(path))
    )


def audit_key(df: DataFrame, dataset_name: str) -> dict[str, object]:
    row = df.agg(
        F.count("*").alias("rows"),
        F.count("TransactionID").alias("non_null_keys"),
        F.countDistinct("TransactionID").alias("distinct_keys"),
    ).first()
    rows = int(row["rows"])
    non_null = int(row["non_null_keys"])
    distinct_keys = int(row["distinct_keys"])
    return {
        "dataset": dataset_name,
        "rows": rows,
        "null_transaction_ids": rows - non_null,
        "duplicate_transaction_ids": rows - distinct_keys,
        "status": "pass" if rows == non_null == distinct_keys else "fail",
    }


def left_join_with_identity(transaction_df: DataFrame, identity_df: DataFrame, dataset_name: str) -> tuple[DataFrame, dict[str, object]]:
    marker = identity_df.select("TransactionID").distinct().withColumn("__has_identity", F.lit(1))
    joined = (
        transaction_df
        .join(identity_df, on="TransactionID", how="left")
        .join(marker, on="TransactionID", how="left")
        .withColumn("has_identity", F.coalesce(F.col("__has_identity"), F.lit(0)).cast("int"))
        .drop("__has_identity")
    )
    before = transaction_df.count()
    after = joined.count()
    matched = joined.filter(F.col("has_identity") == 1).count()
    audit = {
        "dataset": dataset_name,
        "transaction_rows_before": before,
        "identity_rows": identity_df.count(),
        "joined_rows_after": after,
        "matched_identity_rows": matched,
        "unmatched_transaction_rows": after - matched,
        "row_difference": after - before,
        "status": "pass" if after == before else "fail",
    }
    return joined, audit


source_paths = validate_source_files(RAW_DATA_DIR)
inventory_pdf = pd.DataFrame([
    {
        "filename": path.name,
        "path": str(path),
        "size_bytes": int(path.stat().st_size),
        "size_mb": round(path.stat().st_size / 1024**2, 2),
        "modified_time": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "checksum_sha256": sha256_file(path),
        "schema_version": FEATURE_SCHEMA_VERSION,
    }
    for path in source_paths.values()
])
print(inventory_pdf.to_string(index=False))
print(f"Total source size: {inventory_pdf['size_mb'].sum():,.2f} MB")
assert inventory_pdf.loc[inventory_pdf["filename"].isin(REQUIRED_FILES), "size_mb"].sum() >= 500, "The required IEEE-CIS files must total at least 500 MB."
inventory_pdf.to_csv(REPORTS_DIR / "source_inventory.csv", index=False)
inventory_pdf.to_csv(REPORTS_DIR / "dataset_inventory.csv", index=False)

train_tx_schema = build_transaction_schema(read_csv_header(source_paths["train_transaction"]))
test_tx_schema = build_transaction_schema(read_csv_header(source_paths["test_transaction"]))
train_id_schema = build_identity_schema(normalize_identity_columns(read_csv_header(source_paths["train_identity"])))
test_id_schema = build_identity_schema(normalize_identity_columns(read_csv_header(source_paths["test_identity"])))
write_schema_artifact("train_transaction", train_tx_schema)
write_schema_artifact("test_transaction", test_tx_schema)
write_schema_artifact("train_identity", train_id_schema)
write_schema_artifact("test_identity", test_id_schema)

train_transaction = read_with_schema(source_paths["train_transaction"], train_tx_schema)
test_transaction = read_with_schema(source_paths["test_transaction"], test_tx_schema)
train_identity = read_with_schema(source_paths["train_identity"], train_id_schema)
test_identity = read_with_schema(source_paths["test_identity"], test_id_schema)

for dataset_name, df in [
    ("train_transaction", train_transaction),
    ("test_transaction", test_transaction),
    ("train_identity", train_identity),
    ("test_identity", test_identity),
]:
    row_count = df.count()
    column_count = len(df.columns)
    inventory_pdf.loc[inventory_pdf["filename"] == f"{dataset_name}.csv", "row_count"] = row_count
    inventory_pdf.loc[inventory_pdf["filename"] == f"{dataset_name}.csv", "column_count"] = column_count

key_audit_rows = [
    audit_key(train_transaction, "train_transaction"),
    audit_key(test_transaction, "test_transaction"),
    audit_key(train_identity, "train_identity"),
    audit_key(test_identity, "test_identity"),
]
key_audit = spark.createDataFrame(pd.DataFrame(key_audit_rows))
key_audit.show(truncate=False)
assert key_audit.filter(F.col("status") == "fail").count() == 0, "TransactionID validation failed."

train_merged, train_join_audit = left_join_with_identity(train_transaction, train_identity, "train")
test_merged, test_join_audit = left_join_with_identity(test_transaction, test_identity, "test")
join_audit = spark.createDataFrame(pd.DataFrame([train_join_audit, test_join_audit]))
join_audit.show(truncate=False)
assert join_audit.filter(F.col("status") == "fail").count() == 0, "Transaction-identity join changed the transaction grain."
write_single_csv(join_audit, REPORTS_DIR / "join_audit.csv")

# The joined IEEE-CIS tables are very wide. Keep them on disk instead of
# filling the JVM heap with columnar cache blocks.
train_merged = train_merged.persist(StorageLevel.DISK_ONLY)
test_merged = test_merged.persist(StorageLevel.DISK_ONLY)
train_rows = train_merged.count()
test_rows = test_merged.count()
print("Merged train rows/columns:", train_rows, len(train_merged.columns))
print("Merged test rows/columns:", test_rows, len(test_merged.columns))
inventory_pdf.to_csv(REPORTS_DIR / "dataset_inventory.csv", index=False)

def profile_dataframe(df: DataFrame, dataset_name: str, full_profile: bool = True) -> DataFrame:
    row_count = df.count()
    selected = df.columns if full_profile else [
        c for c in [
            "TransactionID", "isFraud", "TransactionDT", "TransactionAmt", "ProductCD", "card1", "card4", "card6",
            "P_emaildomain", "R_emaildomain", "DeviceType", "DeviceInfo", "dist1", "dist2", "C1", "C2", "D1", "D2",
        ] if c in df.columns
    ]
    rows: list[dict[str, object]] = []
    dtype_map = dict(df.dtypes)
    for batch in chunked(selected, PROFILE_BATCH_SIZE):
        expressions = []
        for column in batch:
            expressions.extend([
                F.sum(F.when(F.col(column).isNull(), 1).otherwise(0)).alias(f"{column}__null"),
                F.approx_count_distinct(F.col(column)).alias(f"{column}__distinct"),
            ])
        metrics = df.agg(*expressions).first().asDict()
        for column in batch:
            null_count = int(metrics[f"{column}__null"] or 0)
            distinct = int(metrics[f"{column}__distinct"] or 0)
            rows.append({
                "dataset": dataset_name,
                "column_name": column,
                "spark_type": dtype_map.get(column, "unknown"),
                "row_count": row_count,
                "null_count": null_count,
                "null_pct": float(null_count / row_count * 100.0) if row_count else 0.0,
                "approx_distinct_count": distinct,
                "cardinality_ratio": float(distinct / row_count) if row_count else 0.0,
                "is_sparse_over_80pct": bool(row_count and null_count / row_count > 0.8),
                "is_high_cardinality_over_10pct": bool(row_count and distinct / row_count > 0.1),
            })
    return spark.createDataFrame(pd.DataFrame(rows))


train_profile = profile_dataframe(train_merged, "train", RUN_FULL_PROFILE)
test_profile = profile_dataframe(test_merged, "test", RUN_FULL_PROFILE)
data_profile = train_profile.unionByName(test_profile)
data_profile.orderBy(F.desc("null_pct")).show(30, truncate=False)

class_distribution = (
    train_merged.groupBy("isFraud")
    .agg(F.count("*").alias("transaction_count"))
    .withColumn("percentage", F.round(F.col("transaction_count") / F.sum("transaction_count").over(Window.partitionBy()) * 100, 6))
    .orderBy("isFraud")
)
class_distribution.show()

fraud_count = train_merged.filter(F.col("isFraud") == 1).count()
legit_count = train_merged.filter(F.col("isFraud") == 0).count()
imbalance_summary = {
    "fraud_count": fraud_count,
    "legitimate_count": legit_count,
    "fraud_rate": fraud_count / train_rows,
    "legitimate_to_fraud_ratio": legit_count / max(fraud_count, 1),
}
print(json.dumps(imbalance_summary, indent=2))

data_quality_rows = [
    {
        "stage": "raw_train_transaction",
        "metric": "rows",
        "value": train_transaction.count(),
    },
    {
        "stage": "raw_train_identity",
        "metric": "rows",
        "value": train_identity.count(),
    },
    {
        "stage": "raw_test_transaction",
        "metric": "rows",
        "value": test_transaction.count(),
    },
    {
        "stage": "raw_test_identity",
        "metric": "rows",
        "value": test_identity.count(),
    },
    {
        "stage": "joined_train",
        "metric": "identity_coverage_ratio",
        "value": float(train_join_audit["matched_identity_rows"] / max(train_join_audit["joined_rows_after"], 1)),
    },
    {
        "stage": "joined_test",
        "metric": "identity_coverage_ratio",
        "value": float(test_join_audit["matched_identity_rows"] / max(test_join_audit["joined_rows_after"], 1)),
    },
]
duplicate_summary_pdf = pd.DataFrame([
    {
        "dataset": row["dataset"],
        "duplicate_transaction_ids": row["duplicate_transaction_ids"],
        "null_transaction_ids": row["null_transaction_ids"],
    }
    for row in key_audit_rows
])
invalid_records_pdf = pd.DataFrame([
    {
        "dataset": "train_transaction",
        "metric": "null_transaction_amount",
        "value": train_transaction.filter(F.col("TransactionAmt").isNull()).count(),
    },
    {
        "dataset": "test_transaction",
        "metric": "null_transaction_amount",
        "value": test_transaction.filter(F.col("TransactionAmt").isNull()).count(),
    },
    {
        "dataset": "train_transaction",
        "metric": "empty_productcd",
        "value": train_transaction.filter(F.trim(F.coalesce(F.col("ProductCD"), F.lit(""))) == "").count(),
    },
    {
        "dataset": "test_transaction",
        "metric": "empty_productcd",
        "value": test_transaction.filter(F.trim(F.coalesce(F.col("ProductCD"), F.lit(""))) == "").count(),
    },
])

write_parquet(data_profile, REPORTS_DIR / "data_profile_parquet")
write_single_csv(data_profile.orderBy(F.desc("null_pct")), REPORTS_DIR / "data_profile_csv")
write_single_csv(data_profile.orderBy(F.desc("null_pct")), REPORTS_DIR / "missingness_profile_csv")
write_single_csv(key_audit, REPORTS_DIR / "key_audit_csv")
write_single_csv(key_audit, REPORTS_DIR / "key_audit.csv")
write_single_csv(join_audit, REPORTS_DIR / "join_audit_csv")
write_single_csv(join_audit, REPORTS_DIR / "join_audit.csv")
write_single_csv(class_distribution, REPORTS_DIR / "class_distribution_csv")
write_single_csv(class_distribution, REPORTS_DIR / "class_distribution.csv")
write_json(imbalance_summary, REPORTS_DIR / "imbalance_summary.json")
pd.DataFrame(data_quality_rows).to_csv(REPORTS_DIR / "data_quality_summary.csv", index=False)
duplicate_summary_pdf.to_csv(REPORTS_DIR / "duplicate_summary.csv", index=False)
invalid_records_pdf.to_csv(REPORTS_DIR / "invalid_records_summary.csv", index=False)

CATEGORICAL_TO_NORMALIZE = [
    "ProductCD", "card1", "card2", "card3", "card4", "card5", "card6", "addr1", "addr2",
    "P_emaildomain", "R_emaildomain", "DeviceType", "DeviceInfo", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
    "id_12", "id_15", "id_16", "id_23", "id_27", "id_28", "id_29", "id_30", "id_31", "id_33", "id_34", "id_35", "id_36", "id_37", "id_38",
]


def normalize_categoricals(df: DataFrame) -> DataFrame:
    result = df
    for column in CATEGORICAL_TO_NORMALIZE:
        if column in result.columns:
            result = result.withColumn(
                column,
                F.when(F.trim(F.col(column).cast("string")) == "", F.lit(None))
                 .otherwise(F.lower(F.trim(F.col(column).cast("string")))),
            )
    return result


def add_base_features(df: DataFrame) -> DataFrame:
    identity_columns = [c for c in df.columns if c.startswith("id_")]
    selected_missing_columns = [
        c for c in [
            "TransactionAmt", "ProductCD", "card1", "card2", "card3", "card4", "card5", "card6",
            "addr1", "addr2", "P_emaildomain", "R_emaildomain", "DeviceType", "DeviceInfo",
            "dist1", "dist2", "C1", "C2", "C3", "D1", "D2", "D3",
        ] if c in df.columns
    ]
    selected_missing_expr = reduce(
        lambda left, right: left + right,
        [F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0)) for c in selected_missing_columns],
        F.lit(0),
    )
    identity_missing_expr = reduce(
        lambda left, right: left + right,
        [F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0)) for c in identity_columns],
        F.lit(0),
    ) if identity_columns else F.lit(0)

    result = (
        df
        .withColumn("transaction_day", F.floor(F.col("TransactionDT") / F.lit(86400)).cast("long"))
        .withColumn("transaction_week", F.floor(F.col("TransactionDT") / F.lit(604800)).cast("long"))
        .withColumn("transaction_hour", F.floor((F.col("TransactionDT") % F.lit(86400)) / F.lit(3600)).cast("int"))
        .withColumn("transaction_day_of_week_proxy", (F.col("transaction_day") % F.lit(7)).cast("int"))
        .withColumn("transaction_age_days", (F.col("TransactionDT") / F.lit(86400)).cast("double"))
        .withColumn("is_night_transaction", F.when((F.col("transaction_hour") <= 5) | (F.col("transaction_hour") >= 22), 1).otherwise(0).cast("int"))
        .withColumn("transaction_period", F.concat(F.lit("week_"), F.col("transaction_week").cast("string")))
        .withColumn("log_transaction_amount", F.log1p(F.col("TransactionAmt").cast("double")))
        .withColumn("amount_decimal", (F.col("TransactionAmt") - F.floor(F.col("TransactionAmt"))).cast("double"))
        .withColumn("amount_band", F.when(F.col("TransactionAmt") <= 10, "00_0_10")
                    .when(F.col("TransactionAmt") <= 25, "01_10_25")
                    .when(F.col("TransactionAmt") <= 50, "02_25_50")
                    .when(F.col("TransactionAmt") <= 100, "03_50_100")
                    .when(F.col("TransactionAmt") <= 250, "04_100_250")
                    .when(F.col("TransactionAmt") <= 500, "05_250_500")
                    .when(F.col("TransactionAmt") <= 1000, "06_500_1000")
                    .otherwise("07_1000_plus"))
        .withColumn("selected_missing_count", selected_missing_expr.cast("int"))
        .withColumn("selected_missing_ratio", (F.col("selected_missing_count") / F.lit(max(len(selected_missing_columns), 1))).cast("double"))
        .withColumn("identity_missing_count", identity_missing_expr.cast("int"))
        .withColumn("identity_missing_ratio", (F.col("identity_missing_count") / F.lit(max(len(identity_columns), 1))).cast("double"))
        .withColumn("has_device_info", F.when(F.col("DeviceInfo").isNotNull(), 1).otherwise(0).cast("int"))
        .withColumn("has_p_email", F.when(F.col("P_emaildomain").isNotNull(), 1).otherwise(0).cast("int"))
        .withColumn("has_r_email", F.when(F.col("R_emaildomain").isNotNull(), 1).otherwise(0).cast("int"))
        .withColumn("has_distance", F.when(F.col("dist1").isNotNull() | F.col("dist2").isNotNull(), 1).otherwise(0).cast("int"))
        .withColumn("has_address", F.when(F.col("addr1").isNotNull() | F.col("addr2").isNotNull(), 1).otherwise(0).cast("int"))
        .withColumn("same_email_domain", F.when(F.coalesce(F.col("P_emaildomain"), F.lit("__NA__")) == F.coalesce(F.col("R_emaildomain"), F.lit("__NA__")), 1).otherwise(0).cast("int"))
        .withColumn("device_family", F.when(F.lower(F.col("DeviceInfo")).rlike("iphone|ipad|ios"), "apple")
                    .when(F.lower(F.col("DeviceInfo")).rlike("android|samsung|sm-"), "android")
                    .when(F.lower(F.col("DeviceInfo")).rlike("windows"), "windows")
                    .when(F.lower(F.col("DeviceInfo")).rlike("mac"), "mac")
                    .otherwise("other"))
        .withColumn("card_entity_key", F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit("__NA__")) for c in ["card1", "card2", "card3", "card5"] if c in df.columns]))
        .withColumn("email_entity_key", F.coalesce(F.col("P_emaildomain"), F.lit("__NA__")))
        .withColumn("device_entity_key", F.concat_ws("|", F.coalesce(F.col("DeviceType"), F.lit("__NA__")), F.coalesce(F.col("DeviceInfo"), F.lit("__NA__"))))
        .withColumn("address_entity_key", F.concat_ws("|", F.coalesce(F.col("addr1").cast("string"), F.lit("__NA__")), F.coalesce(F.col("addr2").cast("string"), F.lit("__NA__"))))
    )
    return result


clean_train = add_base_features(normalize_categoricals(train_merged))
clean_test = add_base_features(normalize_categoricals(test_merged))

# Establish chronological boundaries before fitting any data-derived
# preprocessing statistic.  The names q70/q85 are retained as internal legacy
# aliases, while the manifest records the configured ratios explicitly.
temporal_boundaries = calculate_temporal_boundaries(
    clean_train,
    train_ratio=TRAIN_RATIO,
    validation_ratio=VALIDATION_RATIO,
    relative_error=SPLIT_RELATIVE_ERROR,
)
q70, q85 = temporal_boundaries.train_max, temporal_boundaries.validation_max
train_fit_base = clean_train.filter(F.col("TransactionDT") <= F.lit(q70))

# Amount caps/flags are fitted only on the chronological training window.
# Validation, holdout and Kaggle test receive the frozen thresholds below.
amount_quantiles = train_fit_base.approxQuantile(
    "TransactionAmt",
    [0.95, 0.99, 0.25, 0.75],
    OUTLIER_TRANSFORM_RELATIVE_ERROR,
)
amount_p95, amount_p99, amount_p25, amount_p75 = amount_quantiles
amount_iqr = amount_p75 - amount_p25
amount_upper_cap = amount_p75 + 1.5 * amount_iqr
high_amount_threshold = amount_p99
clean_train = (
    clean_train
    .withColumn("transaction_amount_capped", F.least(F.col("TransactionAmt"), F.lit(amount_upper_cap)).cast("double"))
    .withColumn("high_amount_flag", F.when(F.col("TransactionAmt") >= high_amount_threshold, 1).otherwise(0).cast("int"))
    .withColumn("amount_outlier_flag", F.when(F.col("TransactionAmt") >= amount_upper_cap, 1).otherwise(0).cast("int"))
    .withColumn("distance_outlier_flag", F.when((F.col("dist1") >= 1000) | (F.col("dist2") >= 1000), 1).otherwise(0).cast("int"))
)
clean_test = (
    clean_test
    .withColumn("transaction_amount_capped", F.least(F.col("TransactionAmt"), F.lit(amount_upper_cap)).cast("double"))
    .withColumn("high_amount_flag", F.when(F.col("TransactionAmt") >= high_amount_threshold, 1).otherwise(0).cast("int"))
    .withColumn("amount_outlier_flag", F.when(F.col("TransactionAmt") >= amount_upper_cap, 1).otherwise(0).cast("int"))
    .withColumn("distance_outlier_flag", F.when((F.col("dist1") >= 1000) | (F.col("dist2") >= 1000), 1).otherwise(0).cast("int"))
)
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "fit_scope": "chronological_training_only",
        "train_ratio": TRAIN_RATIO,
        "validation_ratio": VALIDATION_RATIO,
        "holdout_ratio": HOLDOUT_RATIO,
        "transaction_amount": {
            "p95": amount_p95,
            "p99": amount_p99,
            "p25": amount_p25,
            "p75": amount_p75,
            "iqr": amount_iqr,
            "upper_cap": amount_upper_cap,
        },
        "distance_outlier_threshold": 1000,
    },
    PREPROCESSING_ARTIFACTS_DIR / "outlier_thresholds.json",
)
print("99th percentile transaction amount:", high_amount_threshold)

clean_train.createOrReplaceTempView("train_clean")

eda_queries = {
    "fraud_overview": """
        SELECT COUNT(*) AS transactions,
               SUM(CASE WHEN isFraud = 1 THEN 1 ELSE 0 END) AS fraud_transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct,
               ROUND(AVG(TransactionAmt), 4) AS avg_amount
        FROM train_clean
    """,
    "fraud_by_product": """
        SELECT COALESCE(ProductCD, '__missing__') AS ProductCD,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct,
               ROUND(AVG(TransactionAmt), 4) AS avg_amount
        FROM train_clean
        GROUP BY COALESCE(ProductCD, '__missing__')
        ORDER BY fraud_rate_pct DESC
    """,
    "fraud_by_card4": """
        SELECT COALESCE(card4, '__missing__') AS card4,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY COALESCE(card4, '__missing__')
        HAVING COUNT(*) >= 100
        ORDER BY fraud_rate_pct DESC, transactions DESC
    """,
    "fraud_by_card6": """
        SELECT COALESCE(card6, '__missing__') AS card6,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY COALESCE(card6, '__missing__')
        HAVING COUNT(*) >= 100
        ORDER BY fraud_rate_pct DESC, transactions DESC
    """,
    "fraud_by_amount_band": """
        SELECT amount_band, COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY amount_band
        ORDER BY amount_band
    """,
    "fraud_by_device": """
        SELECT COALESCE(DeviceType, '__missing__') AS DeviceType,
               COALESCE(device_family, '__missing__') AS device_family,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY COALESCE(DeviceType, '__missing__'), COALESCE(device_family, '__missing__')
        HAVING COUNT(*) >= 100
        ORDER BY fraud_rate_pct DESC
    """,
    "fraud_by_email": """
        SELECT COALESCE(P_emaildomain, '__missing__') AS P_emaildomain,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY COALESCE(P_emaildomain, '__missing__')
        HAVING COUNT(*) >= 100
        ORDER BY fraud_rate_pct DESC, transactions DESC
        LIMIT 30
    """,
    "fraud_by_r_email": """
        SELECT COALESCE(R_emaildomain, '__missing__') AS R_emaildomain,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY COALESCE(R_emaildomain, '__missing__')
        HAVING COUNT(*) >= 100
        ORDER BY fraud_rate_pct DESC, transactions DESC
        LIMIT 30
    """,
    "fraud_by_hour": """
        SELECT transaction_hour, COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct,
               ROUND(AVG(TransactionAmt), 4) AS avg_amount
        FROM train_clean
        GROUP BY transaction_hour
        ORDER BY transaction_hour
    """,
    "fraud_by_day": """
        SELECT transaction_day, COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY transaction_day
        ORDER BY transaction_day
    """,
    "fraud_by_week": """
        SELECT transaction_week, COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY transaction_week
        ORDER BY transaction_week
    """,
    "fraud_by_has_identity": """
        SELECT has_identity, COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY has_identity
        ORDER BY has_identity
    """,
    "fraud_by_missing_ratio": """
        SELECT ROUND(selected_missing_ratio, 1) AS missing_ratio_bucket,
               COUNT(*) AS transactions,
               ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY ROUND(selected_missing_ratio, 1)
        ORDER BY missing_ratio_bucket
    """,
    "top_card_entities": """
        SELECT card_entity_key, COUNT(*) AS transactions, ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY card_entity_key
        HAVING COUNT(*) >= 20
        ORDER BY transactions DESC
        LIMIT 30
    """,
    "top_email_entities": """
        SELECT email_entity_key, COUNT(*) AS transactions, ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY email_entity_key
        HAVING COUNT(*) >= 20
        ORDER BY transactions DESC
        LIMIT 30
    """,
    "top_device_entities": """
        SELECT device_entity_key, COUNT(*) AS transactions, ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY device_entity_key
        HAVING COUNT(*) >= 20
        ORDER BY transactions DESC
        LIMIT 30
    """,
    "top_fraud_rate_entities": """
        SELECT card_entity_key, COUNT(*) AS transactions, ROUND(AVG(isFraud) * 100, 6) AS fraud_rate_pct
        FROM train_clean
        GROUP BY card_entity_key
        HAVING COUNT(*) >= 100
        ORDER BY fraud_rate_pct DESC, transactions DESC
        LIMIT 30
    """,
}

eda_results: dict[str, DataFrame] = {}
for name, query in eda_queries.items():
    result = spark.sql(query)
    eda_results[name] = result
    print(f"\n--- {name} ---")
    result.show(30, truncate=False)
    write_single_csv(result, REPORTS_DIR / f"{name}_csv")
    write_single_csv(result, EDA_REPORTS_DIR / f"{name}.csv")

# Only aggregated Spark results are converted to Pandas for figures.
class_pd = class_distribution.toPandas()
ax = class_pd.plot.bar(x="isFraud", y="transaction_count", legend=False, title="IEEE-CIS Class Distribution")
ax.set_xlabel("isFraud")
ax.set_ylabel("Transactions")
plt.tight_layout()
plt.savefig(FIGURES_DIR / "class_distribution.png", dpi=160)
plt.close()

product_pd = eda_results["fraud_by_product"].toPandas()
ax = product_pd.plot.bar(x="ProductCD", y="fraud_rate_pct", legend=False, title="Fraud Rate by ProductCD")
ax.set_ylabel("Fraud rate (%)")
plt.tight_layout()
plt.savefig(FIGURES_DIR / "fraud_rate_by_product.png", dpi=160)
plt.close()

week_pd = eda_results["fraud_by_week"].toPandas()
ax = week_pd.plot.line(x="transaction_week", y="fraud_rate_pct", legend=False, title="Fraud Rate over Transaction Weeks")
ax.set_ylabel("Fraud rate (%)")
plt.tight_layout()
plt.savefig(FIGURES_DIR / "fraud_rate_by_week.png", dpi=160)
plt.close()

amount_class_pd = (
    clean_train.groupBy("isFraud")
    .agg(
        F.avg("TransactionAmt").alias("avg_transaction_amount"),
        F.expr("percentile_approx(TransactionAmt, 0.5)").alias("median_transaction_amount"),
    )
    .toPandas()
)
amount_class_pd.to_csv(EDA_REPORTS_DIR / "transaction_amount_by_class.csv", index=False)

numeric_corr_pdf = (
    clean_train.select("TransactionAmt", "log_transaction_amount", "selected_missing_ratio", "identity_missing_ratio", "dist1", "dist2")
    .sample(withReplacement=False, fraction=0.02, seed=SEED)
    .toPandas()
    .corr(numeric_only=True)
)
numeric_corr_pdf.to_csv(EDA_REPORTS_DIR / "numeric_feature_correlation.csv")

train_split_base, validation_split_base, holdout_split_base = split_by_boundaries(
    clean_train,
    temporal_boundaries,
)

split_counts = {
    "train": train_split_base.count(),
    "validation": validation_split_base.count(),
    "holdout": holdout_split_base.count(),
    "q70_transaction_dt": q70,
    "q85_transaction_dt": q85,
    "train_ratio": TRAIN_RATIO,
    "validation_ratio": VALIDATION_RATIO,
    "holdout_ratio": HOLDOUT_RATIO,
}
print(json.dumps(split_counts, indent=2))
assert sum(split_counts[k] for k in ["train", "validation", "holdout"]) == train_rows

split_report_rows = []
for split_name, split_df in [
    ("train", train_split_base),
    ("validation", validation_split_base),
    ("holdout", holdout_split_base),
]:
    split_row = split_df.agg(
        F.count("*").alias("rows"),
        F.min("TransactionDT").alias("min_transaction_dt"),
        F.max("TransactionDT").alias("max_transaction_dt"),
        F.sum(F.when(F.col("isFraud") == 1, 1).otherwise(0)).alias("fraud"),
    ).first()
    rows = int(split_row["rows"])
    fraud = int(split_row["fraud"] or 0)
    split_report_rows.append({
        "dataset": split_name,
        "rows": rows,
        "legitimate": rows - fraud,
        "fraud": fraud,
        "fraud_rate": fraud / max(rows, 1),
        "min_transaction_dt": int(split_row["min_transaction_dt"]),
        "max_transaction_dt": int(split_row["max_transaction_dt"]),
    })
split_report = spark.createDataFrame(pd.DataFrame(split_report_rows))
write_single_csv(split_report, REPORTS_DIR / "chronological_split_csv")
write_single_csv(split_report, REPORTS_DIR / "split_summary_csv")
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "train_ratio": TRAIN_RATIO,
        "validation_ratio": VALIDATION_RATIO,
        "holdout_ratio": HOLDOUT_RATIO,
        "train_boundary_transaction_dt": q70,
        "validation_boundary_transaction_dt": q85,
        "q70_transaction_dt": q70,
        "q85_transaction_dt": q85,
        "split_counts": split_counts,
    },
    PREPROCESSING_ARTIFACTS_DIR / "split_thresholds.json",
)


def build_training_lookups(train_df: DataFrame) -> dict[str, DataFrame]:
    return {
        "card": train_df.groupBy("card_entity_key").agg(
            F.count("*").alias("card_history_count"),
            F.sum("TransactionAmt").alias("card_history_amount_sum"),
            F.stddev_samp("TransactionAmt").alias("card_history_amount_stddev"),
            F.max("TransactionDT").alias("card_last_transaction_dt"),
        ),
        "email": train_df.groupBy("email_entity_key").agg(
            F.count("*").alias("email_history_count"),
            F.sum("TransactionAmt").alias("email_history_amount_sum"),
            F.avg("TransactionAmt").alias("email_history_avg_amount"),
        ),
        "device": train_df.groupBy("device_entity_key").agg(
            F.count("*").alias("device_history_count"),
            F.sum("TransactionAmt").alias("device_history_amount_sum"),
            F.avg("TransactionAmt").alias("device_history_avg_amount"),
        ),
    }


def add_training_window_history(df: DataFrame) -> DataFrame:
    """Backward-compatible alias for the canonical point-in-time transform."""
    return add_point_in_time_history(df)


def apply_training_lookups(df: DataFrame, lookups: dict[str, DataFrame]) -> DataFrame:
    return (
        df
        .join(F.broadcast(lookups["email"]), on="email_entity_key", how="left")
        .join(lookups["card"], on="card_entity_key", how="left")
        .join(lookups["device"], on="device_entity_key", how="left")
        .withColumn("prior_card_transaction_count", F.coalesce(F.col("card_history_count"), F.lit(0)).cast("long"))
        .withColumn("prior_card_amount_sum", F.coalesce(F.col("card_history_amount_sum"), F.lit(0.0)).cast("double"))
        .withColumn("prior_card_avg_amount", F.when(F.col("prior_card_transaction_count") > 0, F.col("prior_card_amount_sum") / F.col("prior_card_transaction_count")).otherwise(F.lit(0.0)))
        .withColumn("prior_card_amount_stddev", F.coalesce(F.col("card_history_amount_stddev"), F.lit(0.0)).cast("double"))
        .withColumn("time_since_previous_card_transaction", (F.col("TransactionDT") - F.col("card_last_transaction_dt")).cast("double"))
        .withColumn("prior_email_transaction_count", F.coalesce(F.col("email_history_count"), F.lit(0)).cast("long"))
        .withColumn("prior_email_amount_sum", F.coalesce(F.col("email_history_amount_sum"), F.lit(0.0)).cast("double"))
        .withColumn("prior_email_avg_amount", F.coalesce(F.col("email_history_avg_amount"), F.lit(0.0)).cast("double"))
        .withColumn("prior_device_transaction_count", F.coalesce(F.col("device_history_count"), F.lit(0)).cast("long"))
        .withColumn("prior_device_amount_sum", F.coalesce(F.col("device_history_amount_sum"), F.lit(0.0)).cast("double"))
        .withColumn("prior_device_avg_amount", F.coalesce(F.col("device_history_avg_amount"), F.lit(0.0)).cast("double"))
        .drop("card_history_count", "card_history_amount_sum", "card_history_amount_stddev", "card_last_transaction_dt", "email_history_count", "email_history_amount_sum", "email_history_avg_amount", "device_history_count", "device_history_amount_sum", "device_history_avg_amount")
    )


lookups = build_training_lookups(train_split_base)
for lookup_name, lookup_df in lookups.items():
    write_parquet(lookup_df, FEATURE_STORE_DIR / f"{lookup_name}_aggregates")

# Compute event-history features over the chronological transaction stream.
# Window frames end at -1, so each row can use all prior transactions but never
# its own values or future activity.  Splits are filtered only after the
# point-in-time computation; no label participates in these aggregates.
train_timeline_features = add_training_window_history(clean_train)
train_features, validation_features, holdout_features = split_by_boundaries(
    train_timeline_features,
    temporal_boundaries,
)

# Kaggle test transactions occur after the labeled stream.  Build the same
# point-in-time histories from all prior labeled and earlier test events using
# only transaction attributes, then join the derived columns back by ID.
history_base_columns = [
    "TransactionID",
    "TransactionDT",
    "TransactionAmt",
    "card_entity_key",
    "email_entity_key",
    "device_entity_key",
]
history_feature_columns = [
    "prior_card_transaction_count",
    "prior_card_amount_sum",
    "prior_card_avg_amount",
    "prior_card_amount_stddev",
    "time_since_previous_card_transaction",
    "prior_email_transaction_count",
    "prior_email_amount_sum",
    "prior_email_avg_amount",
    "prior_device_transaction_count",
    "prior_device_amount_sum",
    "prior_device_avg_amount",
]
test_history_stream = (
    clean_train.select(*history_base_columns)
    .withColumn("__history_source", F.lit("labeled"))
    .unionByName(
        clean_test.select(*history_base_columns).withColumn(
            "__history_source",
            F.lit("kaggle_test"),
        )
    )
)
test_history = (
    add_training_window_history(test_history_stream)
    .filter(F.col("__history_source") == "kaggle_test")
    .select("TransactionID", *history_feature_columns)
)
test_features = clean_test.join(test_history, on="TransactionID", how="left")

for dataset_name, df in [
    ("train_features", train_features),
    ("validation_features", validation_features),
    ("holdout_features", holdout_features),
    ("test_features", test_features),
]:
    if "prior_card_avg_amount" in df.columns:
        df = df.withColumn(
            "amount_ratio_to_card_mean",
            F.when(F.col("prior_card_avg_amount") > 0, F.col("TransactionAmt") / F.col("prior_card_avg_amount")).otherwise(F.lit(1.0)),
        ).withColumn(
            "amount_deviation_from_card_mean",
            (F.col("TransactionAmt") - F.col("prior_card_avg_amount")).cast("double"),
        )
    if dataset_name == "train_features":
        train_features = df
    elif dataset_name == "validation_features":
        validation_features = df
    elif dataset_name == "holdout_features":
        holdout_features = df
    else:
        test_features = df

if WRITE_WIDE_FEATURE_STORE:
    write_parquet(train_features, FEATURE_STORE_DIR / "train_wide", ["transaction_period"])
    write_parquet(validation_features, FEATURE_STORE_DIR / "validation_wide", ["transaction_period"])
    write_parquet(holdout_features, FEATURE_STORE_DIR / "holdout_wide", ["transaction_period"])
    write_parquet(test_features, FEATURE_STORE_DIR / "kaggle_test_wide", ["transaction_period"])

NUMERIC_CANDIDATES = [
    "TransactionAmt", "log_transaction_amount", "transaction_amount_capped", "amount_decimal", "TransactionDT", "transaction_day", "transaction_week", "transaction_hour",
    "transaction_day_of_week_proxy", "transaction_age_days", "is_night_transaction",
    "selected_missing_count", "selected_missing_ratio", "identity_missing_count", "identity_missing_ratio", "has_identity", "has_device_info", "has_p_email", "has_r_email", "has_distance", "has_address",
    "same_email_domain", "high_amount_flag", "amount_outlier_flag", "distance_outlier_flag", "dist1", "dist2",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13", "C14",
    "D1", "D2", "D3", "D4", "D5", "D10", "D15",
    "prior_card_transaction_count", "prior_card_amount_sum", "prior_card_avg_amount", "prior_card_amount_stddev", "time_since_previous_card_transaction",
    "prior_email_transaction_count", "prior_email_amount_sum", "prior_email_avg_amount",
    "prior_device_transaction_count", "prior_device_amount_sum", "prior_device_avg_amount",
    "amount_ratio_to_card_mean", "amount_deviation_from_card_mean",
]
CATEGORICAL_CANDIDATES = ["ProductCD", "card4", "card6", "DeviceType", "device_family", "M4", "amount_band"]
NUMERIC_COLUMNS = [c for c in NUMERIC_CANDIDATES if c in train_features.columns]
CATEGORICAL_COLUMNS = [c for c in CATEGORICAL_CANDIDATES if c in train_features.columns]


def select_model_columns(df: DataFrame, include_label: bool) -> DataFrame:
    selected = ["TransactionID"]
    if include_label and "isFraud" in df.columns:
        selected.append("isFraud")
    selected += NUMERIC_COLUMNS + CATEGORICAL_COLUMNS
    result = df.select(*selected)
    for column in NUMERIC_COLUMNS:
        result = result.withColumn(column, F.col(column).cast("double"))
    result = result.fillna("__MISSING__", subset=CATEGORICAL_COLUMNS)
    return result


train_model_raw = select_model_columns(train_features, include_label=True)
validation_model_raw = select_model_columns(validation_features, include_label=True)
holdout_model_raw = select_model_columns(holdout_features, include_label=True)
test_model_raw = select_model_columns(test_features, include_label=False)

imputed_names = [f"{c}__imputed" for c in NUMERIC_COLUMNS]
imputer = Imputer(strategy="median", inputCols=NUMERIC_COLUMNS, outputCols=imputed_names)
imputer_model = imputer.fit(train_model_raw)
median_values = imputer_model.surrogateDF.collect()[0].asDict() if NUMERIC_COLUMNS else {}
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "strategy": "median_train_only",
        "values": {str(key): value for key, value in median_values.items()},
    },
    PREPROCESSING_ARTIFACTS_DIR / "numeric_medians.json",
)


def apply_imputer(df: DataFrame) -> DataFrame:
    transformed = imputer_model.transform(df)
    identity_columns = ["TransactionID"] + (["isFraud"] if "isFraud" in transformed.columns else [])
    return transformed.select(
        *identity_columns,
        *[F.col(f"{c}__imputed").alias(c) for c in NUMERIC_COLUMNS],
        *CATEGORICAL_COLUMNS,
    )


train_model_ready = apply_imputer(train_model_raw).persist(StorageLevel.MEMORY_AND_DISK)
validation_model_ready = apply_imputer(validation_model_raw).persist(StorageLevel.DISK_ONLY)
holdout_model_ready = apply_imputer(holdout_model_raw).persist(StorageLevel.DISK_ONLY)
test_model_ready = apply_imputer(test_model_raw).persist(StorageLevel.DISK_ONLY)

train_class_counts = {int(row["isFraud"]): int(row["count"]) for row in train_model_ready.groupBy("isFraud").count().collect()}
train_legit = train_class_counts.get(0, 0)
train_fraud = train_class_counts.get(1, 0)
train_total = train_legit + train_fraud
fraud_weight = train_total / (2.0 * max(train_fraud, 1))
legit_weight = train_total / (2.0 * max(train_legit, 1))
train_weighted = train_model_ready.withColumn(
    "class_weight",
    F.when(F.col("isFraud") == 1, F.lit(fraud_weight)).otherwise(F.lit(legit_weight)).cast("double"),
)

fraud_train = train_model_ready.filter(F.col("isFraud") == 1)
legit_train = train_model_ready.filter(F.col("isFraud") == 0)
desired_legit = min(train_legit, int(train_fraud * IMBALANCE_RATIO))
legit_fraction = min(1.0, desired_legit / max(train_legit, 1))
legit_sample = legit_train.sample(withReplacement=False, fraction=legit_fraction, seed=SEED)
train_balanced = fraud_train.unionByName(legit_sample).repartition(max(8, spark.sparkContext.defaultParallelism)).persist(StorageLevel.DISK_ONLY)

def label_counts(df: DataFrame) -> tuple[int, int]:
    counts = {int(row["isFraud"]): int(row["count"]) for row in df.groupBy("isFraud").count().collect()}
    return counts.get(0, 0), counts.get(1, 0)

balanced_legit, balanced_fraud = label_counts(train_balanced)
validation_legit, validation_fraud = label_counts(validation_model_ready)
holdout_legit, holdout_fraud = label_counts(holdout_model_ready)
balance_report = spark.createDataFrame(pd.DataFrame([
    {"dataset": "train_original", "legitimate": train_legit, "fraud": train_fraud, "legit_to_fraud_ratio": train_legit / max(train_fraud, 1)},
    {"dataset": "train_weighted", "legitimate": train_legit, "fraud": train_fraud, "legit_to_fraud_ratio": train_legit / max(train_fraud, 1)},
    {"dataset": "train_balanced", "legitimate": balanced_legit, "fraud": balanced_fraud, "legit_to_fraud_ratio": balanced_legit / max(balanced_fraud, 1)},
    {"dataset": "validation_untouched", "legitimate": validation_legit, "fraud": validation_fraud, "legit_to_fraud_ratio": validation_legit / max(validation_fraud, 1)},
    {"dataset": "holdout_untouched", "legitimate": holdout_legit, "fraud": holdout_fraud, "legit_to_fraud_ratio": holdout_legit / max(holdout_fraud, 1)},
]))
balance_report.show(truncate=False)

write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "fraud_weight": fraud_weight,
        "legitimate_weight": legit_weight,
        "undersampling_ratio_legitimate_to_fraud": IMBALANCE_RATIO,
        "undersampling_fraction_legitimate": legit_fraction,
        "seed": SEED,
    },
    PREPROCESSING_ARTIFACTS_DIR / "imbalance_config.json",
)

feature_order = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_columns": feature_order,
        "required_features": feature_order,
        "optional_features": [],
        "defaultable_features": CATEGORICAL_COLUMNS,
    },
    PREPROCESSING_ARTIFACTS_DIR / "feature_order.json",
)
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "selected_features": feature_order,
    },
    PREPROCESSING_ARTIFACTS_DIR / "selected_features.json",
)
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "missing_category": "__MISSING__",
        "unseen_category": "__UNKNOWN__",
        "rare_category": "__OTHER__",
        "categorical_columns": CATEGORICAL_COLUMNS,
    },
    PREPROCESSING_ARTIFACTS_DIR / "category_policy.json",
)

def with_contract_columns(df: DataFrame, split_name: str, include_label: bool = True, weighted: bool = False) -> DataFrame:
    result = (
        df
        .withColumn("split_name", F.lit(split_name))
        .withColumn("processing_version", F.lit(PROCESSING_VERSION))
        .withColumn("feature_schema_version", F.lit(FEATURE_SCHEMA_VERSION))
        .withColumn("generated_at", F.lit(utc_now_iso()))
    )
    if not include_label and "isFraud" in result.columns:
        result = result.drop("isFraud")
    if not weighted and "class_weight" in result.columns:
        result = result.drop("class_weight")
    return result


train_original_export = with_contract_columns(train_model_ready, "train_original")
train_weighted_export = with_contract_columns(train_weighted, "train_weighted", weighted=True)
train_balanced_export = with_contract_columns(train_balanced, "train_balanced")
validation_export = with_contract_columns(validation_model_ready, "validation")
holdout_export = with_contract_columns(holdout_model_ready, "holdout")
test_export = with_contract_columns(test_model_ready, "kaggle_test", include_label=False)

write_parquet(train_merged, CURATED_DIR / "train_joined")
write_parquet(test_merged, CURATED_DIR / "test_joined")
write_parquet(clean_train, CURATED_DIR / "train_cleaned")
write_parquet(clean_test, CURATED_DIR / "test_cleaned")
write_parquet(train_split_base, SPLITS_DIR / "train")
write_parquet(validation_split_base, SPLITS_DIR / "validation")
write_parquet(holdout_split_base, SPLITS_DIR / "holdout")

write_parquet(train_original_export, MODEL_READY_DIR / "train_original")
write_parquet(train_weighted_export, MODEL_READY_DIR / "train_weighted")
write_parquet(train_balanced_export, MODEL_READY_DIR / "train_balanced")
write_parquet(validation_export, MODEL_READY_DIR / "validation")
write_parquet(holdout_export, MODEL_READY_DIR / "holdout")
write_parquet(test_export, MODEL_READY_DIR / "kaggle_test")
write_single_csv(balance_report, REPORTS_DIR / "class_balance_report_csv")
write_single_csv(balance_report, REPORTS_DIR / "imbalance_comparison_csv")

def calculate_binary_metrics(predictions: DataFrame, dataset_name: str) -> dict[str, object]:
    counts = {
        (int(row["isFraud"]), int(row["prediction"])): int(row["count"])
        for row in predictions.groupBy("isFraud", "prediction").count().collect()
    }
    tp = counts.get((1, 1), 0)
    tn = counts.get((0, 0), 0)
    fp = counts.get((0, 1), 0)
    fn = counts.get((1, 0), 0)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    pr_auc = BinaryClassificationEvaluator(labelCol="isFraud", rawPredictionCol="rawPrediction", metricName="areaUnderPR").evaluate(predictions)
    roc_auc = BinaryClassificationEvaluator(labelCol="isFraud", rawPredictionCol="rawPrediction", metricName="areaUnderROC").evaluate(predictions)
    return {
        "dataset": dataset_name,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision_fraud": precision,
        "recall_fraud": recall,
        "f1_fraud": f1,
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
    }


model_metrics: list[dict[str, object]] = []
if RUN_MODEL_DEMO:
    indexers = [
        StringIndexer(inputCol=c, outputCol=f"{c}__idx", handleInvalid="keep")
        for c in CATEGORICAL_COLUMNS
    ]
    assembled_inputs = NUMERIC_COLUMNS + [f"{c}__idx" for c in CATEGORICAL_COLUMNS]
    assembler = VectorAssembler(inputCols=assembled_inputs, outputCol="features", handleInvalid="keep")
    def build_tree_pipeline(weight_col: str | None = None) -> Pipeline:
        classifier_kwargs = {
            "labelCol": "isFraud",
            "featuresCol": "features",
            "predictionCol": "prediction",
            "probabilityCol": "probability",
            "rawPredictionCol": "rawPrediction",
            "maxDepth": int(os.getenv("DT_MAX_DEPTH", "8")),
            "maxBins": int(os.getenv("DT_MAX_BINS", "128")),
            "minInstancesPerNode": int(os.getenv("DT_MIN_INSTANCES_PER_NODE", "50")),
            "seed": SEED,
        }
        if weight_col:
            classifier_kwargs["weightCol"] = weight_col
        classifier = DecisionTreeClassifier(**classifier_kwargs)
        return Pipeline(stages=[*indexers, assembler, classifier])

    training_jobs = [
        ("baseline_tree", train_model_ready, None),
        ("weighted_tree", train_weighted, "class_weight"),
        ("undersampled_tree", train_balanced, None),
    ]
    champion_name = None
    champion_validation_pr_auc = -1.0
    champion_holdout_predictions = None
    champion_test_predictions = None
    for model_name, training_df, weight_col in training_jobs:
        ml_pipeline = build_tree_pipeline(weight_col)
        start = time.time()
        fitted_model = ml_pipeline.fit(training_df)
        training_seconds = time.time() - start
        model_path = MODEL_DIR.parent / model_name
        fitted_model.write().overwrite().save(spark_path(model_path))

        validation_predictions = fitted_model.transform(validation_model_ready).withColumn("fraud_probability", vector_to_array("probability")[1])
        holdout_predictions = fitted_model.transform(holdout_model_ready).withColumn("fraud_probability", vector_to_array("probability")[1])
        test_predictions = fitted_model.transform(test_model_ready).withColumn("fraud_probability", vector_to_array("probability")[1])

        validation_metrics = calculate_binary_metrics(validation_predictions, "validation")
        holdout_metrics = calculate_binary_metrics(holdout_predictions, "holdout")
        model_metrics.extend([
            {"model": model_name, **validation_metrics, "training_seconds": training_seconds},
            {"model": model_name, **holdout_metrics, "training_seconds": training_seconds},
        ])
        if validation_metrics["pr_auc"] > champion_validation_pr_auc:
            champion_validation_pr_auc = validation_metrics["pr_auc"]
            champion_name = model_name
            champion_holdout_predictions = holdout_predictions
            champion_test_predictions = test_predictions

    model_metrics_df = spark.createDataFrame(pd.DataFrame(model_metrics))
    model_metrics_df.show(truncate=False)
    write_single_csv(model_metrics_df, REPORTS_DIR / "decision_tree_metrics_csv")
    write_single_csv(model_metrics_df, REPORTS_DIR / "decision_tree_metrics.csv")
    write_json({"metrics": model_metrics, "training_seconds": training_seconds}, REPORTS_DIR / "decision_tree_metrics.json")

    if champion_holdout_predictions is None or champion_test_predictions is None:
        raise RuntimeError("No Decision Tree model completed successfully.")

    case_type = (
        F.when((F.col("isFraud") == 1) & (F.col("prediction") == 1), "true_positive")
        .when((F.col("isFraud") == 0) & (F.col("prediction") == 0), "true_negative")
        .when((F.col("isFraud") == 0) & (F.col("prediction") == 1), "false_positive")
        .otherwise("false_negative")
    )
    case_window = Window.partitionBy("case_type").orderBy(F.desc("fraud_probability"), F.asc("TransactionID"))
    demo_cases = (
        champion_holdout_predictions
        .withColumn("case_type", case_type)
        .withColumn("case_rank", F.row_number().over(case_window))
        .filter(F.col("case_rank") <= 3)
        .select(
            "case_type", "case_rank", "TransactionID", "isFraud", "prediction", "fraud_probability",
            "TransactionAmt", "ProductCD", "card4", "card6", "DeviceType", "device_family", "transaction_hour",
            "prior_card_transaction_count", "prior_email_transaction_count", "prior_device_transaction_count",
        )
        .orderBy("case_type", "case_rank")
    )
    demo_cases.show(20, truncate=False)
    write_parquet(demo_cases, DEMO_DIR / "demo_cases_parquet")
    write_single_csv(demo_cases, DEMO_DIR / "demo_cases_csv")
    write_single_csv(
        demo_cases.filter(F.col("isFraud") == 1),
        DEMO_DIR / "real_fraud_cases_csv",
    )
    write_single_csv(
        demo_cases.filter(F.col("isFraud") == 0),
        DEMO_DIR / "real_legitimate_cases_csv",
    )
    demo_file_names = {
        "true_positive": "true_positive_cases_csv",
        "true_negative": "true_negative_cases_csv",
        "false_positive": "false_positive_cases_csv",
        "false_negative": "false_negative_cases_csv",
    }
    for case_name, file_name in demo_file_names.items():
        write_single_csv(demo_cases.filter(F.col("case_type") == case_name), DEMO_DIR / file_name)

    kaggle_predictions = champion_test_predictions.select("TransactionID", F.col("fraud_probability").alias("isFraud")).orderBy("TransactionID")
    write_single_csv(kaggle_predictions, DEMO_DIR / "kaggle_test_predictions_csv")
else:
    logger.info("RUN_MODEL_DEMO=false; skipped the Decision Tree demonstration.")

feature_catalog_rows = []
for column in NUMERIC_COLUMNS:
    feature_catalog_rows.append({
        "feature_name": column,
        "feature_type": "numeric",
        "missing_value_policy": "median fitted on chronological training split",
        "training_ready": True,
    })
for column in CATEGORICAL_COLUMNS:
    feature_catalog_rows.append({
        "feature_name": column,
        "feature_type": "categorical",
        "missing_value_policy": "__MISSING__ category",
        "training_ready": True,
    })
feature_catalog = spark.createDataFrame(pd.DataFrame(feature_catalog_rows))
write_single_csv(feature_catalog, REPORTS_DIR / "feature_catalog_csv")
write_single_csv(feature_catalog, REPORTS_DIR / "feature_catalog.csv")
write_single_csv(feature_catalog, EDA_REPORTS_DIR / "feature_catalog.csv")

missingness_strategy_pdf = data_profile.toPandas()
missingness_strategy_pdf["empty_string_count"] = 0
missingness_strategy_pdf["missing_group"] = np.where(
    missingness_strategy_pdf["null_pct"] < 20,
    "Low",
    np.where(
        missingness_strategy_pdf["null_pct"] < 70,
        "Medium",
        np.where(missingness_strategy_pdf["null_pct"] < 95, "High", "Extreme"),
    ),
)
missingness_strategy_pdf["recommended_strategy"] = np.where(
    missingness_strategy_pdf["spark_type"].str.contains("string", case=False, na=False),
    "trim + normalize empty + __MISSING__ + __UNKNOWN__ for unseen",
    "median_train_only",
)
missingness_strategy_pdf["final_action"] = np.where(
    missingness_strategy_pdf["spark_type"].str.contains("string", case=False, na=False),
    "categorical_fill_missing",
    "numeric_imputation",
)
missingness_strategy_pdf.to_csv(REPORTS_DIR / "missingness_profile.csv", index=False)
missingness_strategy_pdf.to_csv(REPORTS_DIR / "missingness_strategy.csv", index=False)

# Small audit artifacts are materialized after distributed aggregation. The
# source datasets remain Spark/Parquet; only bounded report rows use Pandas.
outlier_rows = []
for column in [c for c in ["TransactionAmt", "dist1", "dist2", "C1", "D1"] if c in train_features.columns]:
    configured_quantiles = sorted(set(OUTLIER_QUANTILES))
    quantile_values = train_features.approxQuantile(
        column,
        configured_quantiles,
        OUTLIER_RELATIVE_ERROR,
    )
    if len(quantile_values) == len(configured_quantiles):
        row = {
            "column_name": column,
            "min": train_features.agg(F.min(column)).first()[0],
            "max": train_features.agg(F.max(column)).first()[0],
        }
        row.update(
            {
                f"p{int(round(quantile * 100)):02d}": value
                for quantile, value in zip(configured_quantiles, quantile_values)
            }
        )
        outlier_rows.append(row)
if outlier_rows:
    write_single_csv(spark.createDataFrame(pd.DataFrame(outlier_rows)), REPORTS_DIR / "numeric_outlier_profile.csv")

type_rows = [{"dataset": "train_joined", "column_name": field.name, "spark_type": field.dataType.simpleString()} for field in train_merged.schema.fields]
write_single_csv(spark.createDataFrame(pd.DataFrame(type_rows)), REPORTS_DIR / "type_conversion_summary.csv")
write_single_csv(spark.createDataFrame(pd.DataFrame(feature_catalog_rows)), REPORTS_DIR / "feature_selection.csv")
atomic_write_text(
    "# Leakage controls\n\n"
    "- Chronological split occurs before imputation and entity lookup fitting.\n"
    "- Numeric medians and card/email/device aggregates are fitted on training data only.\n"
    "- Validation and holdout are not resampled.\n"
    "- TransactionDT is treated as relative ordering, not calendar time.\n",
    REPORTS_DIR / "leakage_controls.md",
)

model_ready_schema_records = [
    {"name": field.name, "type": field.dataType.simpleString()}
    for field in train_weighted_export.schema
]
write_json(
    {
        "generated_at": utc_now_iso(),
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_ready_columns": model_ready_schema_records,
        "schema_hash": schema_hash(model_ready_schema_records),
        "exceptions": {
            "kaggle_test": ["isFraud"],
            "train_weighted": ["class_weight"],
        },
    },
    SCHEMA_ARTIFACTS_DIR / "model_ready_schema.json",
)
write_json(
    {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "schema_hash": schema_hash(model_ready_schema_records),
    },
    SCHEMA_ARTIFACTS_DIR / "feature_schema_version.json",
)

dataset_exports = {
    "train_original": train_original_export,
    "train_weighted": train_weighted_export,
    "train_balanced": train_balanced_export,
    "validation": validation_export,
    "holdout": holdout_export,
    "kaggle_test": test_export,
}
model_ready_dataset_manifest = {}
for dataset_name, dataset_df in dataset_exports.items():
    schema_records = [{"name": field.name, "type": field.dataType.simpleString()} for field in dataset_df.schema.fields]
    model_ready_dataset_manifest[dataset_name] = {
        "path": str(MODEL_READY_DIR / dataset_name),
        "row_count": int(dataset_df.count()),
        "column_count": len(dataset_df.columns),
        "schema_hash": schema_hash(schema_records),
        "columns": [field["name"] for field in schema_records],
    }

input_paths = {
    row["filename"]: {
        "path": row["path"],
        "size_bytes": row["size_bytes"],
        "size_mb": row["size_mb"],
        "modified_time": row["modified_time"],
        "checksum_sha256": row["checksum_sha256"],
        "row_count": row.get("row_count"),
        "column_count": row.get("column_count"),
        "schema_version": row.get("schema_version"),
    }
    for row in inventory_pdf.to_dict(orient="records")
}

report_paths = {}
for report_path in REPORTS_DIR.rglob("*"):
    if report_path.is_file():
        report_paths[str(report_path.relative_to(OUTPUT_DIR))] = str(report_path)

spark_hadoop_version = "unknown"
try:
    spark_hadoop_version = spark.sparkContext._jvm.org.apache.hadoop.util.VersionInfo.getVersion()
except Exception:
    pass

manifest = {
    "project_name": "Fraud Detection / Fraud Risk Scoring",
    "pipeline": "IEEE-CIS Spark preprocessing and EDA",
    "pipeline_version": PIPELINE_VERSION,
    "processing_version": PROCESSING_VERSION,
    "feature_schema_version": FEATURE_SCHEMA_VERSION,
    "generated_at": utc_now_iso(),
    "platform": platform.platform(),
    "python_version": sys.version,
    "spark_version": spark.version,
    "hadoop_version": spark_hadoop_version,
    "spark_master": spark.sparkContext.master,
    "project_root": str(PROJECT_ROOT),
    "raw_data_dir": str(RAW_DATA_DIR),
    "output_dir": str(OUTPUT_DIR),
    "input_paths": input_paths,
    "source_files": inventory_pdf.to_dict(orient="records"),
    "split_boundaries": {
        "train_ratio": TRAIN_RATIO,
        "validation_ratio": VALIDATION_RATIO,
        "holdout_ratio": HOLDOUT_RATIO,
        "train_boundary_transaction_dt": q70,
        "validation_boundary_transaction_dt": q85,
        "q70_transaction_dt": q70,
        "q85_transaction_dt": q85,
    },
    "split_counts": split_counts,
    "imbalance": imbalance_summary,
    "class_weights": {"legitimate": legit_weight, "fraud": fraud_weight},
    "undersampling_target_legitimate_to_fraud_ratio": IMBALANCE_RATIO,
    "selected_features": feature_order,
    "imputation_artifacts": {
        "numeric_medians": str(PREPROCESSING_ARTIFACTS_DIR / "numeric_medians.json"),
        "category_policy": str(PREPROCESSING_ARTIFACTS_DIR / "category_policy.json"),
        "outlier_thresholds": str(PREPROCESSING_ARTIFACTS_DIR / "outlier_thresholds.json"),
        "split_thresholds": str(PREPROCESSING_ARTIFACTS_DIR / "split_thresholds.json"),
        "imbalance_config": str(PREPROCESSING_ARTIFACTS_DIR / "imbalance_config.json"),
        "feature_order": str(PREPROCESSING_ARTIFACTS_DIR / "feature_order.json"),
        "selected_features": str(PREPROCESSING_ARTIFACTS_DIR / "selected_features.json"),
    },
    "schema_hashes": {
        "raw_train_transaction": schema_hash(schema_to_records(RAW_TRANSACTION_SCHEMA)),
        "raw_train_identity": schema_hash(schema_to_records(RAW_IDENTITY_SCHEMA)),
        "raw_test_transaction": schema_hash(schema_to_records(RAW_TRANSACTION_SCHEMA)),
        "raw_test_identity": schema_hash(schema_to_records(RAW_IDENTITY_SCHEMA)),
        "model_ready": schema_hash(model_ready_schema_records),
    },
    "numeric_features": NUMERIC_COLUMNS,
    "categorical_features": CATEGORICAL_COLUMNS,
    "model_ready_datasets": model_ready_dataset_manifest,
    "report_paths": report_paths,
    "outputs": {
        "train_original": str(MODEL_READY_DIR / "train_original"),
        "train_weighted": str(MODEL_READY_DIR / "train_weighted"),
        "train_balanced": str(MODEL_READY_DIR / "train_balanced"),
        "validation": str(MODEL_READY_DIR / "validation"),
        "holdout": str(MODEL_READY_DIR / "holdout"),
        "kaggle_test": str(MODEL_READY_DIR / "kaggle_test"),
        "reports": str(REPORTS_DIR),
        "demo": str(DEMO_DIR),
        "model": str(MODEL_DIR) if RUN_MODEL_DEMO else None,
    },
    "model_demo_metrics": model_metrics,
    "verifier_result": {"status": "verification_pending"},
    "status": "verification_pending",
}
write_json(manifest, OUTPUT_DIR / "manifest.json")

required_output_paths = [
    OUTPUT_DIR / "manifest.json",
]
if PARQUET_EXPORT_ENABLED:
    required_output_paths.extend([
        MODEL_READY_DIR / "train_original",
        MODEL_READY_DIR / "train_weighted",
        MODEL_READY_DIR / "train_balanced",
        MODEL_READY_DIR / "validation",
        MODEL_READY_DIR / "holdout",
        MODEL_READY_DIR / "kaggle_test",
    ])
missing_outputs = [str(path) for path in required_output_paths if not path.exists()]
assert not missing_outputs, f"Missing required outputs: {missing_outputs}"

print("\nPIPELINE COMPLETED SUCCESSFULLY")
print("Training-ready data:", MODEL_READY_DIR)
print("Manifest:", OUTPUT_DIR / "manifest.json")
print("Reports:", REPORTS_DIR)
print("Demo cases:", DEMO_DIR)
print("Decision Tree model:", MODEL_DIR if RUN_MODEL_DEMO else "skipped")

try:
    spark.stop()
except Exception:
    pass
