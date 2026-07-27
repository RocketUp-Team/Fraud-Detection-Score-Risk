"""Smoke test API trên SQLite in-memory, không cần Postgres và không cần
model thật (scorer tự rơi về fallback nếu thiếu artifact)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from fraud_backend.db import Base, SessionLocal, engine  # noqa: E402
from fraud_backend.main import app  # noqa: E402
from fraud_backend.service import upsert_scored_transaction  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for i, amt in enumerate([25.0, 480.0, 9500.0]):
            upsert_scored_transaction(
                db,
                2987000 + i,
                {"TransactionAmt": amt, "ProductCD": "W", "card4": "visa"},
            )
        db.commit()
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_meta_tra_ve_du_5_band(client: TestClient) -> None:
    body = client.get("/meta").json()
    assert [b["band"] for b in body["bands"]] == [
        "low",
        "guarded",
        "medium",
        "high",
        "critical",
    ]
    assert body["bands"][0]["min"] == 0
    assert body["bands"][-1]["max"] == 100


def test_list_co_pagination_va_review_status(client: TestClient) -> None:
    body = client.get("/transactions?page_size=2").json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert all(item["review_status"] == "pending" for item in body["items"])
    # Mặc định sort -risk_score: điểm giảm dần.
    scores = [i["risk_score"] for i in body["items"]]
    assert scores == sorted(scores, reverse=True)


def test_search_khong_phai_so_tra_rong_khong_loi(client: TestClient) -> None:
    res = client.get("/transactions?search=abc")
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_stats_khong_bi_hieu_thanh_transaction_id(client: TestClient) -> None:
    """`/transactions/stats` phải khai báo trước `/{transaction_id}` — nếu sai
    thứ tự, FastAPI parse 'stats' thành int và trả 422."""
    res = client.get("/transactions/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert body["pending_review"] == 3
    assert [b["band"] for b in body["by_band"]] == [
        "low",
        "guarded",
        "medium",
        "high",
        "critical",
    ]
    assert sum(b["count"] for b in body["by_band"]) == 3
    assert 0 <= body["avg_risk_score"] <= 100


def test_stats_pending_giam_sau_khi_review(client: TestClient) -> None:
    before = client.get("/transactions/stats").json()["pending_review"]
    client.post("/transactions/2987000/review", json={"action": "approve", "label": "legit"})
    assert client.get("/transactions/stats").json()["pending_review"] == before - 1


def test_detail_404_khi_khong_ton_tai(client: TestClient) -> None:
    assert client.get("/transactions/999999").status_code == 404


def test_review_ghi_nhan_va_doi_review_status(client: TestClient) -> None:
    res = client.post(
        "/transactions/2987000/review",
        json={"action": "reject", "label": "fraud", "reviewer": "long", "note": "thẻ lạ"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["review_status"] == "rejected"
    assert body["review"]["label"] == "fraud"
    assert body["review"]["reviewer"] == "long"

    # Filter theo review_status phải thấy ngay.
    listed = client.get("/transactions?review_status=rejected").json()
    assert [i["transaction_id"] for i in listed["items"]] == [2987000]
    # Và ca này không còn trong hàng chờ pending.
    pending = client.get("/transactions?review_status=pending").json()
    assert 2987000 not in [i["transaction_id"] for i in pending["items"]]


def test_review_goi_lai_thi_ghi_de(client: TestClient) -> None:
    payload = {"action": "reject", "label": "fraud"}
    client.post("/transactions/2987000/review", json=payload)
    res = client.post(
        "/transactions/2987000/review", json={"action": "approve", "label": "legit"}
    )
    assert res.json()["review"]["status"] == "approved"
    assert res.json()["review"]["label"] == "legit"


def test_score_endpoint_khong_ghi_db(client: TestClient) -> None:
    before = client.get("/transactions").json()["total"]
    body = client.post("/score", json={"features": {"TransactionAmt": 4899.0}}).json()
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_band"] in {"low", "guarded", "medium", "high", "critical"}
    assert client.get("/transactions").json()["total"] == before


def test_import_csv(client: TestClient) -> None:
    csv_body = "TransactionID,TransactionAmt,ProductCD\n3000001,120.5,W\n3000002,khong-phai-so,C\n"
    res = client.post(
        "/transactions/import",
        files={"file": ("batch.csv", csv_body, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    # Dòng 2 có amount không phải số -> _coerce giữ nguyên string, model vẫn
    # chấm được; điều cần đảm bảo là không dòng nào làm sập cả batch.
    assert body["imported"] + body["failed"] == 2


def test_import_thieu_cot_transaction_id(client: TestClient) -> None:
    res = client.post(
        "/transactions/import",
        files={"file": ("bad.csv", "TransactionAmt\n10\n", "text/csv")},
    )
    assert res.status_code == 422
    assert "TransactionID" in res.json()["detail"]
