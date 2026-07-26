"""Seed DB để frontend có dữ liệu thật xem ngay.

    uv run python -m fraud_backend.seed --reset             # dùng SEED_LIMIT
    uv run python -m fraud_backend.seed --limit 20000       # ghi đè
    SEED_DATASET=validation uv run python -m fraud_backend.seed

Số lượng và bộ dữ liệu đều cấu hình được (`SEED_LIMIT`, `SEED_DATASET` trong
config.py) — không có con số nào là bắt buộc.

Đọc parquet `model_ready` của An (`data/processed/ieee_cis_fraud_risk/`). Nếu
chưa có (chưa chạy preprocessing, hoặc parquet bị gitignore trên máy khác) thì
sinh dữ liệu demo theo đúng feature contract trong DATA_DICTIONARY.md, để không
ai bị chặn — nhưng in cảnh báo rõ ràng.
"""
import argparse
import logging
import math
import random
from pathlib import Path

from . import config
from .db import Base, SessionLocal, engine
from .service import split_features, upsert_scored_transaction

log = logging.getLogger("seed")

# seed.py -> fraud_backend -> src -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_READY_DIR = REPO_ROOT / "data" / "processed" / "ieee_cis_fraud_risk" / "model_ready"

CATEGORICAL_CHOICES = {
    "ProductCD": ["W", "C", "R", "H", "S"],
    "card4": ["visa", "mastercard", "american express", "discover"],
    "card6": ["debit", "credit", "__MISSING__"],
    "DeviceType": ["desktop", "mobile", "__MISSING__"],
    "device_family": ["windows", "ios", "android", "macos", "__MISSING__"],
    "M4": ["M0", "M1", "M2", "__MISSING__"],
}


def _rows_from_parquet(limit: int) -> list[dict] | None:
    if not MODEL_READY_DIR.exists():
        return None
    try:
        import pandas as pd
    except ImportError:
        log.warning("Không có pandas — bỏ qua parquet.")
        return None

    # Đọc đúng bộ đã cấu hình. Trước đây rglob toàn bộ model_ready rồi lấy file
    # nào xếp trước — nghĩa là tuỳ thứ tự tên thư mục, có thể rơi vào train_*
    # (đã undersample, tỉ lệ gian lận cao giả tạo).
    dataset_dir = MODEL_READY_DIR / config.SEED_DATASET
    if not dataset_dir.exists():
        log.warning(
            "Không có bộ %s trong %s — có %s",
            config.SEED_DATASET,
            MODEL_READY_DIR,
            [p.name for p in MODEL_READY_DIR.iterdir() if p.is_dir()],
        )
        return None

    parquets = sorted(dataset_dir.rglob("*.parquet"))
    if not parquets:
        return None

    frames, total = [], 0
    for path in parquets:
        df = pd.read_parquet(path)
        frames.append(df)
        total += len(df)
        if total >= limit:
            break
    df = pd.concat(frames).head(limit)
    log.info("Đọc %d dòng từ %s", len(df), dataset_dir)
    return df.to_dict(orient="records")


def _synthetic_rows(limit: int) -> list[dict]:
    log.warning(
        "Chưa có parquet ở %s — sinh %d dòng DEMO theo feature contract. "
        "Chạy preprocessing của An để có dữ liệu thật.",
        MODEL_READY_DIR,
        limit,
    )
    rng = random.Random(42)  # cố định seed -> seed lại cho cùng dữ liệu
    rows = []
    for i in range(limit):
        amount = round(rng.lognormvariate(4.0, 1.3), 2)
        has_identity = rng.choice([0, 1])
        row = {
            "TransactionID": 2987000 + i,
            "TransactionAmt": amount,
            "log_transaction_amount": round(math.log1p(amount), 4),
            "amount_band": ("low" if amount < 50 else "mid" if amount < 500 else "high"),
            "has_identity": has_identity,
            "has_device_info": rng.choice([0, 1]),
            "has_p_email": rng.choice([0, 1]),
            "has_r_email": rng.choice([0, 1]),
            "selected_missing_count": rng.randint(0, 30),
            "selected_missing_ratio": round(rng.random(), 4),
            "identity_missing_count": 0 if has_identity else rng.randint(20, 45),
            "prior_card_transaction_count": rng.randint(0, 60),
            "prior_card_amount_sum": round(rng.uniform(0, 9000), 2),
            "prior_email_transaction_count": rng.randint(0, 40),
            "prior_email_amount_sum": round(rng.uniform(0, 6000), 2),
            "prior_device_transaction_count": rng.randint(0, 20),
            "prior_device_amount_sum": round(rng.uniform(0, 12000), 2),
        }
        for col, choices in CATEGORICAL_CHOICES.items():
            row[col] = rng.choice(choices)
        rows.append(row)
    return rows


def seed(limit: int | None = None, reset: bool = False) -> int:
    limit = limit if limit is not None else config.SEED_LIMIT
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    rows = _rows_from_parquet(limit) or _synthetic_rows(limit)

    inserted = 0
    with SessionLocal() as db:
        for row in rows:
            txn_id, features = split_features(row)
            if txn_id is None:
                continue
            upsert_scored_transaction(db, txn_id, features)
            inserted += 1
        db.commit()

    log.info("Đã seed %d giao dịch.", inserted)
    return inserted


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed DB cho demo risk scoring")
    parser.add_argument(
        "--limit",
        type=int,
        default=config.SEED_LIMIT,
        help=f"số giao dịch (mặc định {config.SEED_LIMIT}, đổi bằng biến SEED_LIMIT)",
    )
    parser.add_argument("--reset", action="store_true", help="drop bảng trước khi seed")
    args = parser.parse_args()
    seed(limit=args.limit, reset=args.reset)


if __name__ == "__main__":
    main()
