"""Cấu hình backend, đọc từ env (docker-compose truyền vào)."""
import os

# Postgres khi chạy docker compose; mặc định SQLite để chạy nhanh không cần DB
# server (dev/demo local, xem README).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fraud_demo.db")

# Vite dev server + preview build trong compose.
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
).split(",")

# Số dòng tối đa cho 1 lần import CSV — chặn upload nhầm file 600MB của IEEE-CIS.
MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "5000"))
