# Model Training Review Report

**Ngày review:** 2026-07-29  
**Phạm vi:** data contract, training code, V1/V2 artifacts, V3 workflow, MLflow và serving compatibility  
**Audience:** technical/model engineering/backend integration  
**Kết luận:** **Needs revision** trước khi coi workflow là production-ready.

## 1. Technical summary

V2 là offline champion theo evidence hiện có. So với V1, V2 cải thiện cả bốn metric:

| Metric | V1 | V2 | Thay đổi tuyệt đối | Thay đổi tương đối |
|---|---:|---:|---:|---:|
| Validation ROC-AUC | 0.8877 | 0.8941 | +0.0064 | +0.72% |
| Validation PR-AUC | 0.4820 | 0.4925 | +0.0105 | +2.18% |
| Holdout ROC-AUC | 0.8684 | 0.8796 | +0.0112 | +1.29% |
| Holdout PR-AUC | 0.4298 | 0.4582 | +0.0283 | +6.59% |

Kết quả này chỉ chứng minh V2 tốt hơn V1 trên các split offline hiện có. Chưa đủ evidence để kết luận V2 tốt hơn trong production vì còn thiếu operating-point metrics, calibration evidence, serving smoke test và MLflow run history.

V3 đã có source code nhưng chưa có artifact V3 hoặc run MLflow thực tế. Không được báo cáo V3 như một kết quả đã train.

## 2. Executive findings

### 2.1 V2 cải thiện offline, nhưng comparison chưa controlled hoàn toàn

**Severity: Medium — confidence: High**

V1 có 53 features, V2 có 68 features và feature contract mới. Cải thiện là kết quả tổng hợp của feature contract, feature order, metadata filtering, training config và tuning. Không thể quy toàn bộ cải thiện cho hyperparameter.

Muốn đo nguyên nhân cần ablation study theo feature group hoặc train V1 trên cùng 68-column contract.

### 2.2 Holdout metric có trong JSON nhưng chưa tái lập được trong môi trường review

**Severity: High — confidence: High**

Metric V2 nằm trong:

- `model/artifacts/v2/training_metadata_v2.json`
- `model/artifacts/v2/model_comparison_v2.json`

Khi load `model/artifacts/v2/final_model_v2.joblib`, môi trường review báo:

```text
ModuleNotFoundError: No module named 'lightgbm'
```

Đây có thể là thiếu dependency local, nhưng cần xác nhận Docker/backend image load được artifact. Nếu không, backend có thể rơi về `_HeuristicScorer`, không phải fraud model thật.

### 2.3 MLflow integration chưa có run evidence

**Severity: High — confidence: High**

`model/artifacts/mlruns/` hiện chỉ có:

```text
0/meta.yaml
```

Chưa có run folders, params, metrics hoặc logged artifacts. Source đã có MLflow integration tại `model/src/fraud_model/tracking.py`, nhưng chưa thể xác nhận training history đã được ghi.

`model/pyproject.toml` có MLflow nhưng `model/uv.lock` chưa chứa MLflow. Dockerfile dùng `uv sync --frozen`, nên build reproducible có thể fail.

### 2.4 Threshold config chưa điều khiển decision thực tế

**Severity: High — confidence: High**

V3 sinh `review_threshold` và `reject_threshold`, nhưng backend vẫn classify theo fixed risk bands trong `backend/src/fraud_backend/risk.py`. Threshold config hiện chỉ được trả ra từ model, chưa điều khiển `approve/review/reject`.

### 2.5 Reject threshold là heuristic tùy ý

**Severity: High — confidence: High**

`model/src/fraud_model/evaluation.py` đang dùng:

```python
reject_threshold = review_threshold + 0.20
```

Giá trị này chưa dựa trên validation cost, precision target hoặc review capacity nên chưa được coi là production policy.

### 2.6 Documentation mâu thuẫn về promotion

**Severity: Medium — confidence: High**

Một số phần nói V2 là serving default, phần khác vẫn nói V1 là default hoặc V2 chưa đủ evidence để promote. Các file cần đồng bộ:

- `model/README.md`
- `docs/AN_MODEL_V1_V2_COMPARISON_REPORT.md`
- `model/src/fraud_model/score.py`
- `model/src/fraud_model/tune_and_explain.py`

Trạng thái an toàn nên là: **V2 là offline champion; promotion chỉ hoàn tất sau compatibility và policy validation.**

## 3. Scope, data và metric definitions

### 3.1 Dataset contract

Training đọc Parquet tại `data/processed/ieee_cis_fraud_risk/model_ready/`.

| Dataset | Mục đích | Label | Sampling |
|---|---|---|---|
| `train_original` | baseline distribution | Có | original |
| `train_weighted` | training chính | Có | original + `class_weight` |
| `train_balanced` | comparison | Có | deterministic undersampling |
| `validation` | model/parameter/policy selection | Có | untouched |
| `holdout` | final evaluation | Có | untouched |
| `kaggle_test` | inference/export | Không | untouched |

Evidence trong data contract:

| Dataset | Rows | Fraud | Legitimate | Fraud rate |
|---|---:|---:|---:|---:|
| `train_original` | 412,956 | 14,522 | 398,434 | 3.5166% |
| `train_weighted` | 412,956 | 14,522 | 398,434 | 3.5166% |
| `train_balanced` | 58,394 | 14,522 | 43,872 | 24.8690% |
| `validation` | 88,490 | 3,036 | 85,454 | 3.4309% |
| `holdout` | 89,094 | 3,105 | 85,989 | 3.4851% |

Pipeline dùng chronological split theo `TransactionDT`. Validation và holdout không resample; preprocessing lookups được fit từ training data rồi apply forward. Đây là thiết kế đúng cho fraud detection theo tương lai.

Giới hạn hiện tại: model selection chỉ dùng một validation window, chưa có temporal cross-validation.

### 3.2 Feature contract

Canonical feature order nằm tại:

```text
data/processed/ieee_cis_fraud_risk/artifacts/preprocessing/feature_order.json
```

Các cột không được dùng làm feature:

```text
TransactionID
isFraud
class_weight
split_name
processing_version
feature_schema_version
generated_at
```

`features.py` chọn canonical columns, kiểm tra missing columns và giữ nguyên order. Đây là một control tốt vì lỗi trước đó đã cho phép `split_name` lọt vào vector và gây lỗi string-to-float.

## 4. Methodology review

### 4.1 Training flow

```text
load train_weighted
→ fit categorical indexer on train
→ transform validation/holdout
→ convert to pandas
→ compare models on validation
→ tune selected model on validation
→ calibrate and select threshold
→ evaluate holdout once
→ save artifact
```

Luồng này đúng về mặt leakage control nếu holdout chỉ được gọi ở stage cuối.

### 4.2 Model comparison

V1/V2 validation comparison:

| Model | V1 PR-AUC | V2 PR-AUC |
|---|---:|---:|
| Logistic Regression | 0.2522 | 0.2518 |
| LightGBM | 0.4739 | 0.4770 |
| XGBoost | 0.4285 | 0.4538 |
| CatBoost | 0.4083 | 0.4298 |

LightGBM đứng đầu validation ở cả hai version. Đây là evidence hợp lý để chọn LightGBM, nhưng bảng này không cho biết precision/recall tại threshold thực tế.

### 4.3 Class imbalance

Dùng `train_weighted` với `class_weight` làm `sample_weight` là lựa chọn hợp lý: giữ toàn bộ legitimate records và giữ validation/holdout ở prevalence thật.

`train_balanced` phù hợp làm experiment phụ. Vì prevalence train khác production, model balanced cần calibration trước khi diễn giải probability.

### 4.4 Hyperparameter tuning

Grid V2 còn nhỏ:

```text
n_estimators: 200, 400
max_depth: 4, 6
learning_rate: 0.05, 0.1
```

Grid này reproducible và dễ chạy, nhưng chưa phải search rộng. Fine-tuning thêm chỉ nên làm sau khi có threshold/calibration evidence để tránh tối ưu sai mục tiêu hoặc overfit validation.

### 4.5 Calibration và threshold

V3 bổ sung Isotonic calibration và threshold scan từ `0.05` đến `0.95`. Đây là cải thiện tốt, nhưng còn ba rủi ro:

1. Model được chọn trên toàn validation trước khi calibration.
2. Chưa có một policy split độc lập cho calibration và threshold cùng lúc.
3. Reject threshold vẫn là heuristic.

Production nên tách theo thời gian:

```text
model-selection validation
→ calibration validation
→ threshold validation
→ untouched holdout
```

## 5. Artifact và serving review

### 5.1 V2 artifacts

Các file V2 đang có:

```text
model/artifacts/v2/baseline_logreg_v2.joblib
model/artifacts/v2/final_model_v2.joblib
model/artifacts/v2/model_comparison_v2.json
model/artifacts/v2/training_metadata_v2.json
```

Metadata có model version, best model, validation/holdout metrics và feature count. Tuy nhiên artifact paths chứa `/app/artifacts`, là container path, không portable trong mọi môi trường.

Artifacts nằm trong thư mục Git-ignored. Reproducibility cần thêm:

- SHA-256 checksum;
- model version;
- processing version;
- feature schema version;
- training config;
- MLflow run ID;
- registry location.

### 5.2 Serving compatibility

Serving đã hỗ trợ:

- versioned artifact paths;
- rollback bằng `FRAUD_MODEL_SERVING_VERSION`;
- categorical mapping không cần Spark;
- missing/unseen categorical values;
- SHAP cho tree model.

Rủi ro còn lại:

- SHAP giải thích raw model output trong khi probability trả về có thể đã calibrated;
- backend chưa dùng threshold config;
- metadata version chưa được lưu đồng nhất trong V2 artifact;
- fallback heuristic có thể che giấu lỗi thiếu model dependency.

### 5.3 MLflow status

Observed state:

```text
model/artifacts/mlruns/0/meta.yaml exists
run artifacts/metrics do not exist
```

Không nên claim training history đã đầy đủ cho đến khi thấy các run:

```text
baseline
compare
tune_validation
threshold_and_calibration
holdout_final
```

Filesystem MLflow backend cũng phát warning deprecated. Nên chuyển local backend sang SQLite:

```text
sqlite:///model/artifacts/mlflow.db
```

và lưu artifact riêng tại `model/artifacts/mlflow-artifacts/`.

## 6. Severity matrix

| ID | Finding | Severity | Confidence | Impact |
|---|---|---|---|---|
| Q1 | MLflow chưa có completed run evidence | High | High | Block reproducibility claim |
| Q2 | `uv.lock` chưa có MLflow | High | High | Block frozen Docker build |
| Q3 | Threshold config chưa dùng bởi backend | High | High | Block policy promotion |
| Q4 | Reject threshold là `review + 0.20` | High | High | Block threshold claim |
| Q5 | Thiếu precision/recall/F1/FP/FN operating metrics | High | High | Block fraud operations claim |
| Q6 | Artifact local không load được nếu thiếu LightGBM | High | High | Block serving validation |
| Q7 | V1/V2 feature sets khác nhau | Medium | High | Limit attribution |
| Q8 | Documentation mâu thuẫn promotion state | Medium | High | Release confusion |
| Q9 | Toàn bộ dataset chuyển qua `toPandas()` | Medium | High | Driver memory risk |
| Q10 | SHAP raw output khác calibrated output | Medium | Medium | Explanation mismatch |
| Q11 | Thiếu tests cho threshold/calibration/MLflow | Medium | High | Regression risk |
| Q12 | Artifacts Git-ignored, chưa có registry/checksum | Medium | High | Handover risk |

## 7. Remediation plan

### Phase 1 — Reproducibility

1. Chạy `uv lock` sau khi thêm MLflow.
2. Build Docker với `uv sync --frozen`.
3. Verify imports của LightGBM, XGBoost, CatBoost, SHAP và MLflow trong container.
4. Chạy V3 workflow.
5. Xác nhận năm MLflow runs và artifact paths.

### Phase 2 — Complete evidence

Sinh các báo cáo:

- validation metrics;
- threshold analysis;
- Brier/calibration report;
- precision, recall, F1;
- TP/TN/FP/FN;
- false-positive analysis;
- false-negative analysis;
- feature importance/SHAP;
- inference latency;
- artifact checksum.

### Phase 3 — Fix serving policy

Chọn policy rõ ràng:

```text
probability < review_threshold → approve
review_threshold ≤ probability < reject_threshold → review
probability ≥ reject_threshold → reject
```

Lưu policy trong `threshold_config_v3.json`, load tại backend startup, expose qua `/meta`, và test boundary values. Không đổi live V2 policy trước shadow validation.

### Phase 4 — Promotion gate

V3 chỉ được promote nếu:

- holdout PR-AUC >= V2 `0.4582`;
- recall tại operating point không regress;
- precision phù hợp review capacity;
- calibration đạt tiêu chí Brier/calibration curve;
- full-feature serving smoke test thành công;
- backend không silently fallback heuristic;
- MLflow run ID và checksum được lưu;
- rollback V2 đã test.

## 8. Automated test recommendations

1. Canonical feature order và forbidden metadata columns.
2. Duplicate `TransactionID` rejection.
3. `kaggle_test` không có `isFraud`.
4. Train-only categorical mapping.
5. Threshold boundary tại đúng review/reject values.
6. Calibrated probability trong `[0, 1]`.
7. Backend decision dùng threshold config.
8. V3 artifact có model, calibrator, thresholds và metadata.
9. MLflow run có required params/metrics.
10. Thiếu dependency/model khiến health check fail rõ ràng, không silently score heuristic.

## 9. Limitations and open questions

Chưa thể xác định từ repository:

- business cost của false positive và false negative;
- review capacity mỗi ngày;
- precision/recall operating point được chấp nhận;
- calibration dùng cho risk bands hay chỉ reporting;
- drift sau holdout window;
- feature aggregates có sẵn đúng latency khi serving hay không;
- artifact có được lưu trong registry ngoài thư mục Git-ignored hay không.

Các quyết định này cần được chốt trước khi threshold được coi là business-approved.

## 10. Final recommendation

Giữ V2 là offline champion và rollback-safe candidate. Không claim V3 cải thiện cho đến khi có full Docker run, MLflow history và holdout report.

Immediate blockers không phải train thêm thật nhiều model, mà là:

1. reproducible environment;
2. auditable MLflow runs;
3. operating-point metrics;
4. threshold policy nối vào backend;
5. serving smoke test không fallback heuristic.

Sau khi hoàn tất các controls này, fine-tuning LightGBM chỉ đáng làm nếu cải thiện PR-AUC hoặc recall/precision operating point mà không làm tăng validation-to-holdout instability.

## Source inventory

- `data/processed/ieee_cis_fraud_risk/MODEL_READY_DATA_CONTRACT.md`
- `data/processed/ieee_cis_fraud_risk/reports/split_summary.csv`
- `data/processed/ieee_cis_fraud_risk/reports/imbalance_comparison.csv`
- `data/processed/ieee_cis_fraud_risk/reports/decision_tree_metrics.json`
- `model/artifacts/v2/model_comparison_v2.json`
- `model/artifacts/v2/training_metadata_v2.json`
- `model/src/fraud_model/features.py`
- `model/src/fraud_model/train_compare.py`
- `model/src/fraud_model/tune_and_explain.py`
- `model/src/fraud_model/threshold_analysis.py`
- `model/src/fraud_model/evaluate_holdout.py`
- `model/src/fraud_model/tracking.py`
- `backend/src/fraud_backend/risk.py`
- `backend/src/fraud_backend/scoring.py`

**Evidence date:** 2026-07-29. Claims based on artifacts unavailable or not loadable in the review environment are explicitly marked as unverified.
