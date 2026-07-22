import pandas as pd

from fraud_model.features import prepare_baseline_features


def test_prepare_baseline_features_drops_non_feature_cols_and_fills_na():
    df = pd.DataFrame(
        {
            "TransactionID": [1, 2],
            "TransactionDT": [100, 200],
            "isFraud": [0, 1],
            "TransactionAmt": [50.0, None],
            "ProductCD": ["W", "C"],
        }
    )

    X = prepare_baseline_features(df)

    assert list(X.columns) == ["TransactionAmt", "ProductCD"]
    assert X["TransactionAmt"].iloc[1] == -999
    assert X["ProductCD"].dtype.kind in "iu"
