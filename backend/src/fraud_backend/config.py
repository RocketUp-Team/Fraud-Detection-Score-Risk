"""Cấu hình backend, đọc từ env (docker-compose truyền vào)."""
import os

# Postgres khi chạy docker compose; mặc định SQLite để chạy nhanh không cần DB
# server (dev/demo local, xem README).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fraud_demo.db")

# Vite dev server + preview build trong compose.
CORS_ORIGINS = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
).split(",") if origin.strip()]

# Chỉ nên bật khi chạy local/demo. Khi mở toàn bộ origin thì không dùng
# credentials/cookie cross-origin.
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() in {"1", "true", "yes"}

# Số dòng tối đa cho 1 lần import CSV — chặn upload nhầm file 600MB của IEEE-CIS.
MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "5000"))

# Số giao dịch seed vào DB. KHÔNG phải yêu cầu của bài — chỉ là lượng dữ liệu
# muốn có sẵn để xem/demo. `--limit` của seed.py thắng biến này.
#
# Chọn bao nhiêu: dưới ~1000 thì recall/precision dao động quá mạnh để nói được
# (300 dòng chỉ có ~7 ca gian lận, lệch 1 ca là recall nhảy 14 điểm). 5000 cho
# ~155 ca gian lận, đủ ổn định. Toàn bộ holdout là 89.092 dòng.
SEED_LIMIT = int(os.getenv("SEED_LIMIT", "5000"))

# Bộ dữ liệu trong `model_ready/` dùng để seed. `holdout` là tập chưa từng được
# train và giữ phân bố tự nhiên (~3,5% gian lận) nên đúng để demo; các tập
# `train_*` đã bị undersample nên tỉ lệ gian lận cao giả tạo.
SEED_DATASET = os.getenv("SEED_DATASET", "holdout")
