"""Guard chất lượng cho `artifacts/final_model.joblib` đã commit — chặn
trường hợp ai đó vô tình commit đè một model tệ hơn hẳn mà không nhận ra.
Ngưỡng lấy thấp hơn kết quả đo được (holdout ROC-AUC 0.868/PR-AUC 0.430,
xem model/README.md) để chừa biên độ cho các lần train lại hợp lệ.
"""
import joblib
import pytest

from fraud_model import config


def test_committed_final_model_meets_minimum_holdout_bar():
    if not config.FINAL_MODEL_PATH.exists():
        pytest.skip("artifacts/final_model.joblib chưa có trong môi trường này")

    artifact = joblib.load(config.FINAL_MODEL_PATH)

    assert artifact["model_name"] in config.TREE_MODEL_NAMES
    assert artifact["holdout_roc_auc"] > 0.75
    assert artifact["holdout_pr_auc"] > 0.30
    assert len(artifact["top5_global_features"]) == 5
    assert len(artifact["feature_columns"]) > 0
