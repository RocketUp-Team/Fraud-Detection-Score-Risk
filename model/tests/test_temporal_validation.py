from fraud_model.data import split_validation_windows


def test_validation_is_split_into_ordered_non_overlapping_windows(spark):
    validation = spark.createDataFrame(
        [
            (index, index * 10, index % 2, float(index), "w")
            for index in range(1, 9)
        ],
        [
            "TransactionID",
            "TransactionDT",
            "isFraud",
            "TransactionAmt",
            "ProductCD",
        ],
    )

    windows = split_validation_windows(validation)

    assert windows.counts == {"selection": 4, "calibration": 2, "policy": 2}
    ids = {
        name: {
            row["TransactionID"]
            for row in getattr(windows, name).select("TransactionID").collect()
        }
        for name in ("selection", "calibration", "policy")
    }
    assert ids["selection"].isdisjoint(ids["calibration"])
    assert ids["selection"].isdisjoint(ids["policy"])
    assert ids["calibration"].isdisjoint(ids["policy"])
    assert set().union(*ids.values()) == set(range(1, 9))
