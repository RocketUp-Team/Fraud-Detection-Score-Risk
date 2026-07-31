"""Strict verification for downstream-ready IEEE-CIS outputs."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract_utils import (
    FEATURE_SCHEMA_VERSION,
    PROCESSING_VERSION,
    atomic_write_json,
    schema_hash,
)
from .processed_contract import normalize_spark_csv_outputs


LABELED_DATASETS = ["train_original", "train_weighted", "train_balanced", "validation", "holdout"]
REQUIRED_DATASETS = [*LABELED_DATASETS, "kaggle_test"]
WEIGHTED_DATASET = "train_weighted"
REPORT_FILES = [
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


@dataclass
class CheckResult:
    name: str
    ok: bool
    expected: Any = None
    actual: Any = None
    path: str | None = None
    fix: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "expected": self.expected,
            "actual": self.actual,
            "path": self.path,
            "fix": self.fix,
        }


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset(path: Path):
    try:
        import pyarrow.dataset as ds  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for Parquet verification") from exc
    return ds.dataset(str(path), format="parquet")


def _dataset_columns(path: Path) -> list[str]:
    return list(_dataset(path).schema.names)


def _dataset_row_count(path: Path) -> int:
    return int(_dataset(path).count_rows())


def _table_column_values(path: Path, column: str) -> list[Any]:
    table = _dataset(path).to_table(columns=[column])
    return table[column].to_pylist()


def _schema_records(path: Path) -> list[dict[str, str]]:
    dataset = _dataset(path)
    return [
        {"name": field.name, "type": str(field.type)}
        for field in dataset.schema
    ]


def _write_report(root: Path, payload: dict[str, Any]) -> None:
    try:
        atomic_write_json(payload, root / "reports" / "verification_report.json")
    except PermissionError:
        fallback_path = root / "verification_report.json"
        atomic_write_json(payload, fallback_path)


def verify(root: Path, write_report: bool = False) -> dict[str, Any]:
    root = root.resolve()
    normalize_spark_csv_outputs(root)
    manifest = _read_manifest(root)
    expected_processing_version = manifest.get("processing_version") or PROCESSING_VERSION
    expected_feature_schema_version = (
        manifest.get("feature_schema_version") or FEATURE_SCHEMA_VERSION
    )
    checks: list[CheckResult] = []
    model_ready = root / "model_ready"
    preprocessing_dir = root / "artifacts" / "preprocessing"
    schema_dir = root / "artifacts" / "schema"
    reports_dir = root / "reports"

    checks.append(CheckResult(
        name="manifest.processing_version",
        ok=bool(manifest.get("processing_version")),
        expected="non-empty processing_version",
        actual=manifest.get("processing_version"),
        path=str(root / "manifest.json"),
        fix="Regenerate manifest with processing_version.",
    ))
    checks.append(CheckResult(
        name="manifest.feature_schema_version",
        ok=bool(manifest.get("feature_schema_version")),
        expected="non-empty feature_schema_version",
        actual=manifest.get("feature_schema_version"),
        path=str(root / "manifest.json"),
        fix="Regenerate manifest with feature_schema_version.",
    ))

    for dataset_name in REQUIRED_DATASETS:
        dataset_path = model_ready / dataset_name
        exists = dataset_path.is_dir()
        checks.append(CheckResult(
            name=f"dataset.exists.{dataset_name}",
            ok=exists,
            expected="directory exists",
            actual=str(dataset_path),
            path=str(dataset_path),
            fix="Run preprocessing to materialize all model_ready datasets.",
        ))
        if not exists:
            continue

        row_count = _dataset_row_count(dataset_path)
        columns = _dataset_columns(dataset_path)
        checks.append(CheckResult(
            name=f"dataset.non_empty.{dataset_name}",
            ok=row_count > 0,
            expected="row_count > 0",
            actual=row_count,
            path=str(dataset_path),
            fix="Inspect upstream export stage for empty dataset.",
        ))
        checks.append(CheckResult(
            name=f"dataset.transaction_id.{dataset_name}",
            ok="TransactionID" in columns,
            expected="TransactionID column present",
            actual=columns,
            path=str(dataset_path),
            fix="Include TransactionID in all model-ready datasets.",
        ))

        if dataset_name in LABELED_DATASETS:
            checks.append(CheckResult(
                name=f"dataset.label.{dataset_name}",
                ok="isFraud" in columns,
                expected="isFraud column present",
                actual=columns,
                path=str(dataset_path),
                fix="Include isFraud in labeled datasets.",
            ))
        else:
            checks.append(CheckResult(
                name=f"dataset.no_label.{dataset_name}",
                ok="isFraud" not in columns,
                expected="isFraud column absent",
                actual=columns,
                path=str(dataset_path),
                fix="Drop isFraud from kaggle_test contract.",
            ))

        checks.append(CheckResult(
            name=f"dataset.class_weight_policy.{dataset_name}",
            ok=("class_weight" in columns) == (dataset_name == WEIGHTED_DATASET),
            expected="class_weight only in train_weighted",
            actual=columns,
            path=str(dataset_path),
            fix="Ensure class_weight exists only for train_weighted.",
        ))

        if "processing_version" in columns:
            versions = set(v for v in _table_column_values(dataset_path, "processing_version") if v is not None)
            checks.append(CheckResult(
                name=f"dataset.processing_version.{dataset_name}",
                ok=versions == {expected_processing_version},
                expected=expected_processing_version,
                actual=sorted(versions),
                path=str(dataset_path),
                fix="Rewrite dataset metadata columns from preprocessing finalizer.",
            ))

        if "feature_schema_version" in columns:
            versions = set(v for v in _table_column_values(dataset_path, "feature_schema_version") if v is not None)
            checks.append(CheckResult(
                name=f"dataset.feature_schema_version.{dataset_name}",
                ok=versions == {expected_feature_schema_version},
                expected=expected_feature_schema_version,
                actual=sorted(versions),
                path=str(dataset_path),
                fix="Rewrite dataset metadata columns from preprocessing finalizer.",
            ))

    feature_order_path = preprocessing_dir / "feature_order.json"
    medians_path = preprocessing_dir / "numeric_medians.json"
    model_ready_schema_path = schema_dir / "model_ready_schema.json"
    checks.append(CheckResult("artifact.feature_order", feature_order_path.is_file(), "feature_order.json exists", str(feature_order_path), str(feature_order_path), "Generate feature order artifact."))
    checks.append(CheckResult("artifact.numeric_medians", medians_path.is_file(), "numeric_medians.json exists", str(medians_path), str(medians_path), "Generate preprocessing median artifact."))
    checks.append(CheckResult("artifact.model_ready_schema", model_ready_schema_path.is_file(), "model_ready_schema.json exists", str(model_ready_schema_path), str(model_ready_schema_path), "Generate model_ready schema artifact."))

    canonical_feature_columns: list[str] | None = None
    if feature_order_path.is_file():
        feature_contract = _read_json(feature_order_path)
        raw_feature_columns = feature_contract.get("feature_columns")
        if isinstance(raw_feature_columns, list):
            canonical_feature_columns = raw_feature_columns
        checks.append(CheckResult(
            name="artifact.feature_order.processing_version",
            ok=feature_contract.get("processing_version") == expected_processing_version,
            expected=expected_processing_version,
            actual=feature_contract.get("processing_version"),
            path=str(feature_order_path),
            fix="Regenerate feature_order.json with the dataset processing version.",
        ))
        checks.append(CheckResult(
            name="artifact.feature_order.feature_schema_version",
            ok=feature_contract.get("feature_schema_version") == expected_feature_schema_version,
            expected=expected_feature_schema_version,
            actual=feature_contract.get("feature_schema_version"),
            path=str(feature_order_path),
            fix="Regenerate feature_order.json with the dataset feature schema version.",
        ))
        checks.append(CheckResult(
            name="artifact.feature_order.count",
            ok=(
                canonical_feature_columns is not None
                and len(canonical_feature_columns) == 68
            ),
            expected=68,
            actual=(
                len(canonical_feature_columns)
                if canonical_feature_columns is not None
                else None
            ),
            path=str(feature_order_path),
            fix="Restore the canonical 68-feature logical contract.",
        ))
        checks.append(CheckResult(
            name="artifact.feature_order.unique",
            ok=(
                canonical_feature_columns is not None
                and len(canonical_feature_columns)
                == len(set(canonical_feature_columns))
            ),
            expected="68 unique feature names",
            actual=canonical_feature_columns,
            path=str(feature_order_path),
            fix="Remove duplicate names from the canonical feature order.",
        ))

    if expected_processing_version == PROCESSING_VERSION:
        outlier_path = preprocessing_dir / "outlier_thresholds.json"
        outlier_payload = _read_json(outlier_path) if outlier_path.is_file() else {}
        checks.append(CheckResult(
            name="artifact.outliers.train_only_fit",
            ok=outlier_payload.get("fit_scope") == "chronological_training_only",
            expected="chronological_training_only",
            actual=outlier_payload.get("fit_scope"),
            path=str(outlier_path),
            fix="Fit amount thresholds after chronological splitting using train only.",
        ))

    for report_name in REPORT_FILES:
        report_path = reports_dir / report_name
        exists = report_path.is_file() or (
            report_path.is_dir() and any(
                child.is_file() and child.name.startswith("part-") and child.suffix == ".csv"
                for child in report_path.iterdir()
            )
        )
        checks.append(CheckResult(
            name=f"report.{report_name}",
            ok=exists,
            expected="report exists",
            actual=str(report_path),
            path=str(report_path),
            fix=f"Generate report {report_name} during preprocessing.",
        ))

    # Schema consistency for all six public model-ready datasets.
    dataset_feature_columns: dict[str, list[str]] = {}
    for dataset_name in REQUIRED_DATASETS:
        dataset_path = model_ready / dataset_name
        if not dataset_path.is_dir():
            continue
        columns = _dataset_columns(dataset_path)
        feature_columns = [c for c in columns if c not in {"TransactionID", "isFraud", "class_weight", "split_name", "processing_version", "feature_schema_version", "generated_at"}]
        dataset_feature_columns[dataset_name] = feature_columns
    if dataset_feature_columns:
        baseline = next(iter(dataset_feature_columns.values()))
        for dataset_name, columns in dataset_feature_columns.items():
            checks.append(CheckResult(
                name=f"schema.feature_consistency.{dataset_name}",
                ok=columns == baseline,
                expected=baseline,
                actual=columns,
                path=str(model_ready / dataset_name),
                fix="Ensure model-ready feature order/selection is identical across all datasets.",
            ))
            if canonical_feature_columns is not None:
                checks.append(CheckResult(
                    name=f"schema.feature_contract.{dataset_name}",
                    ok=columns == canonical_feature_columns,
                    expected=canonical_feature_columns,
                    actual=columns,
                    path=str(model_ready / dataset_name),
                    fix="Export every dataset in the exact canonical feature order.",
                ))

    # Split order and overlap
    split_bounds: dict[str, tuple[Any, Any]] = {}
    seen_ids: dict[str, set[Any]] = {}
    for dataset_name in ["train_original", "validation", "holdout"]:
        dataset_path = model_ready / dataset_name
        if not dataset_path.is_dir():
            continue
        columns = _dataset_columns(dataset_path)
        if "TransactionDT" in columns:
            values = _table_column_values(dataset_path, "TransactionDT")
            split_bounds[dataset_name] = (min(values), max(values))
        if "TransactionID" in columns:
            txn_ids = _table_column_values(dataset_path, "TransactionID")
            seen_ids[dataset_name] = set(txn_ids)
            checks.append(CheckResult(
                name=f"dataset.duplicate_transaction_id.{dataset_name}",
                ok=len(txn_ids) == len(seen_ids[dataset_name]),
                expected="unique TransactionID",
                actual={"rows": len(txn_ids), "distinct": len(seen_ids[dataset_name])},
                path=str(dataset_path),
                fix="Inspect split export for duplicated TransactionID rows.",
            ))

    if {"train_original", "validation", "holdout"} <= set(split_bounds):
        train_min, train_max = split_bounds["train_original"]
        val_min, val_max = split_bounds["validation"]
        hold_min, hold_max = split_bounds["holdout"]
        checks.append(CheckResult(
            name="split.temporal_order.train_validation",
            ok=train_max <= val_min,
            expected="train max <= validation min",
            actual={"train_max": train_max, "validation_min": val_min},
            path=str(model_ready),
            fix="Recompute chronological split before fit/export.",
        ))
        checks.append(CheckResult(
            name="split.temporal_order.validation_holdout",
            ok=val_max <= hold_min,
            expected="validation max <= holdout min",
            actual={"validation_max": val_max, "holdout_min": hold_min},
            path=str(model_ready),
            fix="Recompute chronological split before fit/export.",
        ))

    if {"train_original", "validation", "holdout"} <= set(seen_ids):
        checks.append(CheckResult(
            name="split.overlap.train_validation",
            ok=seen_ids["train_original"].isdisjoint(seen_ids["validation"]),
            expected="no overlap",
            actual=len(seen_ids["train_original"] & seen_ids["validation"]),
            path=str(model_ready),
            fix="Ensure TransactionID does not appear in multiple splits.",
        ))
        checks.append(CheckResult(
            name="split.overlap.validation_holdout",
            ok=seen_ids["validation"].isdisjoint(seen_ids["holdout"]),
            expected="no overlap",
            actual=len(seen_ids["validation"] & seen_ids["holdout"]),
            path=str(model_ready),
            fix="Ensure TransactionID does not appear in multiple splits.",
        ))
        checks.append(CheckResult(
            name="split.overlap.train_holdout",
            ok=seen_ids["train_original"].isdisjoint(seen_ids["holdout"]),
            expected="no overlap",
            actual=len(seen_ids["train_original"] & seen_ids["holdout"]),
            path=str(model_ready),
            fix="Ensure TransactionID does not appear in multiple splits.",
        ))

    # Manifest row counts
    manifest_outputs = manifest.get("model_ready_datasets", {})
    for dataset_name in REQUIRED_DATASETS:
        dataset_path = model_ready / dataset_name
        if not dataset_path.is_dir():
            continue
        if dataset_name in manifest_outputs and "row_count" in manifest_outputs[dataset_name]:
            actual = _dataset_row_count(dataset_path)
            expected = int(manifest_outputs[dataset_name]["row_count"])
            checks.append(CheckResult(
                name=f"manifest.row_count.{dataset_name}",
                ok=actual == expected,
                expected=expected,
                actual=actual,
                path=str(dataset_path),
                fix="Regenerate manifest after export or fix stale row counts.",
            ))
        if dataset_name in manifest_outputs and "schema_hash" in manifest_outputs[dataset_name]:
            actual_hash = schema_hash(_schema_records(dataset_path))
            expected_hash = manifest_outputs[dataset_name]["schema_hash"]
            checks.append(CheckResult(
                name=f"manifest.schema_hash.{dataset_name}",
                ok=actual_hash == expected_hash,
                expected=expected_hash,
                actual=actual_hash,
                path=str(dataset_path),
                fix="Regenerate manifest/schema artifacts from latest export.",
            ))

    failed = [c for c in checks if not c.ok]
    payload = {
        "status": "ready_for_downstream_training" if not failed else "verification_failed",
        "processing_version": manifest.get("processing_version"),
        "feature_schema_version": manifest.get("feature_schema_version"),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": [c.as_dict() for c in checks],
    }
    if write_report:
        _write_report(root, payload)
    if failed:
        first = failed[0]
        raise RuntimeError(
            f"Verification failed at {first.name}: expected={first.expected!r} actual={first.actual!r} "
            f"path={first.path!r} fix={first.fix!r}"
        )
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify model-ready Parquet output contract.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/ieee_cis_fraud_risk"))
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.output_dir, write_report=True), indent=2))


if __name__ == "__main__":
    main()
