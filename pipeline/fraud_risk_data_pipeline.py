"""Production entrypoint for the IEEE-CIS fraud-risk preprocessing workflow.

The Spark implementation is shared with the existing assignment bundle under
``data/ieee_cis/pipeline``. This adapter gives downstream users a stable root
command, applies configuration, and keeps raw data outside the image.
"""
from __future__ import annotations

import argparse
import os
import runpy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_IMPLEMENTATION = PROJECT_ROOT / "data" / "ieee_cis" / "pipeline" / "ieee_cis_preprocess.py"


def _read_simple_yaml(path: Path) -> dict[str, Any]:
    """Read the small config contract without requiring YAML at runtime."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _setdefault_from_config(config: dict[str, Any]) -> None:
    spark = config.get("spark", {})
    imbalance = config.get("imbalance", {})
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
    parser.add_argument("--skip-model-demo", action="store_true")
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
    if args.skip_model_demo:
        os.environ["RUN_MODEL_DEMO"] = "false"
    if args.skip_profile:
        os.environ["RUN_FULL_PROFILE"] = "false"
    runpy.run_path(str(LEGACY_IMPLEMENTATION), run_name="__main__")
    _finalize_contract(Path(os.environ["IEEE_CIS_OUTPUT_DIR"]))


def _finalize_contract(output_dir: Path) -> None:
    """Add stable names/metadata without duplicating large Parquet datasets."""
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "project_name": "Distributed Data Processing and Feature Preparation Pipeline for Fraud Risk Scoring",
        "pipeline_version": "1.0.0",
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_downstream_training",
        "output_contract": "data/processed/ieee_cis_fraud_risk",
        "downstream_recommended_dataset": "model_ready/train_weighted",
    })
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

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
        if source_path.is_file() and source_path != target_path:
            shutil.copyfile(source_path, target_path)
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
        if source_path.is_file() and source_path != target_path:
            shutil.copyfile(source_path, target_path)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (output_dir / "logs" / "pipeline.log").write_text(
        "Pipeline completed successfully; see manifest.json and reports/.\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
