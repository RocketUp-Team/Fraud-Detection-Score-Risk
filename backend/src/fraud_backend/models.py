"""Bảng DB. Dùng JSON generic (không JSONB) để chạy được cả Postgres và
SQLite — SQLite là đường chạy nhanh khi không có Docker (xem config.py)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    # Dùng TransactionID gốc của IEEE-CIS làm khoá chính (contract yêu cầu giữ
    # nguyên key này — xem RISK_SCORE_DATA_CONTRACT.md), không sinh id mới.
    transaction_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fraud_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(16), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # Feature thô đã dùng để chấm điểm, giữ lại để màn chi tiết hiển thị được
    # và để chấm lại khi đổi model.
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    # None khi model fallback (baseline LogReg không có SHAP) — xem score.py.
    shap_top5: Mapped[list | None] = mapped_column(JSON, nullable=True)

    review: Mapped["Review | None"] = relationship(
        back_populates="transaction", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_transactions_risk_score", "risk_score"),
        Index("ix_transactions_risk_band", "risk_band"),
        Index("ix_transactions_scored_at", "scored_at"),
    )

    @property
    def review_status(self) -> str:
        return self.review.status if self.review else "pending"


class Review(Base):
    """Quyết định của *người* rà soát — tách khỏi `Transaction.decision` là
    quyết định tự động của hệ thống theo band."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.transaction_id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # approved | rejected
    label: Mapped[str | None] = mapped_column(String(16), nullable=True)  # fraud | legit
    reviewer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    transaction: Mapped[Transaction] = relationship(back_populates="review")
