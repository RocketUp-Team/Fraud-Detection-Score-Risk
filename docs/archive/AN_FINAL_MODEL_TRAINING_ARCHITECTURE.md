# Final Model Training Architecture

**Classification:** HYBRID WITH EXPLICIT LEGEND

## As-Built lifecycle

Code hiện có các stage:

1. `validate_data`: validate sáu dataset, feature order, versions và metadata.
2. `train_baseline`: Logistic Regression trên weighted training.
3. `train_compare`: Logistic Regression, LightGBM, XGBoost và CatBoost.
4. `tune_and_explain`: tune selected family và ghi final artifact.
5. `threshold_analysis`: calibrator và threshold configuration.
6. `evaluate_holdout`: đọc holdout sau các quyết định trước đó.
7. `package_candidate`: bundle validation, policy-window smoke score và checksum.
8. `promotion_gate`: ghi gate result; `automatic_promotion` không phải serving update.

`scripts/train_model.ps1` gọi đầy đủ package/gate; `scripts/train_model.sh` hiện không tương đương hoàn toàn vì dừng ở `evaluate_holdout`.

## Temporal and leakage contract

`split_validation_windows()` chia validation thành selection, calibration và policy. Selection chọn family/hyperparameters; calibration fit calibrator; policy chọn threshold; holdout chỉ dùng final evaluation. Nếu đã mở holdout mà cần cải thiện, phải đóng candidate và tạo version mới.

Historical features trong Spark được order theo `TransactionDT, TransactionID` và history window kết thúc ở previous row. Không được hiểu là aggregate toàn dataset trước split.

## Spark/Python boundary

Spark tạo/đọc Parquet. `.toPandas()` là handover vào single-node Python ML. Vì vậy không mô tả LightGBM/XGBoost/CatBoost là Spark-distributed training.

## Bundle and lineage

Bundle có thể chứa estimator, category mappings, feature columns, processing/schema versions, calibrator, threshold config, metrics, MLflow run ID và checksum. Nhưng chỉ gọi là immutable release khi có manifest/checksum và runtime load evidence cùng snapshot.

## Target changes

- model bundle và policy bundle tách riêng;
- registry/release store là serving authority;
- API trả `model_version`, `calibration_version`, `policy_version`;
- holdout reuse được chặn bằng candidate state;
- cân nhắc distributed-compatible training khi `.toPandas()` không còn phù hợp.
