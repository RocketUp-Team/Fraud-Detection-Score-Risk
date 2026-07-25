# Build context là REPO ROOT (không phải ./backend) vì backend có path
# dependency tới ../model — xem docker-compose.yml.
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# libgomp1: LightGBM/XGBoost cần OpenMP runtime lúc predict.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy manifest của cả hai package trước để cache layer cài deps.
COPY backend/pyproject.toml backend/uv.lock ./backend/
COPY model/pyproject.toml model/README.md ./model/
COPY model/src ./model/src

WORKDIR /app/backend
# Không dùng --frozen: uv.lock chưa có sqlalchemy/psycopg/fraud-model, để uv
# tự resolve. Chạy `uv lock` ở backend/ rồi bật lại --frozen cho build tái lập.
RUN uv sync --no-install-project

COPY backend ./
RUN uv sync

# Model artifact (final_model.joblib) — score() load lúc startup.
COPY model/artifacts /app/model/artifacts

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "fraud_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
