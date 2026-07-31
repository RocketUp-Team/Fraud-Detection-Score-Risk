# Báo cáo so sánh Model V1 và Model V2 — HISTORICAL EVIDENCE

> Current architecture interpretation is maintained in
> [`AN_FINAL_ARCHITECTURE_REVIEW.md`](AN_FINAL_ARCHITECTURE_REVIEW.md). Metrics
> here are not runtime-verified unless a matching versioned artifact and one
> official evidence snapshot are available.

## 1. Technical summary

Model V2 cho kết quả tốt hơn model V1 trên cả validation và holdout theo hai metric chính của bài toán fraud detection là ROC-AUC và PR-AUC. Cải thiện rõ nhất xuất hiện ở holdout PR-AUC, từ `0.4298` lên `0.4582`, tăng `0.0283` điểm tuyệt đối, tương đương khoảng `6.59%` tương đối.

V1 và V2 đều sử dụng LightGBM làm final model. Vì vậy, kết quả cải thiện của V2 không đến từ việc đổi sang model family khác, mà chủ yếu liên quan đến feature contract, số lượng feature và quy trình training được chuẩn hóa lại.

V2 là software serving default sau khi vượt V1 trên holdout PR-AUC; V1 vẫn được
giữ làm rollback target. Đây là lựa chọn mặc định của code cho môi trường
demo, không phải bằng chứng về một quyết định production promotion đã được phê
duyệt. Prediction compatibility, threshold/risk-score behavior và downstream
consumer vẫn cần được kiểm soát.

## 2. Scope and evidence

Báo cáo này chỉ so sánh model artifacts V1/V2 trong thư mục `model/artifacts/`. Không đánh giá backend, frontend, API hay deployment.

Các nguồn đã kiểm tra:

| Source | Purpose |
|---|---|
| `model/artifacts/final_model.joblib` | Final model V1 đang được giữ làm legacy/serving artifact |
| `model/artifacts/model_comparison.json` | Kết quả comparison validation của V1 |
| `model/artifacts/v2/final_model_v2.joblib` | Final model V2 |
| `model/artifacts/v2/model_comparison_v2.json` | Kết quả comparison validation của V2 |
| `model/artifacts/v2/training_metadata_v2.json` | Version, feature count và metric final V2 |
| `model/src/fraud_model/features.py` | Chuẩn hóa feature vector và loại metadata columns |
| `model/src/fraud_model/train_compare.py` | So sánh các model trên validation |
| `model/src/fraud_model/tune_and_explain.py` | Chọn tham số trên validation và đánh giá holdout một lần |
| `model/src/fraud_model/config.py` | Quy ước artifact path và model version |

Lưu ý: repository hiện không có `model/artifacts/v1/final_model_v1.joblib`; V1 được lưu ở tên legacy `model/artifacts/final_model.joblib`. Code serving có fallback để đọc artifact legacy này khi phục vụ V1.

## 3. Comparison basis

So sánh chính sử dụng metric được lưu trong final model artifacts:

- `Validation`: dùng để chọn model và tuning.
- `Holdout`: chỉ dùng để đánh giá final model sau khi đã chốt lựa chọn trên validation.
- `ROC-AUC`: khả năng xếp hạng fraud so với legitimate trên nhiều threshold.
- `PR-AUC`: phù hợp hơn khi fraud class bị mất cân bằng mạnh vì tập trung vào precision/recall của positive class.

Đây là so sánh descriptive/predictive giữa hai lần training. Kết quả không chứng minh rằng V2 luôn tốt hơn trên dữ liệu tương lai hoặc trong production.

## 4. Final model results

### 4.1 Overall metrics

| Metric | V1 | V2 | Absolute change | Relative change |
|---|---:|---:|---:|---:|
| Validation ROC-AUC | 0.8877 | 0.8941 | +0.0064 | +0.72% |
| Validation PR-AUC | 0.4820 | 0.4925 | +0.0105 | +2.18% |
| Holdout ROC-AUC | 0.8684 | 0.8796 | +0.0112 | +1.29% |
| Holdout PR-AUC | 0.4298 | 0.4582 | +0.0283 | +6.59% |

### 4.2 Interpretation

V2 cải thiện trên cả bốn metric được dùng trong so sánh. Holdout PR-AUC tăng mạnh hơn validation PR-AUC, cho thấy V2 có khả năng xếp hạng positive class tốt hơn trên holdout theo artifact hiện tại.

Tuy nhiên, không nên diễn giải mức tăng này thành số lượng fraud được phát hiện tăng cùng tỷ lệ. ROC-AUC và PR-AUC không trực tiếp cho biết confusion matrix tại một threshold cụ thể. Muốn quyết định promote model, cần đánh giá thêm precision, recall, false positives và false negatives tại threshold phục vụ risk score.

## 5. Model comparison on validation

Bảng dưới đây được lấy từ `model_comparison.json` và `v2/model_comparison_v2.json`. Đây là comparison validation-only, không phải kết quả holdout final.

| Model | V1 ROC-AUC | V1 PR-AUC | V2 ROC-AUC | V2 PR-AUC |
|---|---:|---:|---:|---:|
| Logistic Regression | 0.8059 | 0.2522 | 0.8092 | 0.2518 |
| LightGBM | 0.8863 | 0.4739 | 0.8887 | 0.4770 |
| XGBoost | 0.8564 | 0.4285 | 0.8618 | 0.4538 |
| CatBoost | 0.8402 | 0.4083 | 0.8445 | 0.4298 |

Ở cả V1 và V2, LightGBM là model có validation PR-AUC cao nhất. Do đó, việc chọn LightGBM cho final V2 nhất quán với tiêu chí model selection đã được định nghĩa trong training code.

## 6. Model and feature differences

| Dimension | V1 | V2 |
|---|---|---|
| Final model type | LightGBM | LightGBM |
| Feature columns | 53 | 68 |
| Model version metadata | Artifact V1 không có `model_version` rõ ràng | `model_version: v2` |
| Final artifact | `model/artifacts/final_model.joblib` | `model/artifacts/v2/final_model_v2.joblib` |
| Comparison artifact | `model/artifacts/model_comparison.json` | `model/artifacts/v2/model_comparison_v2.json` |
| Training metadata | Không có metadata final tương đương V2 | `model/artifacts/v2/training_metadata_v2.json` |
| Feature selection | Legacy feature list trong artifact | Canonical `feature_order.json` |
| Metadata handling | Có nguy cơ metadata lọt vào vector nếu không lọc rõ | `split_name` và version metadata được loại khỏi feature vector |

V2 lưu `feature_count: 68` trong `training_metadata_v2.json`. Số feature V1 là `53`, được đọc từ trường `feature_columns` của `final_model.joblib`.

Các feature V2 được đưa vào theo feature contract của data pipeline, gồm các nhóm time, amount, missingness, identity/presence, entity aggregate và categorical features. Báo cáo này không kết luận từng feature riêng lẻ là nguyên nhân trực tiếp của cải thiện vì artifact hiện tại không có ablation study theo từng nhóm feature.

## 7. Important training correction in V2

Trong lần chạy V2, training ban đầu thất bại với lỗi:

```text
ValueError: could not convert string to float: 'train_weighted'
```

Nguyên nhân là cột metadata `split_name` lọt vào `X_train`. Giá trị `train_weighted` là string nên sklearn không thể chuyển thành numeric feature.

V2 đã sửa điểm này trong `model/src/fraud_model/features.py`:

- đọc danh sách feature canonical từ `data/processed/ieee_cis_fraud_risk/artifacts/preprocessing/feature_order.json`;
- chỉ chọn các cột trong `feature_columns`;
- loại metadata như `split_name`, `processing_version`, `feature_schema_version`, `generated_at`;
- kiểm tra và báo lỗi nếu thiếu required feature;
- giữ nguyên feature order giữa train, validation và holdout.

Đây là một thay đổi quan trọng về data/model contract, không chỉ là thay đổi implementation nhỏ. Nó giảm nguy cơ training-serving skew và ngăn model học thông tin mô tả split thay vì tín hiệu giao dịch.

## 8. V2 tuning result

V2 chọn LightGBM theo validation PR-AUC. Tham số tốt nhất được lưu trong log training:

```text
n_estimators=400
max_depth=6
learning_rate=0.05
verbosity=-1
```

Kết quả final V2:

| Stage | ROC-AUC | PR-AUC | Use |
|---|---:|---:|---|
| Validation after tuning | 0.8941 | 0.4925 | Chọn cấu hình |
| Holdout after selection | 0.8796 | 0.4582 | Đánh giá cuối |

Theo `model/src/fraud_model/tune_and_explain.py`, holdout được đọc sau khi model và parameters đã được chọn trên validation. Vì vậy, holdout V2 không được dùng trực tiếp để chọn cấu hình.

## 9. Artifact integrity and version separation

V2 không ghi đè final artifact legacy của V1. Các output được lưu riêng:

```text
model/artifacts/v2/baseline_logreg_v2.joblib
model/artifacts/v2/model_comparison_v2.json
model/artifacts/v2/final_model_v2.joblib
model/artifacts/v2/training_metadata_v2.json
```

`model/src/fraud_model/config.py` tách các path serving và training:

- serving mặc định: `FRAUD_MODEL_SERVING_VERSION=v2`;
- training mặc định: `FRAUD_MODEL_TRAINING_VERSION=v2`.

Vì vậy, việc tạo artifact V2 không tự động tạo một quyết định promotion có kiểm
soát. Cấu hình hiện đã chọn V2 làm mặc định cho demo, nhưng repository chưa có
registry record, approval, checksum và rollback smoke để gọi đó là production
promotion.

## 10. Limitations and open questions

Các điểm chưa đủ bằng chứng để kết luận hoàn toàn:

- Chưa có threshold analysis của V1/V2 trên cùng các operating points.
- Chưa có confusion matrix, precision, recall, F1 và business cost trong artifact final.
- Chưa có calibration comparison giữa V1 và V2.
- Chưa có prediction-level paired test để xác định mức cải thiện có ổn định trên từng nhóm transaction hay không.
- Chưa có production shadow test hoặc A/B test.
- V1 là legacy artifact không có `model_version` metadata rõ ràng.
- Model artifacts nằm trong thư mục được ignore bởi Git; cần lưu checksum hoặc model registry nếu muốn handover reproducible hoàn toàn.

Do đó, kết luận hiện tại nên được ghi là: **V2 có kết quả offline tốt hơn V1
trên artifact validation/holdout hiện có và là software default, nhưng chưa đủ
bằng chứng để được xem là production promotion.**

## 11. Recommendation

Đề xuất quy trình promote:

1. Giữ V2 làm software default cho demo và V1 làm rollback target.
2. So sánh threshold analysis của candidate mới với V2 trên các temporal window
   độc lập, tập trung vào PR-AUC, recall và false-positive rate.
3. Kiểm tra V2 bằng đúng input contract mà downstream scoring sử dụng.
4. Lưu model checksum, feature schema version, processing version và model version.
5. Có thể rollback bằng `FRAUD_MODEL_SERVING_VERSION=v1` nếu monitoring phát hiện
   regression hoặc incompatibility.

## 12. Conclusion

V2 là phiên bản có chất lượng offline tốt hơn V1 theo các metric hiện có. Cải thiện lớn nhất là Holdout PR-AUC tăng từ `0.4298` lên `0.4582`. Ngoài metric, V2 còn có feature contract rõ hơn, 68 feature được xác định theo canonical order và artifact versioning riêng.

Kết quả này đủ để giữ V2 làm serving default cho demo, nhưng chưa đủ để gọi là
serving production chính thức. Threshold, compatibility, deployment validation,
registry approval và rollback evidence phải được hoàn tất trước promotion.
