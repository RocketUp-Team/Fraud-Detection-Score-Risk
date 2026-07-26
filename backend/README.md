# backend/ — API chấm điểm rủi ro

FastAPI + SQLAlchemy. Chấm điểm giao dịch bằng model LightGBM của Quân (import
trực tiếp, không qua network), lưu Postgres/SQLite, phục vụ dashboard.

- Hợp đồng API: [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md) — nguồn sự
  thật. Đổi shape thì sửa cả `schemas.py` và `frontend/src/types/api.ts`.
- Từ điển feature: [`../DATA_DICTIONARY.md`](../DATA_DICTIONARY.md)

---

## 1. Cài đặt

### Cần gì

| | Vì sao |
|---|---|
| **Python ≥ 3.11** | `X \| None` trong annotation của SQLAlchemy 2.0 |
| **uv** | quản lý dependency, tự tải luôn Python 3.11 nếu máy chưa có |
| **libomp** (chỉ macOS) | LightGBM cần OpenMP runtime lúc predict |
| Docker | tuỳ chọn — chỉ cần khi chạy full stack |

### Các bước

```bash
# 1. uv (tự tải Python 3.11 khi sync, không cần cài Python riêng)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 2. macOS: LightGBM cần libomp, thiếu là model không load được
brew install libomp

# 3. Dependency
cd backend
uv sync
```

> **Nếu thiếu `libomp`**, backend vẫn khởi động nhưng rơi về `_HeuristicScorer`:
> `GET /meta` trả `model_name: "unavailable-heuristic"` kèm `warning`, và
> dashboard hiện banner vàng. Điểm lúc đó **không phải** của model.
> Lỗi gốc: `dlopen(...lib_lightgbm.dylib): Library not loaded: @rpath/libomp.dylib`.

### Vấn đề dependency đã xử lý

`shap` → `numba` → `llvmlite`. Với numpy rất mới mà `model/` pin, resolver tụt về
`llvmlite 0.36` — bản này không có wheel cho Python 3.11 và build from source thì
fail. `pyproject.toml` đặt sàn `numba>=0.62`, `llvmlite>=0.45` để luôn lấy bản có
wheel.

---

## 2. Chạy

### Nhanh nhất — SQLite, không cần Postgres

```bash
uv run uvicorn fraud_backend.main:app --reload
```
→ API `http://localhost:8000`, docs `http://localhost:8000/docs`

DB mặc định là file `fraud_demo.db`. Nạp dữ liệu bằng màn **Nạp dữ liệu** trên
dashboard, hoặc CLI (mục 3).

### Với Postgres

```bash
export DATABASE_URL=postgresql+psycopg://fraud:fraud@localhost:5432/fraud
uv run uvicorn fraud_backend.main:app --reload
```

> `postgresql://` (thiếu `+psycopg`) sẽ tìm psycopg2 và lỗi — driver ở đây là
> psycopg 3.

### Full stack bằng Docker

Xem [`../README.md`](../README.md). Điểm cần nhớ: build context là **repo root**
(backend có path dependency tới `../model`), và parquet **mount lúc chạy** qua
`DATA_PROCESSED_DIR` chứ không nằm trong image.

Schema tạo bằng `Base.metadata.create_all` lúc startup — **không dùng Alembic**.
Demo 8 ngày, 2 bảng, DB tạo lại được, nên migration là chi phí không cần thiết.

---

## 3. Nạp dữ liệu

Ba đường, đều gọi model để chấm rồi ghi DB:

| Đường | Dùng khi |
|---|---|
| Màn **Nạp dữ liệu** trên dashboard | mặc định, có tiến độ và nút dừng |
| `POST /data/load` | tự động hoá |
| `uv run python -m fraud_backend.seed` | CLI, dùng khi chưa có frontend |

### CLI

```bash
uv run python -m fraud_backend.seed --reset            # dùng SEED_LIMIT
uv run python -m fraud_backend.seed --limit 20000
SEED_DATASET=validation uv run python -m fraud_backend.seed
```

### Ba plan nạp

| Plan | Cách chọn dòng | Dùng khi |
|---|---|---|
| `coverage` | chấm rồi chỉ giữ dòng thuộc mức còn thiếu | cần **đủ 5 mức rủi ro** để trình bày. 20 ca/mức → 100 giao dịch, quét ~480 dòng |
| `sample` | ngẫu nhiên rải đều cả bộ, có seed | cần số liệu **đại diện**. Tái lập được |
| `head` | N dòng đầu theo thứ tự file | nhanh nhất, **không đại diện** — là một khối liền trong 1–2 file part |

Vì sao cần `coverage`: band `critical` chỉ ~3% dữ liệu thật, nạp ít thì không có
ca nghiêm trọng nào để trình bày.

Vì sao `sample` hơn `head`: đo thực tế, 5.000 dòng đầu cho 3,10% gian lận còn mẫu
ngẫu nhiên cho 3,62% — phân bố gốc là 3,50%. Nhưng `sample` chỉ bỏ được **lệch hệ
thống**, không bỏ được nhiễu do mẫu nhỏ: ở n=300 nó cho 5,33%.

### Nên nạp bộ nào

`/datasets` tự tính và xếp bộ nên dùng lên đầu. Tiêu chí suy ra từ dữ liệu, không
viết cứng: có nhãn `isFraud`, model chưa train trên đó, và tỉ lệ gian lận lệch
phân bố gốc ≤ 0,5 điểm %.

| Bộ | Dòng | Gian lận | |
|---|---|---|---|
| `holdout` | 89.092 | 3,49% | nên dùng |
| `validation` | 88.515 | 3,43% | nên dùng |
| `train_original` / `train_weighted` | 412.933 | 3,52% | model **đã học** → điểm đẹp giả tạo |
| `train_balanced` | 72.694 | **19,97%** | đã undersample → dashboard méo |
| `kaggle_test` | 506.691 | — | không có nhãn |

### Nạp bao nhiêu

| Số dòng | Ca gian lận | |
|---|---|---|
| 300 | ~7 | quá ít để trích recall/precision, lệch 1 ca là recall nhảy 14 điểm |
| 5.000 | ~155 | số liệu đã ổn định |
| 89.092 | 3.105 | đầy đủ, chấm ~12 phút |

Tốc độ đo thực tế: **~125 giao dịch/giây** khi có ghi DB (225/giây nếu chỉ chấm
không ghi).

### Xem database bằng giao diện

Docker Desktop quản container/volume/image nhưng **không có trình xem DB**. Bật
Adminer khi cần:

```bash
docker compose --profile tools up -d adminer
```

Mở thẳng link này (đã có sẵn driver + user, chỉ cần nhập mật khẩu `fraud`):

**http://localhost:8081/?pgsql=db&username=fraud&db=fraud**

> Vào `http://localhost:8081` trần sẽ báo *Connection refused* vì Adminer mặc
> định chọn MySQL. Đổi dropdown **System** sang PostgreSQL, hoặc dùng link trên.

Chạy trong profile `tools` nên `docker compose up` thường ngày không khởi động
nó. Cổng 8081 vì 8080 đã dành cho Spark UI.

Cách khác không cần thêm container:

```bash
docker compose exec db psql -U fraud -d fraud
```

Hoặc nối TablePlus/DBeaver vào `localhost:5432`, user/pass/db đều là `fraud`.

### Dữ liệu mất khi nào

| Lệnh | Container | Dữ liệu trong DB |
|---|---|---|
| `docker compose stop` | dừng | còn |
| `docker compose down` | xoá | **còn** — volume không bị đụng |
| `docker compose down -v` | xoá | **mất sạch** |

Dữ liệu Postgres nằm trong volume `..._db_data` (~51MB với 3.000 giao dịch),
không nằm trong thư mục repo. Chạy local không Docker thì dùng SQLite
`fraud_demo.db` — **hai nơi lưu khác nhau, không dùng chung dữ liệu**.

---

## 4. Endpoints

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/health` | |
| GET | `/meta` | model_version, explainability, `n_features`, 5 bands, `warning` khi fallback |
| GET | `/transactions` | filter `risk_band`/`decision`/`review_status`/`min_score`/`max_score`/`search`, `sort`, `page`, `page_size` |
| GET | `/transactions/stats` | KPI: total, pending, phân bố band, điểm TB, tổng tiền rủi ro cao |
| GET | `/transactions/{id}` | + `features`, `shap_top5`, `review` |
| POST | `/transactions/{id}/review` | duyệt/từ chối + gắn nhãn, gọi lại thì ghi đè |
| POST | `/score` | chấm ad-hoc, **không** ghi DB |
| POST | `/transactions/import` | CSV multipart, trả thêm độ khớp cột |
| GET | `/transactions/import/template` | tải CSV mẫu: đúng 53 header + N dòng thật |
| GET | `/datasets` | các bộ parquet + số dòng + tỉ lệ gian lận |
| POST | `/data/load` | nạp theo lô, trả `202` + `job_id` |
| GET | `/jobs/{id}` · `/jobs/active/current` | tiến độ |
| POST | `/jobs/{id}/cancel` | dừng, giữ phần đã chấm |

> `/transactions/stats` và `/transactions/import/template` phải khai báo **trước**
> `/transactions/{id}`, nếu không FastAPI parse `stats` thành int và trả 422. Có
> test chặn việc này.

---

## 5. Tích hợp model

`scoring.py` gọi `fraud_model.score.score(features)` — import module trực tiếp,
không qua network (theo `docs/RISK_SCORING_PLAN.md` mục 2). `warm_up()` chạy trong
`lifespan` để request đầu không phải chờ load joblib + SHAP.

`fraud-model` là path dependency (`[tool.uv.sources]` trỏ `../model`).

**Không load được model thì backend không sập**: rơi về `_HeuristicScorer`,
`GET /meta` trả `model_name: "unavailable-heuristic"` + `warning`, frontend hiện
banner. Điểm lúc đó không phải của model thật và UI nói rõ điều đó.

Model hiện tại: LightGBM, **53 feature**, có SHAP. Feature thiếu hoặc `None` đều
được điền `-999`.

---

## 6. Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./fraud_demo.db` | chuỗi kết nối SQLAlchemy |
| `CORS_ORIGINS` | `http://localhost:5173,…` | origin được phép, phân tách bằng dấu phẩy |
| `MAX_IMPORT_ROWS` | `5000` | chặn upload nhầm file CSV 600MB |
| `SEED_LIMIT` | `5000` | số dòng `seed.py` nạp (`--limit` thắng biến này) |
| `SEED_DATASET` | `holdout` | bộ dùng để seed |
| `DATA_PROCESSED_DIR` | `./data/processed` | (compose) nơi mount parquet |

---

## 7. Cấu trúc

```
src/fraud_backend/
├── config.py     # env
├── db.py         # engine + session (StaticPool cho sqlite in-memory)
├── models.py     # Transaction, Review
├── risk.py       # proba -> score -> band -> decision (nơi DUY NHẤT tính band)
├── schemas.py    # pydantic, khớp API_CONTRACT.md
├── scoring.py    # wrapper quanh fraud_model.score + fallback
├── service.py    # chấm điểm + upsert, dùng chung cho import/seed/load
├── datasets.py   # đọc parquet, tự suy ra bộ nào nên dùng
├── loader.py     # nạp theo lô có báo tiến độ (chạy nền)
├── jobs.py       # registry theo dõi job (TRONG BỘ NHỚ)
├── seed.py       # CLI
├── main.py       # app, lifespan, CORS, /health /meta /score
└── routers/
    ├── transactions.py
    └── data.py
```

---

## 8. Test

```bash
uv run pytest          # 23 test
uv run ruff check src/
```

- `test_risk.py` — chặn thay đổi bands ở mọi biên (19/20, 39/40, …)
- `test_api.py` — smoke toàn bộ endpoint trên SQLite in-memory, không cần
  Postgres và không cần model thật

---

## 9. Hạn chế đã biết

| | |
|---|---|
| **Job registry nằm trong RAM** | restart backend là mất job đang chạy và lịch sử. Chỉ đúng với 1 worker uvicorn. Muốn job sống qua restart thì phải Redis + arq/celery |
| **Import CSV đồng bộ** | giữ request HTTP suốt thời gian chấm (~40 giây cho 5.000 dòng). Lô lớn nên dùng `/data/load` |
| **Không có endpoint chấm lại** | mỗi dòng lưu `model_version` lúc được chấm. Đổi model thì dòng cũ giữ điểm cũ, dashboard trộn hai phiên bản |
| **Image backend 6,72GB** | vì `fraud-model` kéo theo cả PySpark (chỉ dùng lúc train). Tách extras `serving`/`training` sẽ giảm mạnh |
| **Chỉ một job nạp cùng lúc** | cố ý — hai job cùng ghi một bảng thì tiến độ vô nghĩa |
