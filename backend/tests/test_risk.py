"""Bands là hợp đồng với frontend (docs/API_CONTRACT.md) — test chặn thay đổi
âm thầm, nhất là ở biên."""
import pytest

from fraud_backend import risk


@pytest.mark.parametrize(
    ("proba", "score", "band", "decision"),
    [
        (0.0, 0, "low", "approve"),
        (0.194, 19, "low", "approve"),
        (0.20, 20, "guarded", "approve"),
        (0.395, 40, "medium", "review"),
        (0.599, 60, "high", "review"),
        (0.795, 80, "critical", "reject"),
        (1.0, 100, "critical", "reject"),
    ],
)
def test_classify_bands(proba: float, score: int, band: str, decision: str) -> None:
    assert risk.classify(proba) == (score, band, decision)


@pytest.mark.parametrize("proba", [-0.5, 1.7, 42.0])
def test_score_luon_nam_trong_0_100(proba: float) -> None:
    """Proba lỗi không được tạo ra band lạ hay ném lỗi 500."""
    score, band, _ = risk.classify(proba)
    assert 0 <= score <= 100
    assert band in {b for b, _, _ in risk.BANDS}


def test_bands_phu_kin_0_100_khong_ho_khong_chong_lan() -> None:
    covered = sorted((lo, hi) for _, lo, hi in risk.BANDS)
    assert covered[0][0] == 0
    assert covered[-1][1] == 100
    for (_, prev_hi), (next_lo, _) in zip(covered, covered[1:]):
        assert next_lo == prev_hi + 1
