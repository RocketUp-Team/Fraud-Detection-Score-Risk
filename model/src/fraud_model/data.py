from pathlib import Path

from pyspark.sql import DataFrame

from . import config
from .spark_session import get_spark


class DatasetNotFoundError(FileNotFoundError):
    pass


def _require_dir(path: Path) -> Path:
    if not path.exists():
        raise DatasetNotFoundError(
            f"Không tìm thấy {path}. Chạy pipeline preprocessing của An trước "
            "(xem README_DATA_PIPELINE.md ở repo root): "
            "docker compose -f docker-compose.preprocessing.yml build && "
            "docker compose -f docker-compose.preprocessing.yml run --rm preprocess"
        )
    return path


def load_dataset(name: str) -> DataFrame:
    """name: một trong train_original/train_weighted/train_balanced/
    validation/holdout/kaggle_test — xem data/ieee_cis/HANDOVER_TO_QUAN.md."""
    spark = get_spark()
    return spark.read.parquet(str(_require_dir(config.MODEL_READY_DIR / name)))


def load_train_weighted() -> DataFrame:
    """Điểm bắt đầu khuyến nghị của An — dùng cột `class_weight` làm
    sample_weight khi train thay vì class_weight='balanced' tự đoán."""
    return load_dataset("train_weighted")


def load_train_balanced() -> DataFrame:
    return load_dataset("train_balanced")


def load_validation() -> DataFrame:
    """Dùng để chọn model/tuning — không refit transform nào trên tập này."""
    return load_dataset("validation")


def load_holdout() -> DataFrame:
    """Chỉ đánh giá MỘT LẦN sau khi đã chốt model trên validation, xem
    data/ieee_cis/HANDOVER_TO_QUAN.md mục leakage precautions."""
    return load_dataset("holdout")
