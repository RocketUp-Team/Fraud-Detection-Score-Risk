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
    processing_version: str | None = None
    feature_schema_version: str | None = None
    explainability: bool
    # Số feature model mong đợi. Frontend dùng để nói rõ "đã cung cấp 9/53",
    # vì chấm ad-hoc chỉ điền được một phần, phần còn lại là giá trị mặc định.
    n_features: int
    required_features: list[str] = []
    optional_features: list[str] = []
    defaultable_features: list[str] = []
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
    scoring_mode: Literal["full_feature", "partial_demo"]
    shap_top5: list[ShapContribution] | None
    model_version: str
    processing_version: str | None = None
    feature_schema_version: str | None = None
    scored_at: datetime


class DatasetOut(BaseModel):
    name: str
    rows: int
    recommended: bool
    note: str
    # Tỉ lệ gian lận thật của bộ; None khi bộ không có cột isFraud.
    fraud_rate: float | None = None
    has_labels: bool = True
    model_trained_on: bool = False


class LoadRequest(BaseModel):
    dataset: str = "holdout"
    # Chặn trên để một cú bấm nhầm không nạp cả nửa triệu dòng.
    limit: int = Field(default=5000, ge=1, le=100_000)
    # Xoá dữ liệu cũ trước khi nạp; mặc định là ghi thêm/ghi đè theo id.
    reset: bool = False
    # `head`: N dòng đầu — nhanh nhất nhưng là một khối liền, không đại diện.
    # `sample`: N dòng ngẫu nhiên rải đều cả bộ, có seed nên tái lập được.
    # `coverage`: bộ nhỏ có đủ 5 mức rủi ro, mỗi mức `per_band` ca.
    mode: Literal["head", "sample", "coverage"] = "head"
    per_band: int = Field(default=20, ge=1, le=500)
    # Cố định để nạp lại ra đúng mẫu cũ; đổi seed để lấy mẫu khác.
    seed: int = Field(default=42, ge=0)


class JobOut(BaseModel):
    id: str
    status: Literal["running", "done", "error", "cancelled"]
    processed: int
    total: int
    percent: int
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class ImportError_(BaseModel):
    row: int
    error: str


class ImportResponse(BaseModel):
    imported: int
    failed: int
    errors: list[ImportError_]
    # Độ khớp cột giữa file và model. CSV thô của Kaggle chỉ có 28/53 cột — 25
    # cột còn lại do pipeline Spark sinh ra, thiếu thì bị điền mặc định và điểm
    # lệch, nên phải nói ra thay vì để người dùng tưởng điểm là chuẩn.
    matched_features: int = 0
    expected_features: int = 0
    missing_features: list[str] = []
