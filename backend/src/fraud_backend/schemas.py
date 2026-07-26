"""Pydantic schemas — phải khớp `docs/API_CONTRACT.md` và
`frontend/src/types/api.ts`. Đổi shape thì sửa cả ba cùng commit."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskBand = Literal["low", "guarded", "medium", "high", "critical"]
Decision = Literal["approve", "review", "reject"]
ReviewStatus = Literal["pending", "approved", "rejected"]
ReviewLabel = Literal["fraud", "legit"]

FeatureValue = str | float | int | None


class ShapContribution(BaseModel):
    feature: str
    shap_value: float


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    amount: float
    fraud_probability: float
    risk_score: int
    risk_band: RiskBand
    decision: Decision
    scored_at: datetime
    model_version: str
    review_status: ReviewStatus


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ReviewStatus
    label: ReviewLabel | None
    reviewer: str | None
    note: str | None
    updated_at: datetime


class TransactionDetailOut(TransactionOut):
    features: dict[str, FeatureValue]
    shap_top5: list[ShapContribution] | None
    review: ReviewOut | None


class PaginatedTransactions(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


class BandRange(BaseModel):
    band: RiskBand
    min: int
    max: int


class MetaOut(BaseModel):
    model_version: str
    model_name: str
    explainability: bool
    # Số feature model mong đợi. Frontend dùng để nói rõ "đã cung cấp 9/53",
    # vì chấm ad-hoc chỉ điền được một phần, phần còn lại là giá trị mặc định.
    n_features: int
    bands: list[BandRange]
    # Chỉ có khi model thật chưa dùng được (xem scoring._HeuristicScorer).
    warning: str | None = None


class BandCount(BaseModel):
    band: RiskBand
    count: int


class StatsOut(BaseModel):
    """Số liệu tổng quan cho KPI row của dashboard."""

    total: int
    pending_review: int
    by_band: list[BandCount]
    avg_risk_score: float
    high_risk_amount: float


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    label: ReviewLabel
    reviewer: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class ScoreRequest(BaseModel):
    features: dict[str, FeatureValue]


class ScoreResponse(BaseModel):
    fraud_probability: float
    risk_score: int
    risk_band: RiskBand
    decision: Decision
    shap_top5: list[ShapContribution] | None
    model_version: str
    scored_at: datetime


class ImportError_(BaseModel):
    row: int
    error: str


class ImportResponse(BaseModel):
    imported: int
    failed: int
    errors: list[ImportError_]
