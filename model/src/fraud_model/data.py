from pathlib import Path
from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from . import config
from .spark_session import get_spark


class DatasetNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class ValidationWindows:
    selection: DataFrame
    calibration: DataFrame
    policy: DataFrame
    selection_boundary: float
    calibration_boundary: float
    counts: dict[str, int]


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


def split_validation_windows(validation_df: DataFrame) -> ValidationWindows:
    """Split validation chronologically into 50% selection, 25% calibration,
    and 25% policy windows without changing the public data contract."""
    if config.TIME_COL not in validation_df.columns:
        raise ValueError(f"validation dataset is missing {config.TIME_COL}")

    selection_boundary, calibration_boundary = validation_df.approxQuantile(
        config.TIME_COL,
        [0.50, 0.75],
        0.0,
    )
    selection = validation_df.filter(
        F.col(config.TIME_COL) <= F.lit(selection_boundary)
    )
    calibration = validation_df.filter(
        (F.col(config.TIME_COL) > F.lit(selection_boundary))
        & (F.col(config.TIME_COL) <= F.lit(calibration_boundary))
    )
    policy = validation_df.filter(
        F.col(config.TIME_COL) > F.lit(calibration_boundary)
    )
    windows = {
        "selection": selection,
        "calibration": calibration,
        "policy": policy,
    }
    counts = {name: frame.count() for name, frame in windows.items()}
    if any(count <= 0 for count in counts.values()):
        raise ValueError(f"validation temporal split produced an empty window: {counts}")
    if sum(counts.values()) != validation_df.count():
        raise ValueError(
            "validation temporal windows do not cover the source exactly once: "
            f"{counts}"
        )

    ordered_bounds = {
        name: frame.agg(
            F.min(config.TIME_COL).alias("minimum"),
            F.max(config.TIME_COL).alias("maximum"),
        ).first()
        for name, frame in windows.items()
    }
    if not (
        ordered_bounds["selection"]["maximum"]
        <= ordered_bounds["calibration"]["minimum"]
        <= ordered_bounds["calibration"]["maximum"]
        <= ordered_bounds["policy"]["minimum"]
    ):
        raise ValueError(
            f"validation temporal windows are not ordered: {ordered_bounds}"
        )

    return ValidationWindows(
        selection=selection,
        calibration=calibration,
        policy=policy,
        selection_boundary=float(selection_boundary),
        calibration_boundary=float(calibration_boundary),
        counts=counts,
    )
