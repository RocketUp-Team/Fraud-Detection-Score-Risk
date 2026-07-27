# Static Validation Report

Ngày chạy: 2026-07-27

## Phạm vi

Static validation tập trung vào:

- Python compile
- YAML/JSON parse
- Docker Compose config validation
- contract file presence
- leakage-pattern search
- hard-coded path search
- split/feature/report contract inspection

## Kết quả chính

### 1. Python compile

Đã compile thành công:

- `data/ieee_cis/pipeline/ieee_cis_preprocess.py`
- `pipeline/fraud_risk_data_pipeline.py`
- `pipeline/verify_processed_data.py`
- `pipeline/processed_contract.py`
- `pipeline/contract_utils.py`
- `model/src/fraud_model/score.py`
- `backend/src/fraud_backend/{main,schemas,service,scoring}.py`

Trạng thái: Pass

### 2. YAML / JSON parse

- `config/pipeline_config.yaml`: parse thành công
- `docker-compose.preprocessing.yml`: parse thành công
- repository template `manifest.json`: valid JSON sau update version
- historical processed manifest: ban đầu invalid JSON, đã được thay thế bằng regenerated manifest hợp lệ

Trạng thái: Pass sau remediation

### 3. Docker Compose config

Lệnh:

```powershell
docker compose -f docker-compose.preprocessing.yml config -q
```

Kết quả:

- cấu hình compose hợp lệ
- có warning truy cập `C:\Users\dan13\.docker\config.json`
- warning này không làm invalid compose file

Trạng thái: Pass with environment warning

### 4. Leakage-pattern search

Đã search các pattern:

- `randomSplit`
- `train_test_split`
- `setCheckpointDir`
- `predict_proba`
- `TransactionDT`
- `SparkSession.builder`
- `.toPandas(`

Kết quả:

- không thấy `randomSplit` trong main preprocessing pipeline
- không thấy `train_test_split` trong main preprocessing pipeline
- chronological split dựa trên `TransactionDT`
- `.toPandas()` tồn tại nhưng dùng cho report nhỏ / plotting / export nhỏ, không collect raw full dataset
- aggregate historical features được fit từ train-only path theo code hiện tại

### 5. Hard-coded paths

Phát hiện:

- `data/ieee_cis/pipeline/ieee_cis_preprocess.py` vẫn giữ `WINDOWS_PROJECT_ROOT` và `WINDOWS_RAW_DATA_DIR`
- đây hiện là fallback-only, không còn là required path
- notebook helper `data/ieee_cis/pipeline/notebook_ieee_cis_data_processing_eda.py` vẫn chứa Windows path cũ

Mức độ:

- pipeline runtime chính: Medium, đã giảm đáng kể vì hỗ trợ config/env/CLI/Docker
- notebook helper cũ: Low

### 6. Contract integrity

Đã thêm hoặc xác nhận:

- `artifacts/preprocessing/feature_order.json`
- `artifacts/preprocessing/selected_features.json`
- `artifacts/preprocessing/numeric_medians.json`
- `artifacts/preprocessing/category_policy.json`
- `artifacts/preprocessing/outlier_thresholds.json`
- `artifacts/preprocessing/split_thresholds.json`
- `artifacts/preprocessing/imbalance_config.json`
- `artifacts/schema/*.json`

### 7. Docker build context

Vấn đề ban đầu:

- `.dockerignore` loại `data/` và `*.ipynb`
- `docker/Dockerfile.preprocessing` lại `COPY` các path bị exclude

Fix:

- thêm exceptions trong `.dockerignore` cho:
  - `data/ieee_cis/pipeline/ieee_cis_preprocess.py`
  - `ieee_cis_fraud_risk_data_pipeline.ipynb`

### 8. Backend / serving contract

Đã thêm metadata contract tối thiểu:

- `processing_version`
- `feature_schema_version`
- `required_features`
- `optional_features`
- `defaultable_features`
- `scoring_mode`

Áp dụng tại:

- `model/src/fraud_model/score.py`
- `backend/src/fraud_backend/schemas.py`
- `backend/src/fraud_backend/service.py`
- `backend/src/fraud_backend/main.py`
- `backend/src/fraud_backend/scoring.py`

## Tổng kết

| Check | Status | Notes |
| --- | --- | --- |
| Python compile | Pass | Sau các bản vá helper/report/contract |
| YAML parse | Pass | `pipeline_config.yaml`, compose |
| JSON parse | Pass | manifest mới valid |
| Docker Compose config | Pass with warning | warning Docker user config |
| Hard-coded path scan | Partial | fallback Windows path vẫn còn |
| Leakage pattern scan | Pass | không thấy random split trong main pipeline |
| Contract artifact presence | Pass | đủ artifacts chính |
| Docker build context scan | Pass after fix | `.dockerignore` đã chỉnh |
