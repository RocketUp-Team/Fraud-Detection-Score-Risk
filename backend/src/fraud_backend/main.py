"""FastAPI stub — scaffold Ngày 1 (Trung).

Chỉ có health check + mock endpoints để docker-compose full stack chạy được
từ đầu (xem docs/RISK_SCORING_PLAN.md mục 5 — làm song song với mock/stub
trước, tích hợp thật Ngày 5). CRUD/DB/scoring thật do Trung xây tiếp.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Fraud Detection Risk Scoring API")


class Transaction(BaseModel):
    id: int
    amount: float
    risk_score: int
    decision: str


MOCK_TRANSACTIONS = [
    Transaction(id=1, amount=129.99, risk_score=12, decision="approve"),
    Transaction(id=2, amount=4899.00, risk_score=87, decision="review"),
]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/transactions", response_model=list[Transaction])
def list_transactions() -> list[Transaction]:
    return MOCK_TRANSACTIONS


@app.get("/transactions/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int) -> Transaction:
    for tx in MOCK_TRANSACTIONS:
        if tx.id == transaction_id:
            return tx
    raise HTTPException(status_code=404, detail="Transaction not found")
