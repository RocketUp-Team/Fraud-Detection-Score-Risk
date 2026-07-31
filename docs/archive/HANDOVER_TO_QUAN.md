# IEEE-CIS Feature Handover

This document defines the data contract between the Spark preprocessing workflow and the model workflow described in `docs/RISK_SCORING_PLAN.md`.

## Run and verify

From the repository root:

```powershell
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml build
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml run --rm preprocess
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml run --rm verify-processed
```

Input is mounted read-only from `data/data/ieee-fraud-detection`. Output is written to `data/processed/ieee_cis_spark`.

## Model-ready datasets

| Dataset | Purpose |
|---|---|
| `model_ready/train_original` | Chronological training data with original class distribution |
| `model_ready/train_weighted` | Same training rows plus `class_weight` |
| `model_ready/train_balanced` | Training-only controlled undersampling, default 4:1 legitimate to fraud |
| `model_ready/validation` | Chronological validation data, never resampled |
| `model_ready/holdout` | Chronological final evaluation data, never resampled |
| `model_ready/kaggle_test` | Unlabeled test features with the training feature contract |

Read with Spark:

```python
train = spark.read.parquet("data/processed/ieee_cis_spark/model_ready/train_weighted")
validation = spark.read.parquet("data/processed/ieee_cis_spark/model_ready/validation")
holdout = spark.read.parquet("data/processed/ieee_cis_spark/model_ready/holdout")
```

## Target and feature policy

- Target: `isFraud`.
- Key: `TransactionID`.
- Time column: `TransactionDT`, a relative transaction-time value.
- Numeric missing values: median fitted only on the training period.
- Categorical missing values: explicit `__MISSING__` category.
- Test identity headers are normalized from `id-xx` to `id_xx`.

Recommended compact model features include `TransactionAmt`, `log_transaction_amount`, `amount_decimal`, `TransactionDT`, `transaction_day`, `transaction_week`, `transaction_hour`, `selected_missing_count`, `selected_missing_ratio`, `identity_missing_count`, `has_identity`, `has_device_info`, `has_p_email`, `has_r_email`, `same_email_domain`, `high_amount_flag`, `dist1`, `dist2`, selected `C*`/`D*` features, card history features, email history features, device history features, `ProductCD`, `card4`, `card6`, `DeviceType`, `device_family`, `M4` and `amount_band`.

## Leakage precautions

- Train, validation and holdout are chronological 70/15/15 splits using `TransactionDT`.
- Card, email and device aggregate lookup tables are fitted only from chronological training rows.
- Median imputation is fitted only from chronological training rows.
- Do not refit transformations on validation, holdout or Kaggle test.
- Do not use `isFraud` aggregate rates as model features unless an explicit historical or out-of-fold scheme is implemented.
- Select the model and threshold on validation; evaluate holdout only once after selection.

## Reports and demo

Reports are under `reports/`, including source inventory, key/join audit, missingness, class balance, chronological split, Spark SQL EDA and Decision Tree metrics.

Demo files are under `demo/`, including real fraud, legitimate, true-positive, true-negative, false-positive and false-negative cases when model inference is enabled.

The model workflow should report PR-AUC, ROC-AUC, precision, recall, F1 and TP/TN/FP/FN. Accuracy alone is not an appropriate fraud metric because the class distribution is strongly imbalanced.

## Measured results available for handoff

The recorded Linux/Spark run in `data/processed/ieee_cis_spark/manifest.json` contains the following evidence:

| Item | Result |
|---|---:|
| Required source size | 1,292.18 MB |
| Labeled training rows | 590,540 |
| Legitimate rows | 569,877 |
| Fraud rows | 20,663 |
| Fraud rate | 3.499% |
| Legitimate : fraud ratio | 27.58 : 1 |
| Train / validation / holdout | 412,956 / 88,490 / 89,094 |
| Split thresholds | `TransactionDT` 10,432,902 and 13,136,653 |

Decision Tree comparison from the recorded run:

| Model | Validation PR-AUC | Holdout PR-AUC | Holdout ROC-AUC | Holdout Recall | Holdout Precision | Holdout F1 |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 0.0205 | 0.0209 | 0.2368 | 0.1952 | 0.6530 | 0.3005 |
| Class weighted | 0.2781 | 0.2978 | 0.7090 | 0.6876 | 0.1332 | 0.2231 |
| Undersampled | 0.0256 | 0.0260 | 0.3824 | 0.4725 | 0.2468 | 0.3242 |

Interpretation for the handoff:

- The class-weighted model is the strongest candidate by validation and holdout PR-AUC.
- It detects substantially more fraud (`68.76%` holdout recall) but generates more alerts, so precision is lower (`13.32%`).
- The baseline is not suitable for fraud screening because its PR-AUC is close to the class-imbalance baseline.
- The undersampled model offers a simpler alternative with higher holdout F1 than the weighted model, but much lower PR-AUC.

These metrics are evidence for the Spark Decision Tree demonstration. Quân should rerun model selection if the feature set, threshold, or downstream model changes.

## Known limitations

- `TransactionDT` is relative time, not a real calendar timestamp.
- Identity coverage is expected to be substantially below 100%.
- The Decision Tree is a pipeline demonstration and not the final production model.
- Full Parquet export is supported in Docker/Linux; native Windows is limited to transformations and small reports.
- The measured results above were recorded before the final memory-safety configuration change; they should be treated as the current reference evidence, not as a claim that the latest Docker image was rerun after that change.
