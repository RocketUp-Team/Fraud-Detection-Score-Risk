from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from . import config
from .spark_session import get_spark


class DatasetNotFoundError(FileNotFoundError):
    pass


def _require_file(path):
    if not path.exists():
        raise DatasetNotFoundError(
            f"Không tìm thấy {path}. Chạy `bash scripts/download_data.sh` "
            "để tải bộ IEEE-CIS trước (cần Kaggle API token, xem README.md)."
        )
    return path


def load_transaction() -> DataFrame:
    spark = get_spark()
    return spark.read.csv(str(_require_file(config.TRAIN_TRANSACTION_FILE)), header=True, inferSchema=True)


def load_identity() -> DataFrame:
    spark = get_spark()
    return spark.read.csv(str(_require_file(config.TRAIN_IDENTITY_FILE)), header=True, inferSchema=True)


def load_merged() -> DataFrame:
    """Merge transaction + identity theo TransactionID (left join — chỉ
    ~24% giao dịch có identity, xem docs mục 5)."""
    tx = load_transaction()
    idn = load_identity()
    return tx.join(idn, on=config.ID_COL, how="left")


def time_based_split(df: DataFrame, val_fraction: float = config.VAL_FRACTION):
    """Chia train/val theo TransactionDT tăng dần thay vì random split —
    random split gây leakage và số liệu ảo (docs mục 5). Ngưỡng chia lấy
    theo approxQuantile để tránh phải sort/collect toàn bộ dữ liệu về driver."""
    threshold = df.approxQuantile(config.TIME_COL, [1 - val_fraction], 0.001)[0]
    train_df = df.filter(F.col(config.TIME_COL) < threshold)
    val_df = df.filter(F.col(config.TIME_COL) >= threshold)
    return train_df, val_df
