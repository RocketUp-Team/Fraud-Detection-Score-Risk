# model/ — Quân (Huấn luyện & đóng gói mô hình)

Nhận feature pipeline từ An, train baseline (Logistic Regression), so sánh
LightGBM/XGBoost/CatBoost theo PR-AUC/ROC-AUC, tuning model tốt nhất, sinh
giải thích SHAP, và đóng gói thành module `score(features) -> {proba, shap}`
để Trung gọi từ backend.

Chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

## Nguồn dữ liệu: feature contract thật từ An

`data.py`/`features.py` đọc trực tiếp parquet đã xử lý bởi pipeline Spark của
An tại `../data/processed/ieee_cis_fraud_risk/model_ready/` (47 numeric + 7
categorical feature, đã impute median/missing-category, đã chia chronological
train/validation/holdout, có sẵn cột `class_weight`). Xem
[`../data/ieee_cis/HANDOVER_TO_QUAN.md`](../data/ieee_cis/HANDOVER_TO_QUAN.md)
và [`../DATA_DICTIONARY.md`](../DATA_DICTIONARY.md) cho data contract đầy đủ.

Nếu chưa có (`DatasetNotFoundError`), tạo bằng pipeline preprocessing ở repo
root (xem [`../README_DATA_PIPELINE.md`](../README_DATA_PIPELINE.md)):

```bash
# raw CSV đặt tại ../data/data/ieee-fraud-detection/ trước
docker compose -f ../docker-compose.preprocessing.yml build
docker compose -f ../docker-compose.preprocessing.yml run --rm preprocess
docker compose -f ../docker-compose.preprocessing.yml run --rm verify-processed
```

**Kỷ luật tránh leakage** (theo yêu cầu của An): `StringIndexer` cho 7 cột
categorical chỉ `fit` trên `train_weighted`, áp dụng lại (không refit) cho
validation/holdout. `train_compare`/`tune_and_explain` chỉ dùng
`validation` để chọn model/tham số; `holdout` chỉ được đánh giá **đúng một
lần** sau khi đã chốt, trong `tune_and_explain.py`.

`synthetic_data.py` (sinh dữ liệu giả từ CSV thô, xem lịch sử) vẫn còn nhưng
không dùng trong luồng chính nữa — chỉ hữu ích nếu cần test nhanh không phụ
thuộc pipeline của An.

## Kiến trúc: Spark cho xử lý dữ liệu, pandas cho train model

`data.py` đọc parquet bằng **PySpark**; `features.py` fit/apply
`StringIndexer` cho categorical trên Spark. Ngay trước khi train,
`features.to_pandas_xy()` convert Spark DataFrame sang pandas (X, y,
sample_weight), vì sklearn/LightGBM/XGBoost/CatBoost cần dữ liệu in-memory.
Đây là ranh giới duy nhất giữa hai thế giới.

`score()` (Ngày 5) **không cần Spark lúc serving** — `category_mappings`
(dict Python thuần, trích từ `StringIndexer` đã fit) được lưu kèm trong
artifact để encode categorical value thô (vd `"visa"`) mà không cần khởi
động JVM/Spark, phù hợp real-time scoring.

Mặc định chạy Spark ở chế độ `local[*]` (không cần cluster, chỉ cần Java —
xem mục Setup). Khi chạy trong Docker Compose với profile `training`, set
`SPARK_MASTER_URL=spark://spark-master:7077` để dùng cluster Spark thật (xem
mục "Chạy training qua Docker Compose + Spark cluster" bên dưới).

## Setup

Cần Java (PySpark yêu cầu JVM) — kiểm tra `java -version`. Trên macOS:
`brew install openjdk@17`.

```bash
cd model
uv sync
```

## Pipeline huấn luyện (chạy tuần tự)

```bash
uv run python -m fraud_model.train_baseline      # Ngày 1-2: baseline Logistic Regression
uv run python -m fraud_model.train_compare       # Ngày 3: so sánh LogReg/LightGBM/XGBoost/CatBoost
uv run python -m fraud_model.tune_and_explain     # Ngày 4: tuning model tốt nhất + SHAP + holdout (1 lần)
```

Train trên `train_weighted` (dùng `class_weight` làm `sample_weight`), chọn
model/tham số trên `validation`. Mỗi script lưu artifact:

| Script | Artifact |
|---|---|
| `train_baseline` | `artifacts/baseline_logreg.joblib` |
| `train_compare` | `artifacts/model_comparison.json` (kết quả so sánh + tên model tốt nhất) |
| `tune_and_explain` | `artifacts/final_model.joblib` (model đã tune + SHAP top-5 + metric holdout) |

`tune_and_explain` đọc `model_comparison.json` để biết model nào cần tune. Nếu
model tốt nhất không phải mô hình cây (LightGBM/XGBoost/CatBoost), script dừng
lại — dùng tạm baseline cho demo theo phương án dự phòng ở mục 5.

**Kết quả tham chiếu** (dữ liệu thật, Ngày 4, xem `artifacts/final_model.joblib`):
LightGBM tuned — validation ROC-AUC 0.888/PR-AUC 0.482, holdout (1 lần)
ROC-AUC 0.868/PR-AUC 0.430. Vượt Decision Tree weighted của An (holdout
PR-AUC 0.298, xem `HANDOVER_TO_QUAN.md`).

## Chạy training qua Docker Compose + Spark cluster

Mặc định `docker compose up` (xem `../docker-compose.yml`) chỉ khởi động
db/backend/frontend cho demo — **không** cần Spark cluster để chấm điểm.
Spark cluster chỉ cần khi training, nằm trong profile `training`:

```bash
docker compose --profile training up -d spark-master spark-worker
docker compose --profile training run --rm model-training \
  uv run python -m fraud_model.train_baseline
# tương tự cho train_compare / tune_and_explain
```

`model-training` build từ `model/Dockerfile` (có Java + uv), mount
`model/data` và `model/artifacts` để dữ liệu/kết quả không mất khi container
dừng, và tự set `SPARK_MASTER_URL=spark://spark-master:7077` để dùng cluster
thay vì `local[*]`. Xem Spark UI tại `http://localhost:8080` khi cluster chạy.

## `score()` — module bàn giao cho Trung (Ngày 5)

`artifacts/final_model.joblib` (LightGBM đã tune) đã commit sẵn trong repo —
Trung **không cần train lại**, chỉ cần `uv sync` trong `model/` rồi import
`fraud_model.score.score` là dùng được ngay.

```python
from fraud_model.score import score

score({
    "TransactionAmt": 120.0, "ProductCD": "w", "card4": "visa", "card6": "debit",
    "DeviceType": "mobile", "device_family": "apple", "M4": "m0",
    "amount_band": "01_10_25", "C5": 1.0, "C13": 10.0, ...
})
# -> {"proba": 0.0231, "shap": [{"feature": "C13", "shap_value": 0.14}, ...top 5]}
```

Cột categorical nhận giá trị string thô (viết thường, khớp giá trị lúc train
— xem `DATA_DICTIONARY.md`); được encode qua `category_mappings` lưu trong
artifact (không cần Spark). Ưu tiên `artifacts/final_model.joblib` (có SHAP
thật). Nếu chưa có — vd tuning trễ — tự động dùng tạm `baseline_logreg.joblib`
(`shap: None`), đúng phương án dự phòng "Đóng gói model trễ" ở mục 5 của kế
hoạch.

## Cấu trúc

```
model/
├── src/fraud_model/
│   ├── config.py           # đường dẫn (kể cả MODEL_READY_DIR của An), hằng số
│   ├── spark_session.py    # SparkSession dùng chung (local[*] hoặc cluster qua SPARK_MASTER_URL)
│   ├── data.py              # đọc parquet model_ready (Spark): train_weighted/validation/holdout/...
│   ├── features.py          # fit/apply StringIndexer (Spark, chỉ fit trên train), to_pandas_xy(),
│   │                        # extract_category_mappings()/encode_categoricals_pandas() cho score()
│   ├── synthetic_data.py    # sinh dữ liệu giả lập CSV (không dùng trong luồng chính)
│   ├── train_baseline.py    # baseline Logistic Regression + StandardScaler (Ngày 1-2)
│   ├── train_compare.py     # so sánh LogReg/LightGBM/XGBoost/CatBoost (Ngày 3)
│   ├── tune_and_explain.py  # tuning + SHAP + đánh giá holdout 1 lần (Ngày 4)
│   └── score.py             # module bàn giao cho Trung: score(features) -> {proba, shap} (Ngày 5)
├── Dockerfile               # Python + Java + uv, dùng cho service model-training
├── entrypoint.sh            # set JAVA_HOME động (đa kiến trúc) trước khi chạy
├── scripts/download_data.sh # tải raw CSV từ Kaggle (input cho pipeline của An)
├── artifacts/               # model + kết quả đã train (gitignored)
└── tests/
```

## Lộ trình tiếp theo

Theo `docs/RISK_SCORING_PLAN.md` mục 3 và 4:

- **Ngày 5:** bàn giao `score()` cho Trung tích hợp vào API thật
- **Ngày 6-7:** hỗ trợ tích hợp, theo dõi latency, bug bash
