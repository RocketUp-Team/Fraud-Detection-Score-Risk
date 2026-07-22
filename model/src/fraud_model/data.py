import pandas as pd

from . import config


class DatasetNotFoundError(FileNotFoundError):
    pass


def _require_file(path):
    if not path.exists():
        raise DatasetNotFoundError(
            f"Không tìm thấy {path}. Chạy `bash scripts/download_data.sh` "
            "để tải bộ IEEE-CIS trước (cần Kaggle API token, xem README.md)."
        )
    return path


def load_transaction() -> pd.DataFrame:
    return pd.read_csv(_require_file(config.TRAIN_TRANSACTION_FILE))


def load_identity() -> pd.DataFrame:
    return pd.read_csv(_require_file(config.TRAIN_IDENTITY_FILE))


def load_merged() -> pd.DataFrame:
    """Merge transaction + identity theo TransactionID (left join — chỉ
    ~24% giao dịch có identity, xem docs mục 5)."""
    tx = load_transaction()
    idn = load_identity()
    return tx.merge(idn, on=config.ID_COL, how="left")


def time_based_split(df: pd.DataFrame, val_fraction: float = config.VAL_FRACTION):
    """Chia train/val theo TransactionDT tăng dần thay vì random split —
    random split gây leakage và số liệu ảo (docs mục 5)."""
    df_sorted = df.sort_values(config.TIME_COL).reset_index(drop=True)
    split_idx = int(len(df_sorted) * (1 - val_fraction))
    return df_sorted.iloc[:split_idx], df_sorted.iloc[split_idx:]
