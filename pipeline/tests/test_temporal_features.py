from pyspark.sql import SparkSession

from pipeline.temporal_features import (
    add_point_in_time_history,
    calculate_temporal_boundaries,
    split_by_boundaries,
)


def test_split_boundaries_and_point_in_time_history():
    spark = (
        SparkSession.builder.master("local[1]")
        .appName("pipeline-temporal-test")
        .getOrCreate()
    )
    try:
        df = spark.createDataFrame(
            [
                (1, 10, 100.0, "card-a", "email-a", "device-a"),
                (2, 20, 50.0, "card-a", "email-a", "device-a"),
                (3, 30, 25.0, "card-a", "email-b", "device-b"),
                (4, 40, 10.0, "card-b", "email-b", "device-b"),
            ],
            [
                "TransactionID",
                "TransactionDT",
                "TransactionAmt",
                "card_entity_key",
                "email_entity_key",
                "device_entity_key",
            ],
        )
        boundaries = calculate_temporal_boundaries(
            df,
            train_ratio=0.50,
            validation_ratio=0.25,
            relative_error=0.0,
        )
        train, validation, holdout = split_by_boundaries(df, boundaries)
        assert train.count() + validation.count() + holdout.count() == 4

        rows = {
            row["TransactionID"]: row
            for row in add_point_in_time_history(df).collect()
        }
        assert rows[1]["prior_card_transaction_count"] == 0
        assert rows[2]["prior_card_transaction_count"] == 1
        assert rows[2]["prior_card_amount_sum"] == 100.0
        assert rows[3]["prior_card_transaction_count"] == 2
        assert rows[3]["prior_card_amount_sum"] == 150.0
        assert rows[4]["prior_card_transaction_count"] == 0
    finally:
        spark.stop()
