import pytest

from fraud_model.features import (
    apply_categorical_indexer,
    encode_categoricals_pandas,
    extract_category_mappings,
    fit_categorical_indexer,
    to_pandas_xy,
)
from fraud_model.spark_session import get_spark


@pytest.fixture(scope="module")
def spark():
    session = get_spark()
    yield session
    session.stop()


def _make_train_val(spark):
    train_df = spark.createDataFrame(
        [
            (1, 100, 0, 50.0, "W", 0.5),
            (2, 200, 1, 30.0, "C", 14.2),
        ],
        ["TransactionID", "TransactionDT", "isFraud", "TransactionAmt", "ProductCD", "class_weight"],
    )
    val_df = spark.createDataFrame(
        [(3, 300, 0, 40.0, "W")],
        ["TransactionID", "TransactionDT", "isFraud", "TransactionAmt", "ProductCD"],
    )
    return train_df, val_df


def test_indexer_fits_on_train_and_applies_to_validation_without_refit(spark):
    train_df, val_df = _make_train_val(spark)

    indexer = fit_categorical_indexer(train_df)
    train_encoded = apply_categorical_indexer(indexer, train_df)
    val_encoded = apply_categorical_indexer(indexer, val_df)

    X_train, y_train, w_train = to_pandas_xy(train_encoded)
    X_val, y_val, w_val = to_pandas_xy(val_encoded)

    assert set(X_train.columns) == {"TransactionAmt", "ProductCD"}
    assert list(y_train) == [0, 1]
    assert list(w_train) == [0.5, 14.2]
    assert w_val is None
    assert X_val["ProductCD"].iloc[0] == X_train["ProductCD"].iloc[0]  # "W" mapped consistently


def test_encode_categoricals_pandas_uses_train_fitted_mapping_and_handles_unseen(spark):
    train_df, _ = _make_train_val(spark)
    indexer = fit_categorical_indexer(train_df)
    mappings = extract_category_mappings(indexer)

    known = encode_categoricals_pandas({"ProductCD": "W", "TransactionAmt": 10.0}, mappings)
    unseen = encode_categoricals_pandas({"ProductCD": "NEVER_SEEN"}, mappings)

    assert known["ProductCD"] == mappings["ProductCD"]["W"]
    assert known["TransactionAmt"] == 10.0
    assert unseen["ProductCD"] == len(mappings["ProductCD"])
