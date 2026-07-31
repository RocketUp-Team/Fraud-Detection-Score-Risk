import json
from pathlib import Path

from pipeline import verify_processed_data


def test_verify_normalizes_spark_csv_report_dirs(tmp_path, monkeypatch):
    root = tmp_path
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "processing_version": "v2026.07.31",
                "feature_schema_version": "schema-2026.07.31",
            }
        ),
        encoding="utf-8",
    )
    for dataset_name in [
        "train_original",
        "train_weighted",
        "train_balanced",
        "validation",
        "holdout",
        "kaggle_test",
    ]:
        (root / "model_ready" / dataset_name).mkdir(parents=True, exist_ok=True)

    (root / "artifacts" / "preprocessing").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "schema").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)

    for artifact_name in [
        "feature_order.json",
        "numeric_medians.json",
        "model_ready_schema.json",
        "outlier_thresholds.json",
    ]:
        (root / "artifacts" / "preprocessing" / artifact_name).write_text("{}", encoding="utf-8")
    (root / "artifacts" / "schema" / "model_ready_schema.json").write_text("{}", encoding="utf-8")

    for report_name in [
        "dataset_inventory.csv",
        "data_quality_summary.csv",
        "duplicate_summary.csv",
        "invalid_records_summary.csv",
        "missingness_profile.csv",
        "missingness_strategy.csv",
        "split_summary.csv",
        "imbalance_comparison.csv",
        "feature_catalog.csv",
    ]:
        (root / "reports" / report_name).write_text("placeholder\n", encoding="utf-8")

    join_dir = root / "reports" / "join_audit.csv"
    join_dir.mkdir(parents=True, exist_ok=True)
    (join_dir / "part-00000.csv").write_text("TransactionID\n1\n", encoding="utf-8")

    monkeypatch.setattr(verify_processed_data, "_dataset_row_count", lambda path: 1)
    monkeypatch.setattr(
        verify_processed_data,
        "_dataset_columns",
        lambda path: [
            "TransactionID",
            "isFraud",
            "feature_1",
            "processing_version",
            "feature_schema_version",
        ],
    )
    monkeypatch.setattr(
        verify_processed_data,
        "_table_column_values",
        lambda path, column: [1] if column == "TransactionID" else ["v2026.07.31"],
    )
    monkeypatch.setattr(verify_processed_data, "_schema_records", lambda path: [])

    payload = verify_processed_data.verify(root, write_report=False)

    assert payload["status"] == "ready_for_downstream_training"
    assert (root / "reports" / "join_audit.csv").exists()
