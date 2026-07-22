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
