# Model-Ready Data Contract

Phiên bản hiện tại:

- pipeline_version: `2.1.0`
- processing_version: `ieee-cis-preprocess-2.1.0`
- feature_schema_version: `ieee-cis-features-1.1.0`

Stable data `2.0.0` remains available until the staged `2.1.0` data and its
model candidate pass all promotion gates.

## 1. Mục đích

Tài liệu này định nghĩa contract downstream cho các dataset model-ready được sinh từ pipeline Spark IEEE-CIS. Đây là contract chuẩn để:

- train model trong `model/`
- verify artifact integrity
- hỗ trợ full-feature scoring
- bàn giao dataset cho backend/application

Project hiện dùng static batch learning và versioned retraining, không triển khai Continual Learning.

## 2. Output datasets

Base path:

`data/processed/ieee_cis_fraud_risk/model_ready/`

| Dataset | Path | Purpose | Label |
| --- | --- | --- | --- |
| train_original | `model_ready/train_original/` | training với distribution gốc theo thời gian | `isFraud` có |
| train_weighted | `model_ready/train_weighted/` | training với `class_weight` | `isFraud` có |
| train_balanced | `model_ready/train_balanced/` | training với legitimate undersampling deterministic | `isFraud` có |
| validation | `model_ready/validation/` | validation untouched | `isFraud` có |
| holdout | `model_ready/holdout/` | final evaluation untouched | `isFraud` có |
| kaggle_test | `model_ready/kaggle_test/` | unlabeled inference/export | `isFraud` không có |

## 3. Required columns

Mọi dataset model-ready phải giữ:

- `TransactionID`
- full feature columns theo `artifacts/preprocessing/feature_order.json`
- `split_name`
- `processing_version`
- `feature_schema_version`
- `generated_at`

Riêng:

- labeled datasets phải có `isFraud`
- `train_weighted` phải có `class_weight`
- `kaggle_test` không được có `isFraud`

## 4. Canonical feature order

Nguồn chuẩn:

- `data/processed/ieee_cis_fraud_risk/artifacts/preprocessing/feature_order.json`

Feature order phải được coi là authoritative cho:

- downstream training
- full-feature scoring
- schema verification

Không được tự sort alphabetically hoặc tự suy diễn order từ dataframe runtime.

## 5. Feature groups

### Time

- `TransactionDT`
- `transaction_day`
- `transaction_week`
- `transaction_hour`
- `transaction_day_of_week_proxy`
- `transaction_age_days`
- `is_night_transaction`

### Amount

- `TransactionAmt`
- `log_transaction_amount`
- `transaction_amount_capped`
- `amount_decimal`
- `amount_band`
- `high_amount_flag`
- `amount_outlier_flag`
- `amount_ratio_to_card_mean`
- `amount_deviation_from_card_mean`

### Missingness and presence

- `selected_missing_count`
- `selected_missing_ratio`
- `identity_missing_count`
- `identity_missing_ratio`
- `has_identity`
- `has_device_info`
- `has_p_email`
- `has_r_email`
- `has_distance`
- `has_address`
- `same_email_domain`

### Distance / numeric behavior

- `dist1`
- `dist2`
- selected `C*`
- selected `D*`

### Historical aggregates

- `prior_card_transaction_count`
- `prior_card_amount_sum`
- `prior_card_avg_amount`
- `prior_card_amount_stddev`
- `time_since_previous_card_transaction`
- `prior_email_transaction_count`
- `prior_email_amount_sum`
- `prior_email_avg_amount`
- `prior_device_transaction_count`
- `prior_device_amount_sum`
- `prior_device_avg_amount`

### Categorical

- `ProductCD`
- `card4`
- `card6`
- `DeviceType`
- `device_family`
- `M4`
- `amount_band`

## 6. Null policy

Numeric:

- median imputation fit trên chronological training split
- artifact tại `artifacts/preprocessing/numeric_medians.json`
- amount outlier/capping thresholds fit trên chronological training split
- artifact tại `artifacts/preprocessing/outlier_thresholds.json`

Categorical:

- missing -> `__MISSING__`
- unseen -> `__UNKNOWN__`
- category policy tại `artifacts/preprocessing/category_policy.json`

Không được refit imputer hoặc category handling trên validation, holdout hoặc kaggle_test.

Historical count/sum/average features are point-in-time: each row may use
transactions ordered before it by `(TransactionDT, TransactionID)`, but never
the current row, a future row, or any label.

## 7. Compatibility rules

- `processing_version` của input phải khớp artifact/model yêu cầu
- `feature_schema_version` phải khớp exact
- `class_weight` chỉ hợp lệ cho `train_weighted`
- `isFraud` không được xuất hiện trong `kaggle_test`
- metadata columns không được đưa vào feature vector nếu model không cần

## 8. Usage example

```python
import json
from pathlib import Path
import pyarrow.dataset as ds

root = Path("data/processed/ieee_cis_fraud_risk")
feature_order = json.loads((root / "artifacts/preprocessing/feature_order.json").read_text())["feature_columns"]
train = ds.dataset(str(root / "model_ready/train_weighted"), format="parquet").to_table().to_pandas()
X = train[feature_order]
y = train["isFraud"]
w = train["class_weight"]
```

## 9. Full-feature vs partial-demo scoring

- `full_feature`: input row đã theo đúng feature contract này
- `partial_demo`: input chỉ là subset từ UI/demo flow, không tương đương preprocessing lúc train

Không mô tả `partial_demo` là production-equivalent.
