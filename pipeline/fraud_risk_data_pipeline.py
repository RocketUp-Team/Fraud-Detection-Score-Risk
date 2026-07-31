"""Production entrypoint for the IEEE-CIS fraud-risk preprocessing workflow.

The Spark implementation is shared with the existing assignment bundle under
``data/ieee_cis/pipeline``. This adapter gives downstream users a stable root
command, applies configuration, and keeps raw data outside the image.
"""
from __future__ import annotations

import argparse
import os
import runpy
from pathlib import Path
from typing import Any

from .contract_utils import (
    FEATURE_SCHEMA_VERSION,
    PIPELINE_VERSION,
    PROCESSING_VERSION,
    atomic_write_json,
    atomic_write_text,
    read_yaml_config,
    safe_copy_if_exists,
    utc_now_iso,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_IMPLEMENTATION = PROJECT_ROOT / "data" / "ieee_cis" / "pipeline" / "ieee_cis_preprocess.py"


def _read_simple_yaml(path: Path) -> dict[str, Any]:
    """Read the small config contract without requiring YAML at runtime."""
    return read_yaml_config(path)


def _setdefault_from_config(config: dict[str, Any]) -> None:
    spark = config.get("spark", {})
    imbalance = config.get("imbalance", {})
    split = config.get("split", {})
    outliers = config.get("outliers", {})
    quantiles = outliers.get("quantiles", [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    values = {
        "IEEE_CIS_DATA_DIR": str((PROJECT_ROOT / config.get("input_dir", "data/data/ieee-fraud-detection")).resolve()),
        "IEEE_CIS_OUTPUT_DIR": str((PROJECT_ROOT / config.get("output_dir", "data/processed/ieee_cis_fraud_risk")).resolve()),
        "SPARK_MASTER": str(spark.get("master", "local[4]")),
        "SPARK_DRIVER_MEMORY": str(spark.get("driver_memory", "8g")),
        "SPARK_DRIVER_MAX_RESULT_SIZE": str(spark.get("driver_max_result_size", "1g")),
        "SPARK_SHUFFLE_PARTITIONS": str(spark.get("shuffle_partitions", 64)),
        "SPARK_DEFAULT_PARALLELISM": str(spark.get("default_parallelism", 8)),
        "IMBALANCE_RATIO": str(imbalance.get("undersample_legitimate_to_fraud", 3.0)),
        "PIPELINE_SEED": str(imbalance.get("seed", 42)),
        "TRAIN_RATIO": str(split.get("train_ratio", 0.70)),
        "VALIDATION_RATIO": str(split.get("validation_ratio", 0.15)),
        "HOLDOUT_RATIO": str(split.get("holdout_ratio", 0.15)),
        "SPLIT_RELATIVE_ERROR": str(split.get("relative_error", 0.001)),
        "OUTLIER_QUANTILES": ",".join(str(value) for value in quantiles),
        "OUTLIER_RELATIVE_ERROR": str(outliers.get("relative_error", 0.01)),
        "OUTLIER_TRANSFORM_RELATIVE_ERROR": str(outliers.get("transform_relative_error", 0.001)),
        "PROJECT_ROOT": str(PROJECT_ROOT),
    }
    for key, value in values.items():
        os.environ.setdefault(key, value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the IEEE-CIS Spark fraud-risk data pipeline.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "pipeline_config.yaml")
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--master")
    model_demo = parser.add_mutually_exclusive_group()
    model_demo.add_argument("--run-model-demo", action="store_true")
    model_demo.add_argument("--skip-model-demo", action="store_true")
    parser.add_argument("--skip-profile", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not LEGACY_IMPLEMENTATION.is_file():
        raise FileNotFoundError(f"Shared Spark implementation not found: {LEGACY_IMPLEMENTATION}")
    _setdefault_from_config(_read_simple_yaml(args.config.resolve()))
    if args.raw_dir:
        os.environ["IEEE_CIS_DATA_DIR"] = str(args.raw_dir.resolve())
    if args.output_dir:
        os.environ["IEEE_CIS_OUTPUT_DIR"] = str(args.output_dir.resolve())
    if args.master:
        os.environ["SPARK_MASTER"] = args.master
    if args.run_model_demo:
        os.environ["RUN_MODEL_DEMO"] = "true"
    elif args.skip_model_demo:
        os.environ["RUN_MODEL_DEMO"] = "false"
    if args.skip_profile:
        os.environ["RUN_FULL_PROFILE"] = "false"
    runpy.run_path(str(LEGACY_IMPLEMENTATION), run_name="__main__")
    _finalize_contract(Path(os.environ["IEEE_CIS_OUTPUT_DIR"]))


def _finalize_contract(output_dir: Path) -> None:
    """Add stable names/metadata without duplicating large Parquet datasets."""
    from .processed_contract import build_manifest
    from .verify_processed_data import verify

    # Rebuild from the materialized Parquet outputs every time.  The legacy
    # Spark workflow writes an intermediate manifest before export; its schema
    # hash can describe the in-memory DataFrame rather than the final Parquet
    # schema.  Verification must compare against the persisted handoff, so
    # the final manifest cannot reuse that intermediate value.
    manifest = build_manifest(output_dir)

    verification = verify(output_dir, write_report=True)
    manifest.update({
        "project_name": "Distributed Data Processing and Feature Preparation Pipeline for Fraud Risk Scoring",
        "pipeline_version": PIPELINE_VERSION,
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "processing_timestamp": utc_now_iso(),
        "generated_at": manifest.get("generated_at", manifest.get("generated_at_utc", utc_now_iso())),
        "status": verification["status"],
        "output_contract": "data/processed/ieee_cis_fraud_risk",
        "downstream_recommended_dataset": "model_ready/train_weighted",
        "verifier_result": verification,
    })
    atomic_write_json(manifest, manifest_path)

    reports = output_dir / "reports"
    aliases = {
        "dataset_inventory.csv": "source_inventory.csv",
        "data_quality_summary.csv": "key_audit.csv",
        "class_distribution.csv": "class_distribution.csv",
        "model_metrics.csv": "decision_tree_metrics.csv",
    }
    for target, source in aliases.items():
        source_path = reports / source
        target_path = reports / target
        if source_path != target_path:
            safe_copy_if_exists(source_path, target_path)
    demo_aliases = {
        "real_fraud_cases.csv": "real_fraud_cases_csv",
        "real_legitimate_cases.csv": "real_legitimate_cases_csv",
        "true_positive_cases.csv": "true_positive_cases_csv",
        "true_negative_cases.csv": "true_negative_cases_csv",
        "false_positive_cases.csv": "false_positive_cases_csv",
        "false_negative_cases.csv": "false_negative_cases_csv",
    }
    demo_dir = output_dir / "demo"
    for target, source in demo_aliases.items():
        source_path = demo_dir / source
        target_path = demo_dir / target
        if source_path != target_path:
            safe_copy_if_exists(source_path, target_path)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        "Pipeline completed successfully; see manifest.json and reports/.\n",
        output_dir / "logs" / "pipeline.log",
    )


if __name__ == "__main__":
    main()
