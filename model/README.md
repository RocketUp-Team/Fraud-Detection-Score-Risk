# model/ — Quân (Huấn luyện & đóng gói mô hình)

Nhận feature pipeline từ An, train baseline (Logistic Regression), so sánh
LightGBM/XGBoost/CatBoost theo PR-AUC/ROC-AUC, tuning model tốt nhất, sinh
giải thích SHAP, và đóng gói thành module `score(features) -> {proba, shap}`
để Trung gọi từ backend.

Chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

## Kiến trúc: Spark cho xử lý dữ liệu, pandas cho train model

`data.py` và `features.py` chạy trên **PySpark** (đọc CSV, merge
transaction+identity, time-based split, fillna, encode categorical) — phần
việc nặng và có thể phân tán. Ngay trước khi train, `features.to_pandas_xy()`
convert Spark DataFrame sang pandas, vì sklearn/LightGBM/XGBoost/CatBoost cần
dữ liệu in-memory, không đọc trực tiếp Spark DataFrame. Đây là ranh giới
duy nhất giữa hai thế giới.

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

## Dữ liệu

**Dataset thật (IEEE-CIS Fraud Detection):**

```bash
bash scripts/download_data.sh
```

Cần Kaggle API token (`~/.kaggle/kaggle.json`) và đã tham gia competition
`ieee-fraud-detection`. Sau khi tải, kỳ vọng có `data/raw/train_transaction.csv`
và `data/raw/train_identity.csv`.

**Dữ liệu giả lập (dev/test khi chưa có Kaggle token hoặc chưa có feature
pipeline thật từ An):**

```bash
uv run python -m fraud_model.synthetic_data
```

Sinh cùng schema (`TransactionID`, `TransactionDT`, `isFraud`, vài cột số/danh
mục) vào `data/raw/`, đủ để chạy toàn bộ pipeline bên dưới end-to-end.

## Pipeline huấn luyện (chạy tuần tự)

```bash
uv run python -m fraud_model.train_baseline      # Ngày 1-2: baseline Logistic Regression
uv run python -m fraud_model.train_compare       # Ngày 3: so sánh LogReg/LightGBM/XGBoost/CatBoost
uv run python -m fraud_model.tune_and_explain     # Ngày 4: tuning model tốt nhất + SHAP
```

Mỗi script in ROC-AUC/PR-AUC trên tập validation chia theo thời gian
(`TransactionDT`, xem `docs/RISK_SCORING_PLAN.md` mục 5 — không random split
để tránh leakage) và lưu artifact:

| Script | Artifact |
|---|---|
| `train_baseline` | `artifacts/baseline_logreg.joblib` |
| `train_compare` | `artifacts/model_comparison.json` (kết quả so sánh + tên model tốt nhất) |
| `tune_and_explain` | `artifacts/final_model.joblib` (model đã tune + top-5 feature SHAP toàn cục) |

`tune_and_explain` đọc `model_comparison.json` để biết model nào cần tune. Nếu
model tốt nhất không phải mô hình cây (LightGBM/XGBoost/CatBoost), script dừng
lại — dùng tạm baseline cho demo theo phương án dự phòng ở mục 5.

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

```python
from fraud_model.score import score

score({"TransactionAmt": 120.0, "ProductCD": "W", ...})
# -> {"proba": 0.0231, "shap": [{"feature": "TransactionAmt", "shap_value": 0.14}, ...top 5]}
```

Ưu tiên `artifacts/final_model.joblib` (có SHAP thật). Nếu chưa có — vd tuning
trễ — tự động dùng tạm `baseline_logreg.joblib` (`shap: None`), đúng phương án
dự phòng "Đóng gói model trễ" ở mục 5 của kế hoạch.

## Cấu trúc

```
model/
├── src/fraud_model/
│   ├── config.py           # đường dẫn, hằng số (cột ID/target/thời gian, đường dẫn artifact)
│   ├── spark_session.py    # SparkSession dùng chung (local[*] hoặc cluster qua SPARK_MASTER_URL)
│   ├── data.py              # load + merge transaction/identity (Spark), time-based split
│   ├── features.py          # feature prep (Spark: fillna, StringIndexer) + to_pandas_xy() convert biên
│   ├── synthetic_data.py    # sinh dữ liệu giả lập cho dev/test cục bộ (pandas, ghi CSV)
│   ├── train_baseline.py    # baseline Logistic Regression + StandardScaler (Ngày 1)
│   ├── train_compare.py     # so sánh LogReg/LightGBM/XGBoost/CatBoost (Ngày 3)
│   ├── tune_and_explain.py  # tuning + SHAP (Ngày 4)
│   └── score.py             # module bàn giao cho Trung: score(features) -> {proba, shap} (Ngày 5)
├── Dockerfile               # Python + Java + uv, dùng cho service model-training
├── entrypoint.sh            # set JAVA_HOME động (đa kiến trúc) trước khi chạy
├── scripts/download_data.sh
├── data/raw/                # dataset thô (gitignored)
├── data/processed/          # dataset đã xử lý (gitignored)
├── artifacts/               # model + kết quả đã train (gitignored)
└── tests/
```

## Lộ trình tiếp theo

Theo `docs/RISK_SCORING_PLAN.md` mục 3 và 4:

- **Ngày 2:** thay `features.prepare_baseline_features` bằng feature pipeline theo EDA của An
- **Ngày 3:** nhận feature pipeline chính thức từ An → chạy lại `train_compare`
- **Ngày 5:** bàn giao `score()` cho Trung tích hợp vào API thật
- **Ngày 6-7:** hỗ trợ tích hợp, theo dõi latency, bug bash
