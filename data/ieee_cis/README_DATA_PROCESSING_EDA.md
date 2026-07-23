# IEEE-CIS Data Processing and EDA

This bundle prepares the IEEE-CIS transaction and identity data for the model workflow described in `docs/RISK_SCORING_PLAN.md`.

It provides Spark ingestion, schema validation, join auditing, missingness profiling, Spark SQL EDA, chronological splitting, leakage-safe card/email/device aggregates, class-imbalance datasets, Decision Tree comparison, demo cases and a handoff contract for the model workflow.

## Run with Docker

From the repository root:

```powershell
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml build
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml run --rm preprocess
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml run --rm verify-processed
```

The raw Kaggle files are mounted read-only from `data/data/ieee-fraud-detection`. Processed output is written to `data/processed/ieee_cis_spark`.

## Notebook and script

- Notebook: `data/ieee_cis/ieee_cis_data_processing_eda.ipynb`
- Docker entrypoint: `data/ieee_cis/pipeline/data_processing_eda.py`
- Shared implementation: `data/ieee_cis/pipeline/ieee_cis_preprocess.py`

The notebook is the reader-facing workflow. The Python entrypoint and Docker job use the same implementation so the handoff is reproducible.

## Input contract

Required files:

- `train_transaction.csv`
- `train_identity.csv`
- `test_transaction.csv`
- `test_identity.csv`

`sample_submission.csv` is optional. The discovery logic checks Windows and Docker layouts and reports every checked path when files are missing.

## Output contract

The pipeline writes:

- `curated/` and `feature_store/` Spark Parquet datasets.
- `model_ready/train_original/` with the original chronological training distribution.
- `model_ready/train_weighted/` with `class_weight` for weighted models.
- `model_ready/train_balanced/` with controlled legitimate undersampling.
- `model_ready/validation/` and `model_ready/holdout/` with untouched labels and class distributions.
- `model_ready/kaggle_test/` with training-compatible unlabeled features.
- `reports/` containing inventory, key/join audit, missingness, Spark SQL EDA, split, imbalance and model metrics.
- `demo/` containing fraud, legitimate, TP, TN, FP and FN examples when model inference is enabled.
- `artifacts/` containing the saved Spark MLlib Decision Tree models.
- `manifest.json` containing source, split, feature and metric metadata.
- `HANDOVER_TO_QUAN.md` containing the downstream model contract.

## Methodology contract

- `TransactionID` is validated for nulls and duplicates before joins.
- Transaction to identity is a left join and must preserve transaction row count.
- Test identity headers are normalized from `id-xx` to `id_xx`.
- The labeled dataset is split chronologically by `TransactionDT` into 70% train, 15% validation and 15% holdout.
- Aggregate features and median imputation are fitted only on the training period.
- Validation and holdout are never undersampled or resampled.
- Model selection uses validation PR-AUC; holdout is evaluated only after selection.
- Native Windows does not perform full Parquet export. Use Docker Linux for Parquet.

## Handoff to the model workflow

Read `data/ieee_cis/HANDOVER_TO_QUAN.md` before integration and `data/processed/ieee_cis_spark/HANDOVER_TO_QUAN.md` after the Docker job completes. The recommended input is `model_ready/train_weighted/` for algorithms supporting weights, or `model_ready/train_balanced/` for algorithms that do not.

The model workflow should not refit imputation or aggregates on validation, holdout or Kaggle test. It should preserve `TransactionID`, use `isFraud` only as the training label, and report PR-AUC, ROC-AUC, precision, recall, F1 and confusion-matrix counts.
