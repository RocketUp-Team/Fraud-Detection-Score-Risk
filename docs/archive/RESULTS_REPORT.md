# IEEE-CIS Processing Results Report

Last reviewed: `2026-07-24`.

## Executive summary

The Spark preprocessing workflow successfully produced a recorded Linux run for the IEEE-CIS dataset and wrote its evidence to `data/processed/ieee_cis_spark/manifest.json`. The dataset is large enough for the Big Data requirement, the fraud class is strongly imbalanced, and class weighting materially improves fraud-ranking quality over the unweighted baseline.

## Dataset evidence

- Required source files: transaction and identity CSVs for train and test.
- Total required source size: `1,292.18 MB`.
- Labeled training rows: `590,540`.
- Legitimate transactions: `569,877`.
- Fraud transactions: `20,663`.
- Fraud rate: `3.499%`.
- Legitimate-to-fraud ratio: `27.58:1`.

This supports the project claim that IEEE-CIS is a wide, sparse and strongly imbalanced Big Data workload.

## Processing completed

- Explicit Spark CSV schemas for transaction and identity tables.
- `TransactionID` null and duplicate validation.
- Transaction left join identity with row-preservation audit.
- Test identity normalization from `id-xx` to `id_xx`.
- Distributed missingness and cardinality profiling.
- Spark SQL fraud-rate analysis by product, card, email, device and time.
- Chronological split using `TransactionDT`:
  - Train: `412,956` rows.
  - Validation: `88,490` rows.
  - Holdout: `89,094` rows.
  - Thresholds: `10,432,902` and `13,136,653`.
- Training-only aggregate features for card, email and device.
- Training-only median imputation.
- Original, weighted and controlled-undersampled training contracts.
- Decision Tree evaluation with PR-AUC, ROC-AUC, precision, recall, F1 and confusion-matrix counts.

## Model results

| Model | Validation PR-AUC | Holdout PR-AUC | Holdout ROC-AUC | Holdout Recall | Holdout Precision | Holdout F1 |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 0.0205 | 0.0209 | 0.2368 | 0.1952 | 0.6530 | 0.3005 |
| Class weighted | 0.2781 | 0.2978 | 0.7090 | 0.6876 | 0.1332 | 0.2231 |
| Undersampled | 0.0256 | 0.0260 | 0.3824 | 0.4725 | 0.2468 | 0.3242 |

## Presentation conclusion

The class-weighted Decision Tree is the best ranking candidate because it has the highest validation PR-AUC (`0.2781`) and holdout PR-AUC (`0.2978`). Its lower precision is an explicit operational tradeoff: the model catches more fraud but raises more alerts. The undersampled model has the highest holdout F1 among these three demonstrations, while the baseline is weak for fraud detection despite its higher precision at the default threshold.

## Handoff to Quân

Quân should start from:

```text
data/processed/ieee_cis_spark/model_ready/train_weighted
data/processed/ieee_cis_spark/model_ready/validation
data/processed/ieee_cis_spark/model_ready/holdout
```

Use `train_balanced` if the selected downstream algorithm cannot consume `class_weight`. Do not refit aggregate features or imputation on validation or holdout. Select the final threshold using validation only, then evaluate holdout once.

Full interface details are in [HANDOVER_TO_QUAN.md](HANDOVER_TO_QUAN.md).

## Evidence status

The values in this report are read from the recorded Spark manifest. The latest Docker image was not rerun after the final filename cleanup and memory-safety configuration, per the requested instruction not to rerun Docker. The next run should regenerate `manifest.json` and reports before final submission if reproducibility evidence from the final image is required.

## Handoff status

- Documentation is ready for the model workflow.
- The single notebook and Docker entrypoint use the neutral filenames documented in `README_DATA_PROCESSING_EDA.md`.
- The selective commit for this change contains documentation only; code, notebook, Docker and generated data changes remain outside that commit.
