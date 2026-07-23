# IEEE-CIS BDA501 Spark Preprocessing Bundle

## 1. Copy files into the project

Copy these bundle files into:

```text
D:\MSE\16. Big Data\Fraud-Detection-Score-Risk
```

Keep the raw dataset at:

```text
D:\MSE\16. Big Data\Fraud-Detection-Score-Risk\data\data\ieee-fraud-detection
```

Required files:

- `train_transaction.csv`
- `train_identity.csv`
- `test_transaction.csv`
- `test_identity.csv`
- `sample_submission.csv` (optional for validation/reference)

## 2. Run the notebook locally

Install Java 17 and Python dependencies, then open:

```text
ieee_cis_bda501_complete_pipeline.ipynb
```

The notebook auto-detects the exact Windows path and creates:

```text
data\processed\ieee_cis_spark
```

## 3. Run preprocessing with Docker

Open PowerShell in the project root:

```powershell
docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess
```

The container reads raw files through a read-only bind mount and writes outputs back to the host:

```text
D:\MSE\16. Big Data\Fraud-Detection-Score-Risk\data\processed\ieee_cis_spark
```

This design deliberately avoids copying the Kaggle dataset into the Docker image. The image remains reproducible, and processed data persists even after the container exits.

The preprocessing image now bundles Java, Spark, and Hadoop so Spark can write parquet output cleanly inside the container without relying on a Windows-only `winutils.exe` setup.

## 4. Verify training readiness

```powershell
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
```

Expected status:

```json
{
  "status": "ready_for_training"
}
```

## 5. Training paths inside Docker

A model-training container should mount:

```yaml
volumes:
  - ./data/processed:/app/data/processed:ro
```

It can then read:

```text
/app/data/processed/ieee_cis_spark/model_ready/train_original
/app/data/processed/ieee_cis_spark/model_ready/train_weighted
/app/data/processed/ieee_cis_spark/model_ready/train_balanced
/app/data/processed/ieee_cis_spark/model_ready/validation
/app/data/processed/ieee_cis_spark/model_ready/holdout
/app/data/processed/ieee_cis_spark/model_ready/kaggle_test
```

## 6. Output contract

- `feature_store/`: wide Spark feature tables, partitioned by transaction week.
- `model_ready/train_original/`: chronological training data with median-imputed numeric features.
- `model_ready/train_weighted/`: original training data plus `class_weight`.
- `model_ready/train_balanced/`: controlled majority undersampling, default ratio 4 legitimate : 1 fraud.
- `model_ready/validation/`: untouched chronological validation distribution.
- `model_ready/holdout/`: untouched chronological final evaluation distribution.
- `model_ready/kaggle_test/`: training-compatible Kaggle test features.
- `reports/`: profile, quality, EDA, balance, and Decision Tree evaluation outputs.
- `demo/`: representative fraud/legitimate prediction cases and Kaggle-format predictions.
- `artifacts/decision_tree_demo/`: saved Spark MLlib Decision Tree pipeline.
- `manifest.json`: paths, row counts, feature lists, split boundaries, and metrics.

## 7. Important methodological decisions

- The split is chronological using `TransactionDT`; random splitting is not used.
- Median imputation is fitted on the training period only.
- Card, email, and device aggregate lookups are built from the training period only.
- Only training data is undersampled or weighted.
- Validation and holdout class distributions remain unchanged.
- PR-AUC and fraud recall are reported because accuracy is misleading for strongly imbalanced fraud data.

---

## Fix `ModuleNotFoundError: No module named 'pyspark'` when running the notebook locally

The Docker preprocessing image already contains PySpark, Java, and Hadoop. This error only means the local VS Code/Jupyter kernel does not contain PySpark, or a different Python interpreter was selected.

### Recommended Windows setup

From the project root:

```powershell
cd "D:\MSE\16. Big Data\Fraud-Detection-Score-Risk"
Set-ExecutionPolicy -Scope Process Bypass
.\setup_local_windows.ps1
```

Then restart VS Code, open the notebook, and select:

```text
Python (Fraud Spark)
```

The first notebook code cell also installs `pyspark==3.5.1` into the active kernel automatically and checks Java 17.

### Manual commands

```powershell
winget install EclipseAdoptium.Temurin.17.JDK
.\.venv\Scripts\python.exe -m pip install -r requirements.local.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name fraud-detection-spark --display-name "Python (Fraud Spark)"
```

Completely restart VS Code/Jupyter after installing Java so the updated `PATH` and `JAVA_HOME` can be detected.
