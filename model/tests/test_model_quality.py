"""Guard chất lượng cho model serving hiện hành `v2` — chặn
trường hợp ai đó vô tình commit đè một model tệ hơn hẳn mà không nhận ra.
Ngưỡng lấy thấp hơn kết quả đo được (holdout ROC-AUC 0.880/PR-AUC 0.458,
xem model/README.md) để chừa biên độ cho các lần train lại hợp lệ.
"""
import joblib
import pytest

from fraud_model import config


def test_committed_final_model_meets_minimum_holdout_bar():
    candidate_paths = [config.SERVING_FINAL_MODEL_PATH, config.ARTIFACTS_DIR / "final_model.joblib"]
    final_path = next((path for path in candidate_paths if path.exists()), None)
    if final_path is None:
        pytest.skip("model serving v2 chưa có trong môi trường này")

    artifact = joblib.load(final_path)

    assert artifact["model_name"] in config.TREE_MODEL_NAMES
    assert artifact["holdout_roc_auc"] > 0.75
    assert artifact["holdout_pr_auc"] > 0.40
    assert len(artifact["top5_global_features"]) == 5
    assert len(artifact["feature_columns"]) > 0
