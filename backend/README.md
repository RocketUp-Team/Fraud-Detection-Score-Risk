# backend/ — Trung (Backend)

FastAPI + SQLAlchemy: API transactions (list/detail), chấm điểm bằng model thật
của Quân, case/review, import CSV batch.

Hợp đồng API: [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md) — nguồn sự
thật, sửa shape thì sửa cả `schemas.py` và `frontend/src/types/api.ts`.

## Yêu cầu

Python ≥ 3.11 + [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run python -m fraud_backend.seed --limit 300   # tạo dữ liệu để FE có gì xem
uv run uvicorn fraud_backend.main:app --reload    # http://localhost:8000/docs
```

Mặc định dùng **SQLite** (`fraud_demo.db`) để chạy được ngay không cần DB
server. Muốn Postgres:

```bash
export DATABASE_URL=postgresql+psycopg://fraud:fraud@localhost:5432/fraud
```

> `postgresql://` (không có `+psycopg`) sẽ tìm psycopg2 và lỗi — driver ở đây
> là psycopg 3.

Schema tạo bằng `Base.metadata.create_all` lúc startup, **không dùng Alembic**
(demo 8 ngày, 2 bảng, DB tạo lại được).

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./fraud_demo.db` | Chuỗi kết nối SQLAlchemy |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Origin được phép, phân tách bằng dấu phẩy |
| `MAX_IMPORT_ROWS` | `5000` | Chặn upload nhầm file CSV 600MB |

## Endpoints

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/health` | |
| GET | `/meta` | model_version, explainability, 5 bands |
| GET | `/transactions` | filter `risk_band`/`decision`/`review_status`/`min_score`/`max_score`/`search`, `sort`, `page`, `page_size` |
| GET | `/transactions/{id}` | + `features`, `shap_top5`, `review` |
| POST | `/transactions/{id}/review` | duyệt/từ chối + gắn nhãn, gọi lại thì ghi đè |
| POST | `/score` | chấm điểm ad-hoc, **không** ghi DB |
| POST | `/transactions/import` | CSV multipart, dòng lỗi báo lại chứ không dừng batch |

## Tích hợp model

`scoring.py` gọi `fraud_model.score.score(features)` — import module trực tiếp,
không qua network (theo `docs/RISK_SCORING_PLAN.md` mục 2). Model được
`warm_up()` trong `lifespan` để request đầu không phải chờ load joblib + SHAP.

`fraud-model` là path dependency (`[tool.uv.sources]` trỏ `../model`), nên
Docker build **dùng context là repo root** — xem `docker-compose.yml`.

Nếu không load được model (thiếu artifact/dep), backend **không sập**: rơi về
`_HeuristicScorer` và `GET /meta` trả `model_name: "unavailable-heuristic"` kèm
`warning`, frontend hiện banner cảnh báo. Điểm lúc đó KHÔNG phải của model thật.

## Cấu trúc

```
src/fraud_backend/
├── config.py     # env
├── db.py         # engine + session (StaticPool cho sqlite in-memory)
├── models.py     # Transaction, Review
├── risk.py       # proba -> score -> band -> decision (nguồn duy nhất tính band)
├── schemas.py    # pydantic, khớp API_CONTRACT.md
├── scoring.py    # wrapper quanh fraud_model.score + fallback
├── service.py    # chấm điểm + upsert, dùng chung cho import và seed
├── seed.py       # seed từ parquet của An, fallback dữ liệu demo
├── main.py       # app, lifespan, CORS, /health /meta /score
└── routers/transactions.py
```

## Test

```bash
uv run pytest
```

`tests/test_risk.py` chặn thay đổi bands (biên 19/20, 39/40, …).
`tests/test_api.py` smoke toàn bộ endpoint trên SQLite in-memory, không cần
Postgres và không cần model thật.
