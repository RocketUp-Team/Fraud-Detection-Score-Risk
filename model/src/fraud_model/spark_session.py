"""SparkSession dùng chung cho data.py/features.py.

Mặc định `local[*]` cho dev cục bộ (không cần cluster). Khi chạy trong
`docker compose` (xem `../docker-compose.yml`), set `SPARK_MASTER_URL` trỏ
tới `spark://spark-master:7077` để dùng cluster Spark thật.
"""
import os

from pyspark.sql import SparkSession


def get_spark() -> SparkSession:
    master = os.environ.get("SPARK_MASTER_URL", "local[*]")
    return (
        SparkSession.builder.appName("fraud-model")
        .master(master)
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "8g"))
        .config("spark.driver.maxResultSize", "0")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
        .getOrCreate()
    )
