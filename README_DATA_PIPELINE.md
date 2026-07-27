# IEEE-CIS Fraud Risk Data Pipeline

This Spark pipeline converts the IEEE-CIS transaction and identity CSV files into reusable, leakage-safe, model-ready Parquet datasets. The raw files are never copied into the Docker image.

## Run

From the project root:

```powershell
docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
```

Raw input:

```text
data/data/ieee-fraud-detection/
```

Processed output:

```text
data/processed/ieee_cis_fraud_risk/
```

The image uses Java 17, Spark 3.5.1 and Hadoop 3.3.6. It runs Spark locally inside Linux with bounded shuffle parallelism. The source dataset is approximately 1.3 GB and must contain the four required CSV files; `sample_submission.csv` is optional.

If a long Docker preprocessing run writes Parquet artifacts but stops before the manifest is finalized, regenerate the downstream contract and normalize Spark CSV report folders with:

```powershell
python -m pipeline.processed_contract --output-dir .\data\processed\ieee_cis_fraud_risk
python -m pipeline.verify_processed_data --output-dir .\data\processed\ieee_cis_fraud_risk
```

## Pipeline stages

The workflow performs source discovery and size validation, typed Spark ingestion, identity-column normalization, key and join audits, missingness profiling, categorical cleanup, temporal feature engineering, Spark SQL EDA, chronological splitting, training-only median imputation and entity aggregates, weighted and undersampled training variants, Decision Tree comparison, demo-case extraction, Parquet export, and manifest generation.

The maintained root entrypoint is `pipeline/fraud_risk_data_pipeline.py`. The shared Spark implementation is kept at `data/ieee_cis/pipeline/ieee_cis_preprocess.py` and is copied into the image by the root Dockerfile.

## Downstream handoff

Recommended starting point:

```text
data/processed/ieee_cis_fraud_risk/model_ready/train_weighted/
```

Read [HANDOVER_PROCESSED_DATA.md](HANDOVER_PROCESSED_DATA.md) and [DATA_DICTIONARY.md](DATA_DICTIONARY.md) before training. The proposed risk-score mapping is documented separately in `RISK_SCORE_DATA_CONTRACT.md`.
The explicit model-ready schema and metadata contract is documented in `MODEL_READY_DATA_CONTRACT.md`.

## Configuration

Edit [config/pipeline_config.yaml](config/pipeline_config.yaml), or override paths and runtime flags:

```powershell
python -m pipeline.fraud_risk_data_pipeline `
  --raw-dir .\data\data\ieee-fraud-detection `
  --output-dir .\data\processed\ieee_cis_fraud_risk `
  --master local[4]
```

For the full dataset, Docker Linux is the supported Parquet path. Native Windows Spark may run exploratory stages but can fail on Hadoop filesystem permissions.
