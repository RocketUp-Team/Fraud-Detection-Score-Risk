"""Endpoints giao dịch: list (filter/sort/pagination), detail, review, import CSV.

Shape response theo `docs/API_CONTRACT.md`.
"""
import csv
import io
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import config, risk, schemas
from ..db import get_db
from ..models import Review, Transaction
from ..service import split_features, upsert_scored_transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])

SortField = Literal["risk_score", "-risk_score", "scored_at", "-scored_at"]

_SORT_COLUMNS = {
    "risk_score": Transaction.risk_score.asc(),
    "-risk_score": Transaction.risk_score.desc(),
    "scored_at": Transaction.scored_at.asc(),
    "-scored_at": Transaction.scored_at.desc(),
}


@router.get("", response_model=schemas.PaginatedTransactions)
def list_transactions(
    db: Session = Depends(get_db),
    risk_band: schemas.RiskBand | None = None,
    decision: schemas.Decision | None = None,
    review_status: schemas.ReviewStatus | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
    search: str | None = None,
    sort: SortField = "-risk_score",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> schemas.PaginatedTransactions:
    stmt = select(Transaction).options(selectinload(Transaction.review))

    if risk_band:
        stmt = stmt.where(Transaction.risk_band == risk_band)
    if decision:
        stmt = stmt.where(Transaction.decision == decision)
    if min_score is not None:
        stmt = stmt.where(Transaction.risk_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(Transaction.risk_score <= max_score)
    if search:
        if not search.isdigit():
            # Hợp đồng nói `search` khớp transaction_id — chuỗi không phải số
            # thì không có gì khớp, trả rỗng thay vì lỗi 500.
            return schemas.PaginatedTransactions(items=[], total=0, page=page, page_size=page_size)
        stmt = stmt.where(Transaction.transaction_id == int(search))

    if review_status == "pending":
        # Chưa có bản ghi review nào -> pending.
        stmt = stmt.where(~Transaction.review.has())
    elif review_status in ("approved", "rejected"):
        stmt = stmt.where(Transaction.review.has(Review.status == review_status))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(_SORT_COLUMNS[sort], Transaction.transaction_id.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = db.scalars(stmt).all()

    return schemas.PaginatedTransactions(
        items=[schemas.TransactionOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=schemas.StatsOut)
def stats(db: Session = Depends(get_db)) -> schemas.StatsOut:
    """Số liệu tổng quan cho KPI row. Tính bằng aggregate trong SQL, không kéo
    hết bảng về Python."""
    total = db.scalar(select(func.count()).select_from(Transaction)) or 0
    pending = (
        db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(~Transaction.review.has())
        )
        or 0
    )
    avg_score = db.scalar(select(func.avg(Transaction.risk_score))) or 0

    counts = dict(
        db.execute(
            select(Transaction.risk_band, func.count()).group_by(Transaction.risk_band)
        ).all()
    )
    # Band nào không có giao dịch vẫn trả 0 để frontend không phải đoán.
    by_band = [
        schemas.BandCount(band=band, count=int(counts.get(band, 0)))
        for band, _, _ in risk.BANDS
    ]

    high_risk_amount = (
        db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.risk_band.in_(["high", "critical"])
            )
        )
        or 0
    )

    return schemas.StatsOut(
        total=total,
        pending_review=pending,
        by_band=by_band,
        avg_risk_score=round(float(avg_score), 1),
        high_risk_amount=float(high_risk_amount),
    )


def _get_or_404(db: Session, transaction_id: int) -> Transaction:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
    return txn


@router.get("/{transaction_id}", response_model=schemas.TransactionDetailOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    return schemas.TransactionDetailOut.model_validate(_get_or_404(db, transaction_id))


@router.post("/{transaction_id}/review", response_model=schemas.TransactionDetailOut)
def submit_review(
    transaction_id: int,
    payload: schemas.ReviewRequest,
    db: Session = Depends(get_db),
):
    """Người rà soát duyệt/từ chối + gắn nhãn. Gọi lại sẽ ghi đè review cũ."""
    txn = _get_or_404(db, transaction_id)
    status = "approved" if payload.action == "approve" else "rejected"

    if txn.review is None:
        txn.review = Review(transaction_id=transaction_id, status=status)
    txn.review.status = status
    txn.review.label = payload.label
    txn.review.reviewer = payload.reviewer
    txn.review.note = payload.note
    txn.review.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(txn)
    return schemas.TransactionDetailOut.model_validate(txn)


def _coerce(value: str) -> str | float | None:
    """CSV đọc ra toàn string — đổi về số khi được, rỗng thành None."""
    if value == "" or value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return value


@router.post("/import", response_model=schemas.ImportResponse)
def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import CSV theo `DATA_DICTIONARY.md`, chấm điểm từng dòng rồi ghi DB.

    Bắt buộc có cột `TransactionID`. Dòng lỗi được bỏ qua và báo lại trong
    `errors`, không làm hỏng cả batch.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Chỉ nhận file .csv")

    try:
        text = file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File không phải UTF-8") from None

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "TransactionID" not in reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV thiếu cột TransactionID")

    imported = 0
    errors: list[schemas.ImportError_] = []

    for line_no, raw in enumerate(reader, start=2):  # dòng 1 là header
        if imported + len(errors) >= config.MAX_IMPORT_ROWS:
            errors.append(
                schemas.ImportError_(
                    row=line_no,
                    error=f"Vượt giới hạn {config.MAX_IMPORT_ROWS} dòng/lần import — đã dừng.",
                )
            )
            break
        try:
            # Savepoint cho từng dòng: dòng lỗi chỉ rollback chính nó, không
            # xoá những dòng đã ghi trước đó trong cùng batch.
            with db.begin_nested():
                row = {k: _coerce(v) for k, v in raw.items() if k}
                txn_id, features = split_features(row)
                if txn_id is None:
                    raise ValueError("TransactionID rỗng")
                upsert_scored_transaction(db, txn_id, features)
            imported += 1
        except Exception as exc:  # noqa: BLE001 — 1 dòng lỗi không dừng cả file
            errors.append(schemas.ImportError_(row=line_no, error=str(exc)))

    db.commit()
    return schemas.ImportResponse(imported=imported, failed=len(errors), errors=errors[:50])
