"""Đọc các bộ parquet `model_ready` của An.

Dùng cho cả `seed.py` (CLI) và endpoint nạp dữ liệu từ giao diện.
"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# datasets.py -> fraud_backend -> src -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_READY_DIR = REPO_ROOT / "data" / "processed" / "ieee_cis_fraud_risk" / "model_ready"

# Bộ nào an toàn để nạp lên dashboard. `train_*` thì model ĐÃ học trên đó nên
# điểm đẹp giả tạo, và `train_balanced` còn bị undersample tới ~20% gian lận.
SAFE_DATASETS = {"holdout", "validation"}

DATASET_NOTES = {
    "holdout": "Model chưa từng thấy, phân bố tự nhiên (~3,5% gian lận). Nên dùng bộ này.",
    "validation": "Dùng khi tuning model, phân bố tự nhiên.",
    "train_original": "Model ĐÃ học trên bộ này — điểm sẽ đẹp giả tạo.",
    "train_weighted": "Model ĐÃ học trên bộ này — điểm sẽ đẹp giả tạo.",
    "train_balanced": "Đã undersample còn ~20% gian lận — dashboard sẽ méo.",
    "kaggle_test": "Không có nhãn isFraud, không đối chiếu được.",
}


def available() -> list[dict]:
    """Danh sách bộ dữ liệu + số dòng. Số dòng đọc từ metadata của parquet nên
    nhanh, không phải load cả file."""
    if not MODEL_READY_DIR.exists():
        return []
    try:
        import pyarrow.parquet as pq
    except ImportError:
        log.warning("Không có pyarrow — không đếm được số dòng.")
        return []

    out = []
    for directory in sorted(p for p in MODEL_READY_DIR.iterdir() if p.is_dir()):
        files = sorted(directory.rglob("*.parquet"))
        if not files:
            continue
        rows = sum(pq.ParquetFile(f).metadata.num_rows for f in files)
        out.append(
            {
                "name": directory.name,
                "rows": rows,
                "recommended": directory.name in SAFE_DATASETS,
                "note": DATASET_NOTES.get(directory.name, ""),
            }
        )
    return out


def read_rows(dataset: str, limit: int) -> list[dict]:
    """Đọc `limit` dòng đầu của một bộ. Chỉ mở đủ số file parquet cần thiết,
    không load cả bộ 500 nghìn dòng vào RAM."""
    import pandas as pd

    directory = MODEL_READY_DIR / dataset
    files = sorted(directory.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Không có parquet nào trong {directory}")

    frames, total = [], 0
    for path in files:
        frames.append(pd.read_parquet(path))
        total += len(frames[-1])
        if total >= limit:
            break
    df = pd.concat(frames).head(limit)
    log.info("Đọc %d dòng từ %s", len(df), directory)
    return df.to_dict(orient="records")
