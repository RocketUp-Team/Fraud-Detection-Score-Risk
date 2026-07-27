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
 Sau khi clone repository, thành viên khác cần cung cấp raw data tại: https://drive.google.com/file/d/1n-PNthwE5DCWEqYuZjsl__OXCJqyX3mI/view?usp=sharing

  data/data/ieee-fraud-detection/
docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
```

Thông tin input/output và hướng dẫn bàn giao nằm trong [README_DATA_PIPELINE.md](README_DATA_PIPELINE.md), [DATA_DICTIONARY.md](DATA_DICTIONARY.md) và [HANDOVER_PROCESSED_DATA.md](HANDOVER_PROCESSED_DATA.md).

## Bắt đầu

Trong lúc chờ bàn giao, mỗi phần phát triển độc lập với mock/stub (xem mục 5 của kế hoạch — rủi ro nếu làm tuần tự). Xem README trong từng thư mục để biết chi tiết setup.

## Chạy full stack bằng Docker

```bash
docker compose up --build
```

Rồi mở `http://localhost:5173` → **Nạp dữ liệu** để nạp giao dịch (hoặc dùng CLI:
`docker compose exec backend uv run python -m fraud_backend.seed`).

Đã chạy thử thật trên colima: 3 service lên, model LightGBM nạp trong container,
nạp dữ liệu ghi vào Postgres, review lưu được, frontend phục vụ bundle đã build.

**Parquet không nằm trong image** (411MB, và `.dockerignore` loại `data/`) mà
mount lúc chạy. Mặc định lấy `./data/processed`. Nếu dữ liệu để chỗ khác — hoặc
bạn dùng colima trên macOS, nơi `~/Documents` bị chặn bởi cơ chế bảo mật TCC:

```bash
DATA_PROCESSED_DIR=$HOME/du-lieu/processed docker compose up
```

Thiếu mount này thì màn "Nạp dữ liệu" báo *"Chưa có dữ liệu đã tiền xử lý"*.

> **Nếu máy có cả Docker Desktop và colima**: cài Docker Desktop sẽ đổi context
> mặc định sang `desktop-linux`, và `docker compose ps` sẽ báo rỗng dù container
> đang chạy trên colima. Kiểm bằng `docker context ls`, đổi bằng
> `docker context use colima`.

Khởi động: PostgreSQL (`5432`), backend FastAPI (`8000`, docs ở `/docs`),
frontend dashboard (`5173`).

| Cổng | Dịch vụ | Đăng nhập |
|---|---|---|
| 5173 | Dashboard | — |
| 8000 | API (`/docs` là Swagger) | — |
| 5432 | PostgreSQL | user/pass/db đều là `fraud` |
| 8081 | Adminer — xem DB, bật bằng `--profile tools` | như trên |

Xem database: `docker compose --profile tools up -d adminer` rồi mở
**http://localhost:8081/?pgsql=db&username=fraud&db=fraud** (mật khẩu `fraud`).
Chi tiết ở [`backend/README.md`](./backend/README.md) mục 3. `model/` không phải service riêng — nó là module
Python (`fraud_model.score.score()`) mà backend import trực tiếp, không gọi
qua network.

Build context của backend là **repo root** (không phải `./backend`) vì backend
có path dependency tới `../model`.

## Chạy không cần Docker

Hai terminal:

```bash
# 1. Backend (Python ≥ 3.11 + uv)
cd backend && uv sync
uv run python -m fraud_backend.seed --limit 300   # SQLite, không cần Postgres
uv run uvicorn fraud_backend.main:app --reload

# 2. Frontend (Node ≥ 20.19)
cd frontend && npm install && npm run dev         # http://localhost:5173
```

Frontend chạy được cả khi chưa có backend: `VITE_USE_MOCKS=true npm run dev`.

Hợp đồng API dùng chung giữa hai phía: [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md).
Design system của dashboard: [`design-system/risk-scoring-engine/MASTER.md`](./design-system/risk-scoring-engine/MASTER.md).

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
