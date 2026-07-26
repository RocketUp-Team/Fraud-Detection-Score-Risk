"""Đọc các bộ parquet `model_ready` của An.

Dùng cho cả `seed.py` (CLI) và endpoint nạp dữ liệu từ giao diện.

Mọi thông tin về từng bộ đều SUY RA TỪ DỮ LIỆU, không viết cứng danh sách tên:
số dòng đọc từ metadata parquet, tỉ lệ gian lận đọc từ cột `isFraud`, phân bố
gốc lấy từ `manifest.json`. Nhờ vậy An thêm split mới thì nó tự xuất hiện kèm
nhận định đúng, không cần sửa code.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# datasets.py -> fraud_backend -> src -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "ieee_cis_fraud_risk"
MODEL_READY_DIR = PROCESSED_DIR / "model_ready"
MANIFEST_PATH = PROCESSED_DIR / "manifest.json"

LABEL_COL = "isFraud"

# Sai số cho phép khi so tỉ lệ gian lận của một bộ với phân bố gốc. 0,5 điểm
# phần trăm: chênh do chia split ngẫu nhiên thì nhỏ hơn nhiều, còn undersample
# thì lệch hàng chục điểm nên không có vùng xám.
NATURAL_RATE_TOLERANCE = 0.005

# Cache theo (đường dẫn, mtime) để không đọc lại parquet mỗi lần gọi /datasets.
_cache: dict[tuple[str, int], dict] = {}


def _manifest() -> dict:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Không đọc được manifest (%s) — bỏ phần so sánh phân bố gốc.", exc)
        return {}


def baseline_fraud_rate() -> float | None:
    """Tỉ lệ gian lận của toàn bộ dữ liệu gốc, theo manifest của An."""
    rate = _manifest().get("imbalance", {}).get("fraud_rate")
    return float(rate) if rate is not None else None


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:] + "."


def _describe(directory: Path, baseline: float | None) -> dict | None:
    """Số liệu thật của một bộ. Trả None nếu thư mục không có parquet."""
    import pyarrow.parquet as pq

    files = sorted(directory.rglob("*.parquet"))
    if not files:
        return None

    rows = 0
    fraud = 0
    has_labels = LABEL_COL in pq.ParquetFile(files[0]).schema_arrow.names

    for path in files:
        pf = pq.ParquetFile(path)
        rows += pf.metadata.num_rows
        if has_labels:
            # Chỉ đọc đúng một cột — nhanh, không nạp 53 cột vào RAM.
            fraud += int(sum(pf.read(columns=[LABEL_COL])[LABEL_COL].to_pylist()))

    fraud_rate = fraud / rows if has_labels and rows else None

    # "Model đã học trên bộ này chưa" suy từ manifest: An ghi bộ khuyến nghị để
    # train, và các bộ train khác cùng tiền tố. Không dựa vào tên cứng.
    trained_hint = _manifest().get("downstream_recommended_dataset", "")
    train_prefix = Path(trained_hint).name.split("_")[0] if trained_hint else "train"
    model_trained_on = directory.name.startswith(train_prefix)

    natural = (
        fraud_rate is not None
        and baseline is not None
        and abs(fraud_rate - baseline) <= NATURAL_RATE_TOLERANCE
    )

    # Nên dùng để nạp lên dashboard khi: có nhãn để đối chiếu, model chưa học
    # trên đó, và phân bố còn tự nhiên.
    recommended = bool(has_labels and not model_trained_on and natural)

    reasons = []
    if not has_labels:
        reasons.append(f"không có cột {LABEL_COL} nên không đối chiếu được dự đoán với thực tế")
    else:
        reasons.append(f"{fraud_rate * 100:.2f}% gian lận")
        if baseline is not None:
            reasons.append(
                "khớp phân bố gốc"
                if natural
                else f"lệch phân bố gốc ({baseline * 100:.2f}%) — đã resample"
            )
    reasons.append(
        "model ĐÃ học trên bộ này nên điểm sẽ đẹp giả tạo"
        if model_trained_on
        else "model chưa từng thấy bộ này"
    )

    return {
        "name": directory.name,
        "rows": rows,
        "recommended": recommended,
        # Chỉ hoa chữ đầu — `capitalize()` sẽ hạ cả `isFraud` thành `isfraud`.
        "note": _sentence(", ".join(reasons)),
        "fraud_rate": fraud_rate,
        "has_labels": has_labels,
        "model_trained_on": model_trained_on,
    }


def available() -> list[dict]:
    """Danh sách bộ dữ liệu kèm số liệu suy ra từ chính dữ liệu."""
    if not MODEL_READY_DIR.exists():
        return []
    try:
        import pyarrow.parquet  # noqa: F401 — chỉ kiểm tra có cài hay không
    except ImportError:
        log.warning("Không có pyarrow — không đọc được parquet.")
        return []

    baseline = baseline_fraud_rate()
    out = []
    for directory in sorted(p for p in MODEL_READY_DIR.iterdir() if p.is_dir()):
        key = (str(directory), directory.stat().st_mtime_ns)
        if key not in _cache:
            described = _describe(directory, baseline)
            if described is None:
                continue
            _cache[key] = described
        out.append(_cache[key])

    # Bộ nên dùng lên trước để người dùng không phải tự đọc hết ghi chú.
    return sorted(out, key=lambda d: (not d["recommended"], d["name"]))


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


def read_random_rows(dataset: str, limit: int, seed: int = 42) -> list[dict]:
    """Mẫu ngẫu nhiên `limit` dòng rải đều toàn bộ bộ dữ liệu.

    Khác `read_rows` (lấy N dòng ĐẦU, tức một khối liền trong 1-2 file part nên
    không đại diện): ở đây bốc chỉ số ngẫu nhiên trên toàn bộ rồi mới đọc.

    `seed` cố định để nạp lại ra đúng mẫu cũ — demo cần tái lập được. Mỗi file
    parquet chỉ mở một lần và đọc lần lượt, không nạp cả bộ vào RAM.
    """
    import random

    import pandas as pd
    import pyarrow.parquet as pq

    directory = MODEL_READY_DIR / dataset
    files = sorted(directory.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Không có parquet nào trong {directory}")

    # Số dòng từng file, đọc từ metadata nên không tốn gì.
    counts = [pq.ParquetFile(f).metadata.num_rows for f in files]
    total = sum(counts)
    take = min(limit, total)

    picked = sorted(random.Random(seed).sample(range(total), take))

    frames = []
    offset = 0
    cursor = 0
    for path, count in zip(files, counts, strict=True):
        # Các chỉ số toàn cục thuộc file này -> đổi sang chỉ số trong file.
        local = []
        while cursor < len(picked) and picked[cursor] < offset + count:
            local.append(picked[cursor] - offset)
            cursor += 1
        if local:
            frames.append(pd.read_parquet(path).iloc[local])
        offset += count

    df = pd.concat(frames) if frames else pd.DataFrame()
    log.info(
        "Đọc mẫu ngẫu nhiên %d/%d dòng từ %s (seed=%d)", len(df), total, directory, seed
    )
    return df.to_dict(orient="records")
