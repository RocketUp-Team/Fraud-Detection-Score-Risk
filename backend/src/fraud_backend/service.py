"""Logic nghiệp vụ: chấm điểm + ghi DB, dùng chung cho endpoint import,
seed script và (một phần) /score."""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from . import risk
from .models import Transaction
from .scoring import scorer

# Cột không phải feature — loại trước khi đưa vào model (xem DATA_DICTIONARY.md).
NON_FEATURE_COLS = {"TransactionID", "TransactionDT", "isFraud", "class_weight"}


def split_features(row: dict) -> tuple[int | None, dict]:
    """Tách TransactionID khỏi phần feature của 1 dòng dữ liệu thô."""
    txn_id = row.get("TransactionID")
    features = {k: v for k, v in row.items() if k not in NON_FEATURE_COLS}
    return (int(txn_id) if txn_id is not None else None), features


def score_features(features: dict) -> dict:
    """Chấm điểm 1 giao dịch, trả về dict đã đủ field cho API/DB."""
    result = scorer.score(features)
    proba = float(result["proba"])
    score, band, decision = risk.classify(proba)
    return {
        "fraud_probability": proba,
        "risk_score": score,
        "risk_band": band,
        "decision": decision,
        "shap_top5": result.get("shap"),
        "model_version": scorer.info["model_version"],
        "scored_at": datetime.now(UTC),
    }


def upsert_scored_transaction(db: Session, transaction_id: int, features: dict) -> Transaction:
    """Chấm điểm rồi ghi/ghi đè vào DB. Không commit — caller quyết định, để
    import CSV commit 1 lần cho cả batch."""
    scored = score_features(features)
    amount = features.get("TransactionAmt") or 0.0

    txn = db.get(Transaction, transaction_id)
    if txn is None:
        txn = Transaction(transaction_id=transaction_id)
        db.add(txn)

    txn.amount = float(amount)
    txn.features = features
    for field, value in scored.items():
        setattr(txn, field, value)
    return txn
