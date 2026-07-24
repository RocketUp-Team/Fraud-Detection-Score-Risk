# Risk Scoring Engine — Demo 8 ngày

Ứng dụng chấm điểm rủi ro (0–100) cho giao dịch, huấn luyện từ IEEE-CIS Fraud Detection, có API chấm điểm, dashboard xem điểm rủi ro + giải thích SHAP, và luồng rà soát/gắn nhãn thủ công.

Kế hoạch chi tiết + Gantt chart: [`docs/RISK_SCORING_PLAN.md`](./docs/RISK_SCORING_PLAN.md) ([bản HTML trực quan](./docs/risk-scoring-plan.html)).

Nhóm: **An (Data/EDA) · Quân (Model) · Trung (Backend) · Long (Frontend)**

## Cấu trúc repo

```
.
├── data/       # An — khảo sát, làm sạch, feature engineering (IEEE-CIS)
├── model/      # Quân — huấn luyện, so sánh model, SHAP, đóng gói score()
├── backend/    # Trung — FastAPI + PostgreSQL + Docker
├── frontend/   # Long — React + TypeScript dashboard
└── docs/       # Kế hoạch demo, Gantt chart
```

Mỗi thư mục có README riêng mô tả cách setup và chạy phần việc tương ứng. Điểm bàn giao giữa các phần theo `docs/RISK_SCORING_PLAN.md` mục 2:

- **An → Quân**: feature pipeline (Ngày 3)
- **Quân → Trung**: module `score(features) -> {proba, shap}` (Ngày 5)
- **Trung ↔ Long**: hợp đồng API JSON (chốt Ngày 1, tích hợp thật Ngày 5)

## IEEE-CIS preprocessing

The completed root-level workflow is documented in [README_DATA_PIPELINE.md](README_DATA_PIPELINE.md). It produces the verified handoff at `data/processed/ieee_cis_fraud_risk`.

```powershell
docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
```

Đọc [data/README.md](data/README.md) và [data/ieee_cis/README_DATA_PROCESSING_EDA.md](data/ieee_cis/README_DATA_PROCESSING_EDA.md) để chạy pipeline Spark và bàn giao dữ liệu cho model workflow:

```powershell
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml build
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml run --rm preprocess
docker compose -f data\ieee_cis\docker-compose.preprocessing.yml run --rm verify-processed
```

Kết quả đã ghi nhận và hướng dẫn bàn giao cho Quân:

- [data/ieee_cis/RESULTS_REPORT.md](data/ieee_cis/RESULTS_REPORT.md)
- [data/ieee_cis/HANDOVER_TO_QUAN.md](data/ieee_cis/HANDOVER_TO_QUAN.md)
- [data/ieee_cis/README_DATA_PROCESSING_EDA.md](data/ieee_cis/README_DATA_PROCESSING_EDA.md)

## Bắt đầu

Trong lúc chờ bàn giao, mỗi phần phát triển độc lập với mock/stub (xem mục 5 của kế hoạch — rủi ro nếu làm tuần tự). Xem README trong từng thư mục để biết chi tiết setup.

## Chạy full stack bằng Docker

```bash
docker compose up --build
```

Khởi động: PostgreSQL (`5432`), backend FastAPI stub (`8000`, `/health`,
`/transactions` mock), frontend Vite stub (`5173`). `model/` chưa phải một
service riêng — theo kế hoạch, nó được đóng gói thành module Python
(`fraud_model.score.score()`) và Trung import trực tiếp vào backend ở
Ngày 5, không gọi qua network.

## Training model qua Spark cluster (profile riêng)

`model/` xử lý dữ liệu (load/merge/feature prep) bằng PySpark trước khi train
model bằng sklearn/LightGBM/XGBoost/CatBoost (xem `model/README.md`). Spark
cluster không khởi động cùng `docker compose up` mặc định — chỉ bật khi
training, qua profile `training`:

```bash
docker compose --profile training up -d spark-master spark-worker
docker compose --profile training run --rm model-training \
  uv run python -m fraud_model.train_baseline
```

Spark UI: `http://localhost:8080`.
