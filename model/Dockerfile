# Java cần cho PySpark (data.py/features.py chạy Spark trước khi convert
# sang pandas để train sklearn/LightGBM/XGBoost/CatBoost). Bookworm được ghim
# rõ ràng vì Debian Trixie dùng Java 21, không tương thích ổn định với Spark
# 3.5.1/Arrow trong workflow hiện tại.
FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless libgomp1 procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uv", "run", "python", "-m", "fraud_model.train_baseline"]
