"""Nạp dữ liệu theo lô: đọc parquet -> chấm điểm -> ghi DB, có báo tiến độ.

Chạy trong BackgroundTasks của FastAPI. Hàm là `def` thường (không `async`) nên
FastAPI đẩy nó ra threadpool — vòng lặp event không bị chặn, API vẫn trả lời
được trong lúc nạp.
"""
import logging

from sqlalchemy import delete

from .datasets import read_random_rows, read_rows
from .db import SessionLocal
from .jobs import registry
from .models import Transaction
from .service import split_features, upsert_scored_transaction

log = logging.getLogger(__name__)

# Commit theo lô: commit từng dòng thì chậm gấp nhiều lần, còn commit một lần ở
# cuối thì huỷ giữa đường là mất trắng và tiến độ không phản ánh dữ liệu thật.
COMMIT_EVERY = 250


def run_load(
    job_id: str,
    dataset: str,
    limit: int,
    reset: bool = False,
    sample: bool = False,
    seed: int = 42,
) -> None:
    processed = 0
    try:
        # Đọc parquet TRƯỚC khi xoá. Xoá trước rồi mới đọc là cách chắc chắn nhất
        # để mất dữ liệu cũ mà chẳng nạp được gì khi parquet lỗi.
        rows = read_random_rows(dataset, limit, seed) if sample else read_rows(dataset, limit)
        with SessionLocal() as db:
            if reset:
                db.execute(delete(Transaction))
                log.info("Job %s: xoá dữ liệu cũ theo yêu cầu", job_id)
            for row in rows:
                if registry.cancel_requested(job_id):
                    db.commit()  # giữ lại phần đã chấm, không bỏ đi
                    registry.advance(job_id, processed)
                    log.info("Job %s bị huỷ sau %d dòng", job_id, processed)
                    return

                txn_id, features = split_features(row)
                if txn_id is None:
                    continue
                upsert_scored_transaction(db, txn_id, features)
                processed += 1
                # Đếm từng dòng (chỉ gán int) để số báo ra luôn khớp thực tế;
                # trước đây chỉ đếm mỗi 250 dòng nên job huỷ giữa hai mốc báo
                # "0 dòng" dù đã ghi được vài trăm.
                registry.advance(job_id, processed)

                if processed % COMMIT_EVERY == 0:
                    db.commit()
            db.commit()
        registry.advance(job_id, processed)
        registry.finish(job_id)
        log.info("Job %s xong: %d giao dịch", job_id, processed)
    except Exception as exc:
        log.exception("Job %s lỗi", job_id)
        registry.advance(job_id, processed)
        registry.finish(job_id, error=str(exc))


# Quét tối đa bao nhiêu dòng để tìm đủ ca cho mỗi band. Band `critical` chỉ
# chiếm ~3% nên muốn 20 ca phải quét ~700 dòng; 40.000 là mức trần rộng rãi để
# không quét vô hạn khi một band gần như không xuất hiện.
COVERAGE_SCAN_CAP = 40_000


def run_coverage_load(
    job_id: str,
    dataset: str,
    per_band: int,
    reset: bool = False,
) -> None:
    """Nạp một bộ ca demo có ĐỦ 5 mức rủi ro, mỗi mức `per_band` ca.

    Chấm lần lượt và chỉ giữ dòng thuộc band còn thiếu. Kết quả là bộ nhỏ mà đi
    hết được các trường hợp — khác với nạp N dòng đầu, ở đó `critical` chỉ chiếm
    ~3% nên rất dễ không có ca nào để trình bày.
    """
    from . import risk
    from .service import score_features

    targets = {band: per_band for band, _, _ in risk.BANDS}
    kept = {band: 0 for band in targets}
    processed = 0
    scanned = 0

    try:
        rows = read_rows(dataset, COVERAGE_SCAN_CAP)
        with SessionLocal() as db:
            if reset:
                db.execute(delete(Transaction))
                log.info("Job %s: xoá dữ liệu cũ theo yêu cầu", job_id)

            for row in rows:
                if registry.cancel_requested(job_id):
                    db.commit()
                    registry.advance(job_id, processed)
                    return
                if all(kept[b] >= targets[b] for b in targets):
                    break

                scanned += 1
                txn_id, features = split_features(row)
                if txn_id is None:
                    continue

                # Chấm trước để biết band, chỉ ghi nếu band đó còn thiếu ca.
                scored = score_features(features)
                band = scored["risk_band"]
                if kept[band] >= targets[band]:
                    continue

                txn = db.get(Transaction, txn_id) or Transaction(transaction_id=txn_id)
                if txn not in db:
                    db.add(txn)
                txn.amount = float(features.get("TransactionAmt") or 0.0)
                txn.features = features
                for field, value in scored.items():
                    setattr(txn, field, value)

                kept[band] += 1
                processed += 1
                registry.advance(job_id, processed)
                if processed % COMMIT_EVERY == 0:
                    db.commit()
            db.commit()

        registry.advance(job_id, processed)
        registry.finish(job_id)
        log.info(
            "Job %s xong: %d giao dịch (quét %d dòng) — %s",
            job_id,
            processed,
            scanned,
            ", ".join(f"{b}={n}" for b, n in kept.items()),
        )
    except Exception as exc:
        log.exception("Job %s lỗi", job_id)
        registry.advance(job_id, processed)
        registry.finish(job_id, error=str(exc))
