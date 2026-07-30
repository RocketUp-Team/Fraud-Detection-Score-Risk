# model/ — Quân (Huấn luyện & đóng gói mô hình)

Nhận feature pipeline từ An, train baseline (Logistic Regression), so sánh
LightGBM/XGBoost/CatBoost theo PR-AUC/ROC-AUC, tuning model tốt nhất, sinh
giải thích SHAP, và đóng gói thành module `score(features) -> {proba, shap}`
để Trung gọi từ backend.

Chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

## Nguồn dữ liệu: feature contract thật từ An

`data.py`/`features.py` đọc trực tiếp parquet đã xử lý bởi pipeline Spark của
An tại `../data/processed/ieee_cis_fraud_risk/model_ready/` (61 numeric + 7
categorical feature, tổng cộng 68 feature theo canonical order; đã impute
median/missing-category, đã chia chronological
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
validation/holdout. Validation được chia theo thời gian thành selection
(50%), calibration (25%) và policy (25%). `train_compare`/`tune_and_explain`
chỉ dùng selection; `threshold_analysis` fit calibrator trên calibration và
chọn threshold trên policy. `evaluate_holdout` chỉ đọc holdout **đúng một
lần** sau khi model, calibrator và policy đã freeze.

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
uv run python -m fraud_model.validate_data
uv run python -m fraud_model.train_baseline
uv run python -m fraud_model.train_compare
uv run python -m fraud_model.tune_and_explain
uv run python -m fraud_model.threshold_analysis
uv run python -m fraud_model.evaluate_holdout
uv run python -m fraud_model.package_candidate
uv run python -m fraud_model.promotion_gate
```

`validation` được chia theo `TransactionDT` thành selection/calibration/policy
theo tỉ lệ 50/25/25. Holdout chỉ được đọc sau khi candidate, calibrator và
threshold policy đã freeze.

Train trên `train_weighted` (dùng `class_weight` làm `sample_weight`), chọn
model/tham số trên `validation`. Mỗi script lưu artifact:

| Script | Artifact |
|---|---|
| `train_baseline` | `artifacts/<version>/baseline_logreg_<version>.joblib` |
| `train_compare` | `artifacts/<version>/model_comparison_<version>.json` |
| `tune_and_explain` | model đã tune, SHAP và validation metrics |
| `threshold_analysis` | calibrator, threshold policy và threshold analysis |
| `evaluate_holdout` | one-time holdout metrics |
| `package_candidate` | candidate manifest và SHA-256 checksum |
| `promotion_gate` | quyết định review; không tự đổi serving version |

Quy ước hiện tại:

- `v1` = model cũ, giữ lại để rollback
- `v2` = model đã được promote làm serving default

Mặc định code training ghi sang `v2`. `score()` cũng phục vụ `v2`; rollback
bằng `FRAUD_MODEL_SERVING_VERSION=v1` mà không cần sửa code.

`tune_and_explain` đọc file comparison của đúng training version để biết
model nào cần tune. Logistic Regression và ba model cây
(LightGBM/XGBoost/CatBoost) đều có trainer tương ứng.

**Kết quả tham chiếu của model hiện hành (`v1`)**:
LightGBM tuned — validation ROC-AUC 0.888/PR-AUC 0.482, holdout (1 lần)
ROC-AUC 0.868/PR-AUC 0.430. Vượt Decision Tree weighted của An (holdout
PR-AUC 0.298, xem `HANDOVER_TO_QUAN.md`).

**Báo cáo so sánh V1/V2**: xem
[`../docs/AN_MODEL_V1_V2_COMPARISON_REPORT.md`](../docs/AN_MODEL_V1_V2_COMPARISON_REPORT.md).

Kết quả final đã chạy của `v2`:

| Metric | V1 | V2 |
|---|---:|---:|
| Validation ROC-AUC | 0.8877 | 0.8941 |
| Validation PR-AUC | 0.4820 | 0.4925 |
| Holdout ROC-AUC | 0.8684 | 0.8796 |
| Holdout PR-AUC | 0.4298 | 0.4582 |

V2 tốt hơn trên các metric offline hiện có và đã được promote. Threshold và
compatibility tiếp tục được theo dõi trong production; mỗi bản ghi scoring
gắn `model_version` để truy vết.

### MLflow training history

Các stage chính tạo run trong experiment `fraud-detection-training`:
`baseline`, `compare`, `tune_validation`, `threshold_and_calibration`,
`holdout_final` và `promotion_gate`. Mặc định MLflow dùng SQLite tại
`model/artifacts/mlflow.db` và lưu file artifacts tại
`model/artifacts/mlflow-artifacts/`; đặt `MLFLOW_TRACKING_URI` để dùng tracking
server chung. Khi dùng server chung, artifact location do server/experiment
quản lý thay vì bị ép về đường dẫn local của client. Run lưu model version,
Spark master, params, validation metrics và holdout metrics (chỉ ở stage cuối),
cùng metadata JSON.

## Retraining an toàn bằng candidate version

Nếu data pipeline thay đổi, giữ serving ở `v2` và train candidate bằng một
semantic version riêng:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train_model.ps1 `
  -Mode local `
  -TrainingVersion 0.0.3 `
  -DataRoot candidates\ieee_cis_fraud_risk_2_1_0
```

Output nằm trong `model/artifacts/0.0.3/`. Promotion gate chỉ ghi
`eligible_for_promotion_review` hoặc `not_promoted`; thao tác đổi serving
version luôn là bước review riêng.

### Một script training duy nhất

Chạy từ repo root để chạy lại toàn bộ workflow, không cần gọi từng stage:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train_model.ps1 `
  -TrainingVersion 0.0.3 `
  -DataRoot candidates\ieee_cis_fraud_risk_2_1_0
```

Script mặc định tự chọn semantic version tiếp theo: `0.0.1`, `0.0.2`,
`0.0.3`... Artifact được ghi vào `model/artifacts/<version>/` và tạo run mới
trong MLflow cho mỗi stage/mỗi lần chạy. Có thể truyền version thủ công khi
cần tái lập:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train_model.ps1 `
  -TrainingVersion 0.0.10
```

Chạy bằng Spark standalone cluster:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train_model.ps1 `
  -Mode cluster `
  -TrainingVersion 0.0.3 `
  -DataRoot candidates\ieee_cis_fraud_risk_2_1_0
```

Cluster failure làm workflow fail rõ ràng; script không âm thầm fallback sang
local trong cùng run.

V1/V2 hiện có vẫn được giữ nguyên để rollback. Training mới không tự động đổi
serving default.

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
Master/worker dùng image chính thức `apache/spark:3.5.1`; training image ghim
Java 17. Arrow collection mặc định tắt để giữ tương thích runtime và có thể
opt-in bằng `FRAUD_SPARK_ARROW_ENABLED=true` khi benchmark.

Nếu không cần cluster, chọn local Spark rõ ràng bằng script PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\train_model.ps1 `
  -Mode local `
  -TrainingVersion 0.0.3 `
  -DataRoot candidates\ieee_cis_fraud_risk_2_1_0
```

Script dùng `model-training-local` với `SPARK_MASTER_URL=local[*]`; candidate
được ghi vào thư mục version riêng và không ghi đè V2.

## `score()` — module bàn giao cho Trung (Ngày 5)

`v2` là model mặc định để backend gọi. Artifact V1 vẫn được giữ để rollback
nhanh bằng biến môi trường `FRAUD_MODEL_SERVING_VERSION=v1`. Artifact hiện hành
(LightGBM đã tune) đã commit sẵn trong repo —
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
artifact (không cần Spark). Serving default tiếp tục dùng artifact `v2`;
candidate semantic version chỉ được xem xét sau khi tất cả gates đạt.

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
│   ├── tune_and_explain.py  # tuning + SHAP trên selection window
│   ├── threshold_analysis.py # calibration + policy thresholds
│   ├── evaluate_holdout.py  # one-time final holdout evaluation
│   ├── package_candidate.py # manifest + checksum + load/score smoke
│   ├── promotion_gate.py    # review decision, không auto-promote
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
