"""Theo dõi tiến độ các việc chạy nền (nạp dữ liệu theo lô).

Registry để trong bộ nhớ, KHÔNG persist. Hệ quả phải biết:
  - restart backend là mất hết job đang chạy và lịch sử job
  - chỉ đúng khi chạy 1 worker uvicorn; nhiều worker thì mỗi process có
    registry riêng, client poll có thể trúng process không giữ job đó

Đủ cho demo. Muốn job sống qua restart và chạy nhiều worker thì phải chuyển
sang queue thật (Redis + arq/celery) — xem backend/README.md.
"""
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Job:
    id: str
    total: int
    processed: int = 0
    status: str = "running"  # running | done | error | cancelled
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    @property
    def percent(self) -> int:
        return round(self.processed / self.total * 100) if self.total else 0


class JobRegistry:
    """Chỉ cho phép MỘT job nạp dữ liệu chạy cùng lúc: hai job cùng ghi vào
    bảng transactions sẽ tranh nhau và tiến độ báo ra vô nghĩa."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active_id: str | None = None

    def start(self, total: int) -> Job:
        with self._lock:
            if self._active_id:
                active = self._jobs[self._active_id]
                if active.status == "running":
                    raise RuntimeError(
                        f"Đang có job nạp dữ liệu chạy ({active.processed}/{active.total}). "
                        "Chờ nó xong đã."
                    )
            job = Job(id=uuid.uuid4().hex[:12], total=total)
            self._jobs[job.id] = job
            self._active_id = job.id
            return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def active(self) -> Job | None:
        with self._lock:
            return self._jobs.get(self._active_id) if self._active_id else None

    def advance(self, job_id: str, processed: int) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.processed = processed

    def finish(self, job_id: str, error: str | None = None) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        job.status = "error" if error else "done"
        job.error = error
        job.finished_at = datetime.now(UTC)

    def cancel_requested(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        return job is not None and job.status == "cancelled"

    def request_cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status == "running":
            job.status = "cancelled"
            return True
        return False


registry = JobRegistry()
