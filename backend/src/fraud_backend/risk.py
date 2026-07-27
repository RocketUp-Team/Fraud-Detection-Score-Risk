"""Chuyển fraud_probability -> risk_score -> risk_band -> decision.

Bands theo `RISK_SCORE_DATA_CONTRACT.md`. Backend là nơi duy nhất tính band —
frontend chỉ hiển thị (xem `docs/API_CONTRACT.md`), tránh hai phía lệch logic.
"""
from typing import Literal

RiskBand = Literal["low", "guarded", "medium", "high", "critical"]
Decision = Literal["approve", "review", "reject"]

# (band, min, max) — max inclusive, phủ kín 0..100 không hở.
BANDS: list[tuple[RiskBand, int, int]] = [
    ("low", 0, 19),
    ("guarded", 20, 39),
    ("medium", 40, 59),
    ("high", 60, 79),
    ("critical", 80, 100),
]

_BAND_DECISION: dict[RiskBand, Decision] = {
    "low": "approve",
    "guarded": "approve",
    "medium": "review",
    "high": "review",
    "critical": "reject",
}


def to_risk_score(fraud_probability: float) -> int:
    """round(proba * 100), clamp về [0, 100] để proba lỗi không tạo score lạ."""
    return max(0, min(100, round(fraud_probability * 100)))


def to_band(risk_score: int) -> RiskBand:
    for band, lo, hi in BANDS:
        if lo <= risk_score <= hi:
            return band
    # Không xảy ra vì to_risk_score đã clamp, nhưng không trả None âm thầm.
    raise ValueError(f"risk_score ngoài [0, 100]: {risk_score}")


def to_decision(band: RiskBand) -> Decision:
    return _BAND_DECISION[band]


def classify(fraud_probability: float) -> tuple[int, RiskBand, Decision]:
    """Tiện dụng: proba -> (risk_score, risk_band, decision)."""
    score = to_risk_score(fraud_probability)
    band = to_band(score)
    return score, band, to_decision(band)
