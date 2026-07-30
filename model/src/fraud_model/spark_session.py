"""SparkSession dùng chung cho data.py/features.py.

Mặc định `local[*]` cho dev cục bộ (không cần cluster). Khi chạy trong
`docker compose` (xem `../docker-compose.yml`), set `SPARK_MASTER_URL` trỏ
tới `spark://spark-master:7077` để dùng cluster Spark thật.
"""
import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession


def _python_executable_for_spark() -> str:
    executable = str(Path(sys.executable).resolve())
    if os.name != "nt" or " " not in executable:
        return executable
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(
            executable,
            buffer,
            len(buffer),
        )
        if length:
            return buffer.value
    except (AttributeError, OSError):
        pass
    return executable


def get_spark() -> SparkSession:
    python_executable = _python_executable_for_spark()
    os.environ.setdefault("PYSPARK_PYTHON", python_executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", python_executable)
    master = os.environ.get("SPARK_MASTER_URL", "local[*]")
    # Non-Arrow collection is the conservative default for Spark 3.5.1 across
    # supported JDKs. It is slower, but avoids a native DirectByteBuffer crash
    # observed with Arrow on Java 21. Controlled opt-in keeps benchmarking easy.
    arrow_enabled = os.environ.get("FRAUD_SPARK_ARROW_ENABLED", "false").lower()
    if arrow_enabled not in {"true", "false"}:
        raise ValueError("FRAUD_SPARK_ARROW_ENABLED must be 'true' or 'false'")
    spark = (
        SparkSession.builder.appName("fraud-model")
        .master(master)
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "8g"))
        .config("spark.driver.maxResultSize", "0")
        .config("spark.sql.execution.arrow.pyspark.enabled", arrow_enabled)
        .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
        .getOrCreate()
    )
    expected_version = os.environ.get("FRAUD_EXPECTED_SPARK_VERSION", "3.5.1")
    if spark.version != expected_version:
        spark.stop()
        raise RuntimeError(
            f"Spark runtime mismatch: expected {expected_version}, got {spark.version}"
        )
    return spark
