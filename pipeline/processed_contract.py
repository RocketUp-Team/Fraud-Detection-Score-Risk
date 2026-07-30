from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

from .contract_utils import (
    FEATURE_SCHEMA_VERSION,
    PIPELINE_VERSION,
    PROCESSING_VERSION,
    atomic_write_json,
    environment_metadata,
    schema_hash,
    utc_now_iso,
)

REQUIRED_DATASETS = [
    "train_original",
    "train_weighted",
    "train_balanced",
    "validation",
    "holdout",
    "kaggle_test",
]

REQUIRED_REPORT_FILES = [
    "dataset_inventory.csv",
    "data_quality_summary.csv",
    "duplicate_summary.csv",
    "invalid_records_summary.csv",
    "join_audit.csv",
    "missingness_profile.csv",
    "missingness_strategy.csv",
    "split_summary.csv",
    "imbalance_comparison.csv",
    "feature_catalog.csv",
]

ALIAS_REPORT_SOURCES = {
    "join_audit.csv": ["join_audit_csv"],
    "split_summary.csv": ["split_summary_csv", "chronological_split_csv"],
    "imbalance_comparison.csv": ["imbalance_comparison_csv", "class_balance_report_csv"],
    "feature_catalog.csv": ["feature_catalog_csv"],
}


def _dataset(path: Path):
    import pyarrow.dataset as ds  # type: ignore

    return ds.dataset(str(path), format="parquet")


def _schema_records(path: Path) -> list[dict[str, str]]:
    return [{"name": field.name, "type": str(field.type)} for field in _dataset(path).schema]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_spark_csv_outputs(root: Path) -> dict[str, str]:
    reports_dir = root / "reports"
    normalized: dict[str, str] = {}
    if not reports_dir.exists():
        return normalized

    for report_name in REQUIRED_REPORT_FILES:
        path = reports_dir / report_name
        backup_dir = path.with_name(path.name + ".sparkdir")
        if path.is_file():
            normalized[report_name] = "already_file"
            continue
        if not path.exists():
            for alias_name in ALIAS_REPORT_SOURCES.get(report_name, []):
                alias_path = reports_dir / alias_name
                alias_backup_dir = alias_path.with_name(alias_path.name + ".sparkdir")
                if alias_path.is_file():
                    shutil.copyfile(alias_path, path)
                    normalized[report_name] = f"copied_from_alias_file:{alias_name}"
                    break
                if alias_path.is_dir():
                    source_dir = alias_path
                    alias_part_files = sorted(source_dir.glob("part-*.csv"))
                    if alias_part_files:
                        shutil.copyfile(alias_part_files[0], path)
                        normalized[report_name] = f"copied_from_alias_dir:{alias_name}"
                        break
                if alias_backup_dir.is_dir():
                    alias_part_files = sorted(alias_backup_dir.glob("part-*.csv"))
                    if alias_part_files:
                        shutil.copyfile(alias_part_files[0], path)
                        normalized[report_name] = f"copied_from_alias_backup:{alias_backup_dir.name}"
                        break
            if path.is_file():
                continue
        source_dir: Path | None = None
        if path.is_dir():
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            path.rename(backup_dir)
            source_dir = backup_dir
        elif backup_dir.is_dir():
            source_dir = backup_dir
        else:
            normalized[report_name] = "missing"
            continue

        backup_part_files = sorted(source_dir.glob("part-*.csv"))
        if not backup_part_files:
            normalized[report_name] = "missing_part_file_after_rename"
            continue
        shutil.copyfile(backup_part_files[0], path)
        normalized[report_name] = f"normalized_from:{source_dir.name}"
    return normalized


def build_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    existing_manifest: dict[str, Any] = {}
    existing_manifest_path = root / "manifest.json"
    if existing_manifest_path.is_file():
        try:
            existing_manifest = _read_json(existing_manifest_path)
        except (json.JSONDecodeError, OSError):
            existing_manifest = {}
    reports_dir = root / "reports"
    artifacts_dir = root / "artifacts"
    preprocessing_dir = artifacts_dir / "preprocessing"
    schema_dir = artifacts_dir / "schema"
    model_ready_dir = root / "model_ready"

    normalize_spark_csv_outputs(root)

    input_paths: dict[str, Any] = {}
    inventory_path = reports_dir / "dataset_inventory.csv"
    if inventory_path.is_file():
        with inventory_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                filename = row.get("filename")
                if filename:
                    input_paths[filename] = row

    selected_features_payload = {}
    feature_order_payload = {}
    split_thresholds_payload = {}
    imbalance_config_payload = {}
    if (preprocessing_dir / "selected_features.json").is_file():
        selected_features_payload = _read_json(preprocessing_dir / "selected_features.json")
    if (preprocessing_dir / "feature_order.json").is_file():
        feature_order_payload = _read_json(preprocessing_dir / "feature_order.json")
    if (preprocessing_dir / "split_thresholds.json").is_file():
        split_thresholds_payload = _read_json(preprocessing_dir / "split_thresholds.json")
    if (preprocessing_dir / "imbalance_config.json").is_file():
        imbalance_config_payload = _read_json(preprocessing_dir / "imbalance_config.json")

    processing_version = (
        feature_order_payload.get("processing_version")
        or existing_manifest.get("processing_version")
        or PROCESSING_VERSION
    )
    feature_schema_version = (
        feature_order_payload.get("feature_schema_version")
        or existing_manifest.get("feature_schema_version")
        or FEATURE_SCHEMA_VERSION
    )
    pipeline_version = existing_manifest.get("pipeline_version") or PIPELINE_VERSION

    model_ready_datasets: dict[str, Any] = {}
    for dataset_name in REQUIRED_DATASETS:
        dataset_path = model_ready_dir / dataset_name
        if not dataset_path.is_dir():
            continue
        ds = _dataset(dataset_path)
        schema_records = _schema_records(dataset_path)
        model_ready_datasets[dataset_name] = {
            "path": str(dataset_path),
            "row_count": int(ds.count_rows()),
            "column_count": len(ds.schema.names),
            "schema_hash": schema_hash(schema_records),
            "columns": ds.schema.names,
        }

    report_paths = {
        str(path.relative_to(root)): str(path)
        for path in reports_dir.rglob("*")
        if path.is_file()
    }

    schema_hashes = {}
    for schema_name in [
        "raw_train_transaction_schema.json",
        "raw_train_identity_schema.json",
        "raw_test_transaction_schema.json",
        "raw_test_identity_schema.json",
        "model_ready_schema.json",
    ]:
        schema_path = schema_dir / schema_name
        if schema_path.is_file():
            schema_payload = _read_json(schema_path)
            schema_hashes[schema_name] = schema_payload.get("schema_hash")

    manifest = {
        "project_name": "Fraud Detection / Fraud Risk Scoring",
        "pipeline_version": pipeline_version,
        "processing_version": processing_version,
        "feature_schema_version": feature_schema_version,
        "generated_at": utc_now_iso(),
        "environment": environment_metadata(),
        "input_paths": input_paths,
        "output_dir": str(root),
        "output_paths": {
            "curated": str(root / "curated"),
            "splits": str(root / "splits"),
            "model_ready": str(model_ready_dir),
            "feature_store": str(root / "feature_store"),
            "artifacts": str(artifacts_dir),
            "reports": str(reports_dir),
            "demo": str(root / "demo"),
        },
        "selected_features": selected_features_payload.get("selected_features", []),
        "feature_order": feature_order_payload.get("feature_columns", []),
        "split_thresholds": split_thresholds_payload,
        "imbalance_settings": imbalance_config_payload,
        "schema_hashes": schema_hashes,
        "model_ready_datasets": model_ready_datasets,
        "imputation_artifacts": {
            "numeric_medians": str(preprocessing_dir / "numeric_medians.json"),
            "category_policy": str(preprocessing_dir / "category_policy.json"),
            "outlier_thresholds": str(preprocessing_dir / "outlier_thresholds.json"),
            "split_thresholds": str(preprocessing_dir / "split_thresholds.json"),
            "imbalance_config": str(preprocessing_dir / "imbalance_config.json"),
            "feature_order": str(preprocessing_dir / "feature_order.json"),
            "selected_features": str(preprocessing_dir / "selected_features.json"),
        },
        "report_paths": report_paths,
        "verifier_result": {"status": "verification_pending"},
        "status": "verification_pending",
    }
    atomic_write_json(manifest, root / "manifest.json")
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Normalize processed outputs and regenerate manifest.json")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/ieee_cis_fraud_risk"))
    args = parser.parse_args(argv)
    manifest = build_manifest(args.output_dir)
    print(json.dumps({"status": "manifest_regenerated", "output_dir": str(args.output_dir), "datasets": list(manifest["model_ready_datasets"].keys())}, indent=2))


if __name__ == "__main__":
    main()
