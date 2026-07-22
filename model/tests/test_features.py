import pytest

from fraud_model.features import prepare_baseline_features, to_pandas_xy
from fraud_model.spark_session import get_spark


@pytest.fixture(scope="module")
def spark():
    session = get_spark()
    yield session
    session.stop()


def test_prepare_baseline_features_drops_non_feature_cols_and_fills_na(spark):
    df = spark.createDataFrame(
        [
            (1, 100, 0, 50.0, "W"),
            (2, 200, 1, None, "C"),
        ],
        ["TransactionID", "TransactionDT", "isFraud", "TransactionAmt", "ProductCD"],
    )

    features_df = prepare_baseline_features(df)
    X, y = to_pandas_xy(features_df)

    assert set(X.columns) == {"TransactionAmt", "ProductCD"}
    assert X["TransactionAmt"].iloc[1] == -999
    assert X["ProductCD"].dtype.kind == "f"
    assert list(y) == [0, 1]
