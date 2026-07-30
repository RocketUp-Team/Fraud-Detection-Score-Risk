# Data Pipeline & Model Training Implementation Plan

**Thời gian:** 10 ngày làm việc  
**Owners:** An — Data Pipeline; Quân — Model Training  
**Phương pháp:** refactor tăng dần, giữ V2 làm serving champion  
**Candidate mục tiêu:** data processing `2.1.0`, feature semantics `1.1.0`, model `0.0.3`

## 1. Mục tiêu

Kế hoạch này chuẩn hóa hai luồng offline của hệ thống:

```text
IEEE-CIS raw CSV
→ Spark data pipeline
→ versioned model-ready Parquet
→ Spark-assisted model training
→ calibrated candidate bundle
→ promotion review
```

Phạm vi gồm Data Pipeline và Model Training. Backend, frontend, security và
production monitoring không nằm trong đợt triển khai này.

Các nguyên tắc bắt buộc:

- không ghi đè model V2 hoặc stable processed data trước khi candidate pass;
- giữ sáu model-ready dataset và canonical feature order 68 cột;
- mọi statistic học từ dữ liệu phải fit trên chronological training window;
- validation được chia theo thời gian thành selection/calibration/policy;
- holdout chỉ được đọc sau khi model, calibrator và threshold policy đã freeze;
- candidate mới luôn ở trạng thái review, không tự đổi serving version.

## 2. Architecture mục tiêu

### 2.1 Data Pipeline

```text
source validation
→ typed ingestion
→ transaction/identity join
→ stateless cleaning
→ chronological split
→ train-only fitted artifacts
→ point-in-time historical features
→ imbalance variants
→ model-ready export
→ contract verification
→ atomic manifest finalization
```

Contract tương thích được giữ cho:

- `train_original`
- `train_weighted`
- `train_balanced`
- `validation`
- `holdout`
- `kaggle_test`

Candidate data phải được ghi vào staging output thông qua `--output-dir`.
Stable output chỉ được thay sau khi data verifier và model promotion gates đều
pass.

### 2.2 Model Training

```text
data contract gate
→ train-fitted categorical mapping
→ baseline and candidate comparison
→ tuning on selection window
→ isotonic calibration on calibration window
→ threshold selection on policy window
→ one-time holdout evaluation
→ bundle/checksum/MLflow lineage
→ promotion review
```

Validation được chia theo `TransactionDT`:

- 50% đầu: model selection;
- 25% tiếp theo: calibration;
- 25% cuối: policy/threshold selection.

Spark local và Spark standalone cluster đều dùng version `3.5.1`. Driver và
worker phải nhìn thấy processed data tại cùng absolute container path.

## 3. Lịch 10 ngày

| Ngày | An — Data Pipeline | Quân — Model Training | Definition of Done |
| --- | --- | --- | --- |
| 1 | Lưu baseline manifest, verifier và preprocessing versions | Lưu V2 metrics, artifact paths và MLflow evidence | Có baseline/rollback evidence |
| 2 | Tách orchestration/config khỏi Spark implementation | Đồng bộ PySpark/Spark 3.5.1 và shared mounts | Local/cluster đọc cùng Parquet |
| 3 | Split trước outlier/imputer fit; config authoritative | Thêm configurable data root; dùng một train-fitted category mapping | Không refit trên later windows |
| 4 | Point-in-time card/email/device histories | Chia validation 50/25/25 và thêm temporal assertions | Không overlap/future leakage |
| 5 | Export staging, verifier và atomic manifest | Chạy contract tests trên candidate data | Data candidate ready |
| 6 | So sánh schema/distribution với 2.0.0 | Baseline và candidate comparison | Chọn model family/variant |
| 7 | Điều tra data regression | Tune và freeze candidate | Không thay params sau freeze |
| 8 | Cung cấp feature evidence | Calibration, policy selection, one-time holdout | Có full operating metrics |
| 9 | Hoàn thiện handover/version docs | Bundle, checksum, MLflow lineage, mode smoke tests | Candidate ở trạng thái review |
| 10 | Chốt data release evidence | Chạy promotion gate và ghi decision | `eligible_for_review` hoặc `not_promoted` |

## 4. Interfaces

### 4.1 Preprocessing

Entry point được giữ:

```powershell
python -m pipeline.fraud_risk_data_pipeline `
  --config config/pipeline_config.yaml `
  --output-dir data/processed/candidates/ieee_cis_fraud_risk_2_1_0
```

`pipeline_config.yaml` là nguồn chuẩn cho split ratios, outlier approximation,
imbalance ratio, seed và Spark runtime.

### 4.2 Training

```powershell
scripts/train_model.ps1 `
  -Mode cluster `
  -TrainingVersion 0.0.3 `
  -DataRoot data/processed/candidates/ieee_cis_fraud_risk_2_1_0
```

Environment tương ứng:

- `FRAUD_MODEL_TRAINING_VERSION`
- `FRAUD_MODEL_DATA_ROOT`
- `FRAUD_SPARK_ARROW_ENABLED`
- `SPARK_MASTER_URL`
- `MLFLOW_EXPERIMENT`

Cluster failure phải làm run fail rõ ràng; workflow không âm thầm chuyển mode
trong cùng training run.

### 4.3 Candidate bundle

Candidate directory phải có:

```text
final_model_<version>.joblib
training_metadata_<version>.json
threshold_config_<version>.json
validation_metrics_<version>.csv
holdout_metrics_<version>.csv
threshold_analysis_<version>.csv
candidate_manifest_<version>.json
checksum_<version>.sha256
promotion_decision_<version>.json
```

## 5. Quality gates

### Data gates

- source key/join audits pass;
- split order đúng và không overlap;
- outlier/median/category artifacts chỉ phụ thuộc train;
- point-in-time histories loại current/future event;
- sáu dataset giữ label/weight/schema rules;
- manifest và verifier có cùng terminal status;
- failed staging run không thay stable output.

### Model gates

- canonical order và processing/schema versions khớp exact;
- cùng category mapping được dùng cho mọi later window;
- tuning/calibration/policy/holdout dùng đúng temporal window;
- artifact load và score smoke test pass;
- MLflow run ID và SHA-256 tồn tại;
- probability và calibrated probability nằm trong `[0, 1]`.

### Promotion gates

- holdout PR-AUC `>= 0.4582`;
- holdout ROC-AUC `>= 0.8746`;
- precision tại review threshold `>= 0.30`;
- calibrated Brier score không xấu hơn raw Brier score;
- contract, checksum và runtime smoke tests pass.

Nếu một gate fail, candidate được ghi `not_promoted`; V2 và stable data alias
không thay đổi.

## 6. Progress checklist

- [x] Baseline và rollback evidence
- [x] Data pipeline config/refactor
- [x] Leakage-safe fitted artifacts
- [x] Point-in-time historical features
- [x] Candidate data full run và verifier
- [x] Spark local/cluster compatibility
- [x] Temporal validation 50/25/25
- [x] Candidate comparison và tuning
- [x] Calibration, policy và holdout
- [x] Bundle/checksum/MLflow lineage
- [x] Promotion decision và handover

## 7. Kết quả triển khai

Hoàn tất ngày 31/07/2026:

- candidate data `ieee_cis_fraud_risk_2_1_0` có đủ sáu dataset, 68 features
  theo đúng canonical order và verifier pass toàn bộ 94 checks;
- local Docker training và Spark standalone 3.5.1 contract smoke test đều
  đọc thành công cùng candidate Parquet;
- model candidate `0.0.3` là CatBoost train trên balanced dataset, có
  validation PR-AUC `0.5750`;
- calibration isotonic giảm policy Brier score từ `0.0461` xuống `0.0238`;
- one-time holdout đạt ROC-AUC `0.8771`, PR-AUC `0.4342`, precision `0.3730`
  và recall `0.5221` tại review threshold `0.14`;
- promotion decision là `not_promoted` vì PR-AUC thấp hơn V2 reference
  `0.4582`; serving V2 và stable processed data không thay đổi.
