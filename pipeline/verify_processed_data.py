"""Strict verification for downstream-ready IEEE-CIS outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FILES = ["train_transaction.csv", "train_identity.csv", "test_transaction.csv", "test_identity.csv"]
LABELED_DATASETS = ["train_original", "train_weighted", "train_balanced"]
REQUIRED_DATASETS = [*LABELED_DATASETS, "validation", "holdout", "kaggle_test"]


def _read_manifest(root: Path) -> dict:
    path = root / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") not in {"ready_for_downstream_training", "ready_for_training"}:
        raise RuntimeError(f"Manifest is not ready: {manifest.get('status')!r}")
    return manifest


def _dataset_has_data(path: Path) -> bool:
    return path.is_dir() and any(p.is_file() and p.stat().st_size > 0 for p in path.rglob("*"))


def _parquet_columns(path: Path) -> set[str]:
    try:
        import pyarrow.dataset as ds  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for Parquet verification") from exc
    return set(ds.dataset(str(path), format="parquet").schema.names)


def verify(root: Path) -> dict:
    manifest = _read_manifest(root)
    model_ready = root / "model_ready"
    missing = [name for name in REQUIRED_DATASETS if not _dataset_has_data(model_ready / name)]
    if missing:
        raise FileNotFoundError(f"Missing or empty model-ready datasets: {missing}")
    if not (model_ready / "train_weighted").is_dir():
        raise FileNotFoundError("Weighted training dataset is required")
    schemas = {name: _parquet_columns(model_ready / name) for name in REQUIRED_DATASETS}
    for name in LABELED_DATASETS + ["validation", "holdout"]:
        if "TransactionID" not in schemas[name] or "isFraud" not in schemas[name]:
            raise RuntimeError(f"{name} must contain TransactionID and isFraud")
    if "TransactionID" not in schemas["kaggle_test"]:
        raise RuntimeError("kaggle_test must contain TransactionID")
    if "class_weight" not in schemas["train_weighted"]:
        raise RuntimeError("train_weighted must contain class_weight")
    if schemas["train_original"] != schemas["validation"] or schemas["validation"] != schemas["holdout"]:
        raise RuntimeError("Labeled model-ready schemas are inconsistent")
    result = {
        "status": "ready_for_downstream_training",
        "root": str(root.resolve()),
        "datasets": REQUIRED_DATASETS,
        "manifest_status": manifest.get("status"),
        "numeric_feature_count": len(manifest.get("numeric_features", [])),
        "categorical_feature_count": len(manifest.get("categorical_features", [])),
        "schema_checked": True,
    }
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify model-ready Parquet output contract.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/ieee_cis_fraud_risk"))
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
