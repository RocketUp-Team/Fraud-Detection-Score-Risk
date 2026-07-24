# Handover: Processed IEEE-CIS Data

The pipeline joins transactions to identity records with a left join, normalizes `id-xx` to `id_xx`, profiles quality/missingness, creates explainable features, splits labeled records chronologically, fits training-only transformations, and exports Parquet.

## Datasets

- `model_ready/train_original`: original chronological training distribution.
- `model_ready/train_weighted`: original rows plus `class_weight`; recommended for weighted models.
- `model_ready/train_balanced`: deterministic legitimate undersampling; fraud rows are retained.
- `model_ready/validation`: untouched validation period.
- `model_ready/holdout`: untouched final evaluation period.
- `model_ready/kaggle_test`: unlabeled scoring features.
- `feature_store/`: train-derived card, email and device aggregate lookups.
- `reports/`, `demo/`, `artifacts/`: audit outputs, examples and Spark ML artifacts.

Example:

```python
train = spark.read.parquet('/app/data/processed/ieee_cis_fraud_risk/model_ready/train_weighted')
validation = spark.read.parquet('/app/data/processed/ieee_cis_fraud_risk/model_ready/validation')
```

Use `isFraud` as the target for labeled datasets and preserve `TransactionID`. Do not refit medians, category mappings or entity aggregates on validation, holdout or test. Use PR-AUC and fraud recall as primary evaluation views.

## Verification and limitations

Run `docker compose -f docker-compose.preprocessing.yml run --rm verify-processed`. The verifier is the authoritative readiness check. `TransactionDT` is relative time, not a calendar timestamp. The Decision Tree is a BDA501 baseline, not a production model. Risk policy thresholds require business calibration.
