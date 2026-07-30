"""Validate the model-ready contract before a training run."""
import json

from . import config
from .data import DatasetNotFoundError, load_dataset, split_validation_windows
from .features import (
    CONTRACT_METADATA_COLS,
    _canonical_feature_columns,
    feature_contract_metadata,
)


DATASETS = ("train_original", "train_weighted", "train_balanced", "validation", "holdout", "kaggle_test")


def main() -> None:
    canonical = _canonical_feature_columns()
    if not canonical:
        raise SystemExit("Không tìm thấy canonical feature contract feature_order.json")

    contract = feature_contract_metadata()
    report = {
        "feature_count": len(canonical),
        "data_root": str(config.PROCESSED_DATA_ROOT),
        "processing_version": contract["processing_version"],
        "feature_schema_version": contract["feature_schema_version"],
        "datasets": {},
    }
    for name in DATASETS:
        try:
            df = load_dataset(name)
        except DatasetNotFoundError as exc:
            raise SystemExit(str(exc)) from exc
        columns = set(df.columns)
        missing = [c for c in canonical if c not in columns]
        if missing:
            raise SystemExit(f"{name}: thiếu feature contract columns: {missing[:10]}")
        if name == "kaggle_test" and config.TARGET_COL in columns:
            raise SystemExit("kaggle_test không được chứa isFraud")
        if name != "kaggle_test" and config.TARGET_COL not in columns:
            raise SystemExit(f"{name}: thiếu isFraud")
        if name == "train_weighted" and config.WEIGHT_COL not in columns:
            raise SystemExit("train_weighted phải có class_weight")
        duplicate_count = df.groupBy(config.ID_COL).count().filter("count > 1").count()
        if duplicate_count:
            raise SystemExit(f"{name}: phát hiện {duplicate_count} TransactionID bị duplicate")
        processing_versions = [
            row["processing_version"]
            for row in df.select("processing_version").distinct().collect()
        ]
        feature_schema_versions = [
            row["feature_schema_version"]
            for row in df.select("feature_schema_version").distinct().collect()
        ]
        if processing_versions != [contract["processing_version"]]:
            raise SystemExit(
                f"{name}: processing_version mismatch: {processing_versions} "
                f"!= {contract['processing_version']}"
            )
        if feature_schema_versions != [contract["feature_schema_version"]]:
            raise SystemExit(
                f"{name}: feature_schema_version mismatch: {feature_schema_versions} "
                f"!= {contract['feature_schema_version']}"
            )
        report["datasets"][name] = {
            "rows": df.count(),
            "columns": len(df.columns),
            "extra_non_feature_columns": sorted(columns.intersection(CONTRACT_METADATA_COLS)),
        }

        if name == "validation":
            windows = split_validation_windows(df)
            report["validation_windows"] = {
                "counts": windows.counts,
                "selection_boundary": windows.selection_boundary,
                "calibration_boundary": windows.calibration_boundary,
            }

    config.TRAINING_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TRAINING_ARTIFACTS_DIR / "data_validation_v3.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"[validate] saved -> {path}")


if __name__ == "__main__":
    main()
