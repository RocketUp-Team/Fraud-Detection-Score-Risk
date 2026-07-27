"""Cầu nối tới model của Quân (`fraud_model.score`).

Điểm bàn giao Ngày 5 theo `docs/RISK_SCORING_PLAN.md` mục 2: backend import
module Python trực tiếp, không gọi qua network.

Nếu `fraud_model` chưa cài được (thiếu artifact, thiếu dep) thì rơi về
`_HeuristicScorer` để API và frontend vẫn chạy được cho demo — nhưng
`GET /meta` báo rõ `model_name: "unavailable-heuristic"` để không ai tưởng
đó là điểm của model thật.
"""
import hashlib
import logging
import math
import warnings
from typing import Any

log = logging.getLogger(__name__)

# SHAP in cảnh báo này ở MỖI lần gọi TreeExplainer với LightGBM binary. Chấm
# theo lô (seed/import CSV) là lặp hàng trăm dòng, lấp hết log thật. Chỉ là
# thông báo đổi định dạng output — score.py đã xử lý cả hai dạng.
# Phải chặn tại điểm gọi (xem Scorer.score): filter mức module không ăn vì shap
# dùng `warnings.catch_warnings()` bên trong, reset filter của mình.
_SHAP_LGBM_WARNING = ".*LightGBM binary classifier with TreeExplainer.*"


class _HeuristicScorer:
    """Fallback KHÔNG phải model — chỉ để pipeline chạy khi model chưa sẵn.

    Điểm sinh từ hash của TransactionAmt để ổn định giữa các lần gọi (cùng
    input -> cùng điểm), không random.
    """

    name = "unavailable-heuristic"

    def info(self) -> dict:
        return {
            "model_name": self.name,
            "model_version": self.name,
            "processing_version": None,
            "feature_schema_version": None,
            "explainability": False,
            "n_features": 0,
            "required_features": [],
            "optional_features": [],
            "defaultable_features": [],
            "warning": "fraud_model chưa dùng được — điểm dưới đây KHÔNG phải của model thật.",
        }

    def feature_columns(self) -> list[str]:
        """Fallback không có model nên không có danh sách cột nào."""
        return []

    def score(self, features: dict) -> dict:
        amt = features.get("TransactionAmt") or 0.0
        try:
            amt = float(amt)
        except (TypeError, ValueError):
            amt = 0.0
        digest = hashlib.sha256(f"{amt:.2f}".encode()).digest()[0] / 255.0
        # Giao dịch giá trị lớn -> điểm cao hơn, cộng nhiễu tiền định từ hash.
        base = 1 / (1 + math.exp(-(math.log1p(amt) - 6) / 1.5))
        return {
            "proba": min(0.99, max(0.01, 0.7 * base + 0.3 * digest)),
            "shap": None,
            "scoring_mode": "partial_demo",
        }


class Scorer:
    """Wrapper singleton quanh `fraud_model.score`, load 1 lần lúc startup."""

    def __init__(self) -> None:
        self._impl: Any = None
        self._info: dict = {}

    def load(self) -> dict:
        """Gọi trong lifespan của FastAPI. Không raise — lỗi model không được
        làm sập cả API."""
        try:
            from fraud_model import score as model_score

            self._info = model_score.warm_up()
            self._impl = model_score
            log.info("Model đã load: %s", self._info)
        except Exception as exc:  # noqa: BLE001 — muốn bắt mọi lỗi load model
            log.warning("Không load được fraud_model (%s) — dùng fallback heuristic.", exc)
            self._impl = _HeuristicScorer()
            self._info = self._impl.info()
            self._info["error"] = str(exc)
        return self._info

    @property
    def info(self) -> dict:
        if not self._info:
            self.load()
        return self._info

    def feature_columns(self) -> list[str]:
        """Cột feature model mong đợi. Rỗng khi đang chạy fallback heuristic —
        caller phải xử lý được trường hợp đó (vd bỏ phần báo độ khớp)."""
        if self._impl is None:
            self.load()
        getter = getattr(self._impl, "feature_columns", None)
        return list(getter()) if callable(getter) else []

    def score(self, features: dict) -> dict:
        """-> {"proba": float, "shap": [...] | None}"""
        if self._impl is None:
            self.load()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=_SHAP_LGBM_WARNING, category=UserWarning)
            return self._impl.score(features)


scorer = Scorer()
