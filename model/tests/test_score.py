import joblib
import pytest
from lightgbm import LGBMClassifier
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

from fraud_model import config
from fraud_model import score as score_module

FEATURE_COLUMNS = ["TransactionAmt", "C1", "C2", "C3", "C4", "ProductCD"]


@pytest.fixture(autouse=True)
def reset_score_cache():
    """score.py cache model/explainer trong biến module-level — reset giữa
    các test để mỗi test tự load artifact monkeypatch riêng của nó."""
    score_module._artifact = None
    score_module._explainer = None
    yield
    score_module._artifact = None
    score_module._explainer = None


def _make_tree_artifact(path):
    X, y = make_classification(
        n_samples=200, n_features=len(FEATURE_COLUMNS), n_informative=4, random_state=0
    )
    model = LGBMClassifier(n_estimators=20, max_depth=3, verbosity=-1).fit(X, y)
    joblib.dump(
        {
            "model": model,
            "model_name": "lightgbm",
            "feature_columns": FEATURE_COLUMNS,
            "category_mappings": {"ProductCD": {"w": 0, "c": 1, "__MISSING__": 2}},
            "required_features": FEATURE_COLUMNS,
            "defaultable_features": ["ProductCD"],
            "optional_features": [],
        },
        path,
    )


def _make_baseline_artifact(path):
    X, y = make_classification(
        n_samples=100, n_features=2, n_informative=2, n_redundant=0, random_state=0
    )
    model = LogisticRegression().fit(X, y)
    joblib.dump(
        {
            "model": model,
            "model_name": "baseline_logreg",
            "feature_columns": ["TransactionAmt", "C1"],
            "category_mappings": {},
        },
        path,
    )


def test_score_returns_valid_probability_and_top5_shap_for_tree_model(tmp_path, monkeypatch):
    final_path = tmp_path / "final_model.joblib"
    _make_tree_artifact(final_path)
    monkeypatch.setattr(config, "SERVING_FINAL_MODEL_PATH", final_path)
    monkeypatch.setattr(config, "SERVING_MODEL_VERSION", "v2")

    result = score_module.score(
        {"TransactionAmt": 50.0, "C1": 1.0, "C2": 2.0, "C3": 0.0, "C4": -1.0, "ProductCD": "w"}
    )

    assert 0.0 <= result["proba"] <= 1.0
    assert len(result["shap"]) == 5
    for item in result["shap"]:
        assert set(item.keys()) == {"feature", "shap_value"}
        assert item["feature"] in FEATURE_COLUMNS
        assert isinstance(item["shap_value"], float)


def test_score_handles_unseen_categorical_value_without_crashing(tmp_path, monkeypatch):
    final_path = tmp_path / "final_model.joblib"
    _make_tree_artifact(final_path)
    monkeypatch.setattr(config, "SERVING_FINAL_MODEL_PATH", final_path)
    monkeypatch.setattr(config, "SERVING_MODEL_VERSION", "v2")

    result = score_module.score(
        {
            "TransactionAmt": 50.0,
            "C1": 1.0,
            "C2": 2.0,
            "C3": 0.0,
            "C4": -1.0,
            "ProductCD": "NEVER_SEEN_BEFORE",
        }
    )

    assert 0.0 <= result["proba"] <= 1.0


def test_score_rejects_missing_required_full_features(tmp_path, monkeypatch):
    final_path = tmp_path / "final_model.joblib"
    _make_tree_artifact(final_path)
    monkeypatch.setattr(config, "SERVING_FINAL_MODEL_PATH", final_path)
    monkeypatch.setattr(config, "SERVING_MODEL_VERSION", "v2")

    with pytest.raises(ValueError, match="Thiếu required features"):
        score_module.score({"TransactionAmt": 50.0})


def test_score_falls_back_to_baseline_when_final_model_missing(tmp_path, monkeypatch):
    baseline_path = tmp_path / "baseline_logreg.joblib"
    _make_baseline_artifact(baseline_path)
    monkeypatch.setattr(config, "SERVING_FINAL_MODEL_PATH", tmp_path / "missing_final.joblib")
    monkeypatch.setattr(config, "SERVING_BASELINE_MODEL_PATH", baseline_path)
    monkeypatch.setattr(config, "SERVING_MODEL_VERSION", "v2")

    result = score_module.score({"TransactionAmt": 20.0, "C1": 0.5})

    assert 0.0 <= result["proba"] <= 1.0
    assert result["shap"] is None


def test_score_raises_file_not_found_when_no_artifact_available(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SERVING_FINAL_MODEL_PATH", tmp_path / "missing1.joblib")
    monkeypatch.setattr(config, "SERVING_BASELINE_MODEL_PATH", tmp_path / "missing2.joblib")
    monkeypatch.setattr(config, "SERVING_MODEL_VERSION", "v2")

    with pytest.raises(FileNotFoundError):
        score_module.score({"TransactionAmt": 10.0})


def test_score_chap_nhan_feature_none(tmp_path, monkeypatch):
    """Feature có mặt nhưng giá trị None phải được coi như thiếu (-999).

    CSV thật luôn có ô trống; nếu None đi vào DataFrame thì cột thành dtype
    object và LightGBM từ chối cả dòng.
    """
    final_path = tmp_path / "final_model.joblib"
    _make_tree_artifact(final_path)
    monkeypatch.setattr(config, "SERVING_FINAL_MODEL_PATH", final_path)
    monkeypatch.setattr(config, "SERVING_MODEL_VERSION", "v2")

    result = score_module.score(
        {
            "TransactionAmt": 100.0,
            "C1": None,
            "C2": None,
            "C3": 0.0,
            "C4": 1.0,
            "ProductCD": None,
        }
    )
    assert 0.0 <= result["proba"] <= 1.0
