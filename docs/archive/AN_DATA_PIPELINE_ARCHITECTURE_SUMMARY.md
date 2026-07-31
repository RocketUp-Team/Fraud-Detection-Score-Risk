# An Data Pipeline Architecture Summary

## 1. Dataset

Pipeline của An xử lý bộ IEEE-CIS Fraud Detection với bốn file chính:

- `train_transaction.csv`: 590,540 rows, 394 columns, 651.69 MB
- `train_identity.csv`: 144,233 rows, 41 columns, 25.30 MB
- `test_transaction.csv`: 506,691 rows, 393 columns, 584.79 MB
- `test_identity.csv`: 141,907 rows, 41 columns, 24.60 MB

Theo `data/processed/ieee_cis_fraud_risk/reports/dataset_inventory.csv`, tổng dữ liệu nguồn vượt 1.28 GB. `isFraud` chỉ có ở train transaction. `TransactionID` là join key giữa transaction và identity. `TransactionDT` được dùng như relative time để chia dữ liệu theo thứ tự thời gian.

## 2. Architecture

Kiến trúc dữ liệu được tổ chức theo nhiều layer:

- Source Layer: raw IEEE-CIS CSV
- Validation Layer: required-file checks, size checks, schema checks
- Curated Layer: transaction–identity join, cleanup, typed curated data
- Analytics Layer: EDA reports và figures từ Spark aggregations
- Feature Layer: time, amount, missingness, presence, entity và historical aggregate features
- Model-Ready Layer: six Parquet datasets cho downstream training
- Handover Layer: manifest, schema artifacts, preprocessing artifacts, reports

Điểm quan trọng là model team đọc trực tiếp `model_ready/*` thay vì tự join lại dữ liệu thô.

## 3. Pipeline

Luồng xử lý end-to-end:

Raw CSV  
→ Spark ingestion với explicit schema  
→ identity-column normalization  
→ left join theo `TransactionID`  
→ data-quality audit  
→ distributed EDA  
→ cleaning và categorical normalization  
→ chronological split 70/15/15 theo `TransactionDT`  
→ train-only fit cho medians, outlier thresholds và historical aggregates  
→ feature engineering  
→ imbalance variants  
→ model-ready Parquet export

Các output chính:

- `curated/`
- `splits/`
- `feature_store/`
- `model_ready/`
- `artifacts/preprocessing/`
- `artifacts/schema/`
- `reports/`

## 4. Key Methods

Các phương pháp cốt lõi:

- Apache Spark DataFrame và Spark SQL cho ingestion, join, EDA và feature engineering
- explicit schema thay vì infer schema mù
- `id-01 -> id_01` để đồng bộ identity schema train/test
- left join để giữ transaction grain
- missingness profiling theo Low / Medium / High / Extreme
- median imputation train-only cho numeric
- `__MISSING__` / `__UNKNOWN__` policy cho categorical
- `approxQuantile` + IQR cho outlier profiling
- chronological split để tránh temporal leakage
- train-only historical aggregates cho card, email, device
- original / weighted / balanced train variants cho class imbalance

## 5. Main Outputs

Các output downstream quan trọng nhất là:

- `model_ready/train_original`
- `model_ready/train_weighted`
- `model_ready/train_balanced`
- `model_ready/validation`
- `model_ready/holdout`
- `model_ready/kaggle_test`

Theo artifact hiện tại:

- feature columns: 68
- numeric features: 61
- categorical features: 7
- `train_weighted` có thêm `class_weight`

Các artifact hỗ trợ:

- `feature_order.json`
- `selected_features.json`
- `numeric_medians.json`
- `outlier_thresholds.json`
- `split_thresholds.json`
- `model_ready_schema.json`

## 6. Contribution

Phần việc của An không chỉ là EDA. Giá trị chính nằm ở việc chuyển raw CSV thành reusable model-ready Parquet có contract rõ ràng. Điều này giúp downstream model training:

- không phải join lại transaction và identity;
- không phải split lại dữ liệu;
- không phải fit lại missing-value strategy;
- không phải tính lại historical aggregates;
- không phải resample validation/holdout.

## 7. BDA501 Mapping

Phần data pipeline đáp ứng trực tiếp các yêu cầu BDA501:

- dataset lớn hơn 500 MB;
- Apache Spark dùng cho raw-data processing;
- có ingestion, cleaning, descriptive analysis;
- có filtering, aggregation và Spark SQL;
- có MLlib Decision Tree baseline;
- có reusable output qua Parquet và artifact handover.

Report đầy đủ nằm tại `docs/AN_BDA501_DATA_ARCHITECTURE_AND_PIPELINE_REPORT.md`.
