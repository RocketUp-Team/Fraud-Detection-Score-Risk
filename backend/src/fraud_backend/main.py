"""FastAPI app — Risk Scoring Engine.

Đã tích hợp model thật của Quân qua `fraud_model.score` (điểm bàn giao Ngày 5,
xem docs/RISK_SCORING_PLAN.md mục 2). Hợp đồng API: docs/API_CONTRACT.md.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, risk, schemas
from .db import Base, engine
from .routers import data, transactions
from .scoring import scorer
from .service import score_features

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo 8 ngày: tạo schema trực tiếp, không Alembic (xem db.py).
    Base.metadata.create_all(bind=engine)
    # Load model + SHAP explainer trước khi nhận request đầu tiên.
    scorer.load()
    yield


app = FastAPI(title="Fraud Detection Risk Scoring API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if config.CORS_ALLOW_ALL else config.CORS_ORIGINS,
    allow_origin_regex=".*" if config.CORS_ALLOW_ALL else None,
    allow_credentials=not config.CORS_ALLOW_ALL,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(data.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meta", response_model=schemas.MetaOut)
def meta() -> schemas.MetaOut:
    info = scorer.info
    return schemas.MetaOut(
        model_version=info["model_version"],
        model_name=info["model_name"],
        processing_version=info.get("processing_version"),
        feature_schema_version=info.get("feature_schema_version"),
        explainability=info["explainability"],
        n_features=info.get("n_features", 0),
        required_features=info.get("required_features", []),
        optional_features=info.get("optional_features", []),
        defaultable_features=info.get("defaultable_features", []),
        bands=[schemas.BandRange(band=b, min=lo, max=hi) for b, lo, hi in risk.BANDS],
        warning=info.get("warning"),
    )


@app.post("/score", response_model=schemas.ScoreResponse, tags=["scoring"])
def score_transaction(payload: schemas.ScoreRequest) -> schemas.ScoreResponse:
    """Chấm điểm ad-hoc, KHÔNG ghi DB — dùng cho demo nhập giao dịch mới."""
    return schemas.ScoreResponse(**score_features(payload.features))
