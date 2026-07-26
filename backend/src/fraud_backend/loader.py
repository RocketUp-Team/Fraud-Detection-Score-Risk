"""Nạp dữ liệu theo lô: đọc parquet -> chấm điểm -> ghi DB, có báo tiến độ.

Chạy trong BackgroundTasks của FastAPI. Hàm là `def` thường (không `async`) nên
FastAPI đẩy nó ra threadpool — vòng lặp event không bị chặn, API vẫn trả lời
được trong lúc nạp.
"""
import logging

from .datasets import read_rows
from .db import SessionLocal
from .jobs import registry
from .service import split_features, upsert_scored_transaction

log = logging.getLogger(__name__)

# Commit theo lô: commit từng dòng thì chậm gấp nhiều lần, còn commit một lần ở
# cuối thì huỷ giữa đường là mất trắng và tiến độ không phản ánh dữ liệu thật.
COMMIT_EVERY = 250


def run_load(job_id: str, dataset: str, limit: int) -> None:
    processed = 0
    try:
        rows = read_rows(dataset, limit)
        with SessionLocal() as db:
            for row in rows:
                if registry.cancel_requested(job_id):
                    db.commit()  # giữ lại phần đã chấm, không bỏ đi
                    log.info("Job %s bị huỷ sau %d dòng", job_id, processed)
                    return

                txn_id, features = split_features(row)
                if txn_id is None:
                    continue
                upsert_scored_transaction(db, txn_id, features)
                processed += 1

                if processed % COMMIT_EVERY == 0:
                    db.commit()
                    registry.advance(job_id, processed)
            db.commit()
        registry.advance(job_id, processed)
        registry.finish(job_id)
        log.info("Job %s xong: %d giao dịch", job_id, processed)
    except Exception as exc:
        log.exception("Job %s lỗi", job_id)
        registry.advance(job_id, processed)
        registry.finish(job_id, error=str(exc))
