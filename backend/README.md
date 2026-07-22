# backend/ — Trung (Backend)

Phụ trách: scaffold FastAPI + schema CSDL (PostgreSQL) + Docker, API transactions (CRUD/list/detail), scoring, case/review, import CSV batch, tích hợp module `score()` từ `model/` vào API chấm điểm thật, và Docker Compose full stack cho buổi demo.

Xem chi tiết phân công & lịch: [`../docs/RISK_SCORING_PLAN.md`](../docs/RISK_SCORING_PLAN.md) mục 2 và 4.

**Nhận từ Quân (Ngày 5 — 26/07):** module `score(features) -> {proba, shap}` từ `model/`.

**Hợp đồng API với Long:** chốt schema JSON mẫu trước cuối Ngày 1 (22/07) — không chờ dữ liệu thật.

## Đã scaffold sẵn (Ngày 1)

FastAPI stub (uv) với `/health`, `/transactions` (mock), `/transactions/{id}`
(mock) tại `src/fraud_backend/main.py`, và `Dockerfile` để chạy trong
`docker compose` (xem `../docker-compose.yml`).

```bash
cd backend
uv sync
uv run uvicorn fraud_backend.main:app --reload
```

CRUD thật, schema DB, scoring/case-review endpoint, batch import CSV do
Trung tự xây tiếp theo phân công.

**Tích hợp model (Ngày 5):** thêm `model/` làm path dependency
(`uv add --editable ../model`) rồi gọi `fraud_model.score.score(features)`
trong scoring endpoint — xem `../model/README.md`.
