import pandas as pd

from fraud_model.evaluation import choose_recall_first_threshold


def test_reject_threshold_is_selected_from_observed_precision():
    table = pd.DataFrame(
        [
            {"threshold": 0.10, "precision": 0.20, "recall": 0.90, "f1": 0.33},
            {"threshold": 0.20, "precision": 0.35, "recall": 0.80, "f1": 0.49},
            {"threshold": 0.40, "precision": 0.61, "recall": 0.50, "f1": 0.55},
            {"threshold": 0.60, "precision": 0.75, "recall": 0.30, "f1": 0.43},
        ]
    )

    policy = choose_recall_first_threshold(
        table,
        min_precision=0.30,
        min_reject_precision=0.60,
    )

    assert policy["review_threshold"] == 0.20
    assert policy["reject_threshold"] == 0.40
    assert (
        policy["reject_selection_rule"]
        == "lowest_threshold_meeting_reject_precision"
    )
