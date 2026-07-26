"""Nạp dữ liệu từ bộ IEEE-CIS đã tiền xử lý, điều khiển từ giao diện.

Chạy nền + poll tiến độ thay vì làm đồng bộ trong request: nạp 50 nghìn dòng
mất vài phút, giữ một request HTTP mở suốt thời gian đó thì reverse proxy sẽ cắt
và người dùng không thấy gì đang xảy ra.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import datasets, schemas
from ..db import Base, engine
from ..jobs import registry
from ..loader import run_load

router = APIRouter(tags=["data"])


@router.get("/datasets", response_model=list[schemas.DatasetOut])
def list_datasets() -> list[schemas.DatasetOut]:
    """Các bộ có trong `model_ready/` kèm số dòng, để giao diện biết tối đa nạp
    được bao nhiêu và bộ nào nên dùng."""
    return [schemas.DatasetOut(**d) for d in datasets.available()]


def _job_out(job) -> schemas.JobOut:
    return schemas.JobOut(
        id=job.id,
        status=job.status,
        processed=job.processed,
        total=job.total,
        percent=job.percent,
        error=job.error,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post("/data/load", response_model=schemas.JobOut, status_code=202)
def start_load(payload: schemas.LoadRequest, background: BackgroundTasks) -> schemas.JobOut:
    available = {d["name"]: d for d in datasets.available()}
    if not available:
        raise HTTPException(
            status_code=409,
            detail="Chưa có dữ liệu đã tiền xử lý. Chạy pipeline của An trước "
            "(xem README_DATA_PIPELINE.md).",
        )
    if payload.dataset not in available:
        raise HTTPException(
            status_code=422,
            detail=f"Không có bộ '{payload.dataset}'. Đang có: {', '.join(available)}.",
        )

    total_rows = available[payload.dataset]["rows"]
    # Xin nhiều hơn số dòng thật thì cắt xuống, không báo lỗi.
    limit = min(payload.limit, total_rows)

    try:
        job = registry.start(total=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if payload.reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    background.add_task(run_load, job.id, payload.dataset, limit)
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str) -> schemas.JobOut:
    job = registry.get(job_id)
    if job is None:
        # Registry ở trong bộ nhớ nên restart backend là mất job — nói rõ để
        # người dùng không tưởng job biến mất một cách bí ẩn.
        raise HTTPException(
            status_code=404,
            detail="Không thấy job này (backend có thể đã khởi động lại).",
        )
    return _job_out(job)


@router.get("/jobs/active/current", response_model=schemas.JobOut | None)
def get_active_job() -> schemas.JobOut | None:
    """Cho giao diện nối lại thanh tiến độ sau khi F5 giữa lúc đang nạp."""
    job = registry.active()
    return _job_out(job) if job else None


@router.post("/jobs/{job_id}/cancel", response_model=schemas.JobOut)
def cancel_job(job_id: str) -> schemas.JobOut:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không thấy job này.")
    if not registry.request_cancel(job_id):
        raise HTTPException(status_code=409, detail=f"Job đã ở trạng thái '{job.status}'.")
    return _job_out(job)
