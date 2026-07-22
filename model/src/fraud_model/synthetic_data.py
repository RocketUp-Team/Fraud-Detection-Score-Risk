"""Sinh dữ liệu giả lập theo schema IEEE-CIS để phát triển/test pipeline cục
bộ trước khi có dataset thật từ Kaggle (xem `scripts/download_data.sh`) hoặc
feature pipeline thật từ An (bàn giao Ngày 3).

Chạy:
    uv run python -m fraud_model.synthetic_data
"""
import numpy as np
import pandas as pd

from . import config


def generate(n: int = 5000, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)

    tx = pd.DataFrame(
        {
            config.ID_COL: range(1, n + 1),
            config.TIME_COL: np.sort(rng.integers(0, 1_000_000, size=n)),
            config.TARGET_COL: rng.choice([0, 1], size=n, p=[0.965, 0.035]),
            "TransactionAmt": rng.exponential(50, size=n),
            "ProductCD": rng.choice(["W", "C", "H", "R"], size=n),
            "card4": rng.choice(["visa", "mastercard", None], size=n),
        }
    )

    n_identity = int(n * 0.24)
    idn = pd.DataFrame(
        {
            config.ID_COL: rng.choice(tx[config.ID_COL], size=n_identity, replace=False),
            "DeviceType": rng.choice(["mobile", "desktop"], size=n_identity),
        }
    )

    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    tx.to_csv(config.TRAIN_TRANSACTION_FILE, index=False)
    idn.to_csv(config.TRAIN_IDENTITY_FILE, index=False)
    print(f"[synthetic_data] wrote {len(tx)} transactions -> {config.TRAIN_TRANSACTION_FILE}")
    print(f"[synthetic_data] wrote {len(idn)} identity rows -> {config.TRAIN_IDENTITY_FILE}")


if __name__ == "__main__":
    generate()
