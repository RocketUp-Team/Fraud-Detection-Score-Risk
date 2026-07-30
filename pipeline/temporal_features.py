"""Reusable, point-in-time-safe Spark transformations."""
from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


@dataclass(frozen=True)
class TemporalBoundaries:
    train_max: float
    validation_max: float


def calculate_temporal_boundaries(
    df: DataFrame,
    *,
    train_ratio: float,
    validation_ratio: float,
    time_col: str = "TransactionDT",
    relative_error: float = 0.001,
) -> TemporalBoundaries:
    if not 0.0 < train_ratio < train_ratio + validation_ratio < 1.0:
        raise ValueError(
            "train_ratio and validation_ratio must create three non-empty windows"
        )
    train_max, validation_max = df.approxQuantile(
        time_col,
        [train_ratio, train_ratio + validation_ratio],
        relative_error,
    )
    return TemporalBoundaries(float(train_max), float(validation_max))


def split_by_boundaries(
    df: DataFrame,
    boundaries: TemporalBoundaries,
    *,
    time_col: str = "TransactionDT",
) -> tuple[DataFrame, DataFrame, DataFrame]:
    train = df.filter(F.col(time_col) <= F.lit(boundaries.train_max))
    validation = df.filter(
        (F.col(time_col) > F.lit(boundaries.train_max))
        & (F.col(time_col) <= F.lit(boundaries.validation_max))
    )
    holdout = df.filter(F.col(time_col) > F.lit(boundaries.validation_max))
    return train, validation, holdout


def add_point_in_time_history(df: DataFrame) -> DataFrame:
    """Add entity histories that use rows strictly before the current row."""
    card_order = Window.partitionBy("card_entity_key").orderBy(
        "TransactionDT",
        "TransactionID",
    )
    card_history = card_order.rowsBetween(Window.unboundedPreceding, -1)
    email_history = (
        Window.partitionBy("email_entity_key")
        .orderBy("TransactionDT", "TransactionID")
        .rowsBetween(Window.unboundedPreceding, -1)
    )
    device_history = (
        Window.partitionBy("device_entity_key")
        .orderBy("TransactionDT", "TransactionID")
        .rowsBetween(Window.unboundedPreceding, -1)
    )
    return (
        df.withColumn(
            "prior_card_transaction_count",
            F.count(F.lit(1)).over(card_history).cast("long"),
        )
        .withColumn(
            "prior_card_amount_sum",
            F.coalesce(F.sum("TransactionAmt").over(card_history), F.lit(0.0)).cast(
                "double"
            ),
        )
        .withColumn(
            "prior_card_avg_amount",
            F.when(
                F.col("prior_card_transaction_count") > 0,
                F.col("prior_card_amount_sum")
                / F.col("prior_card_transaction_count"),
            ).otherwise(F.lit(0.0)),
        )
        .withColumn(
            "prior_card_amount_stddev",
            F.coalesce(
                F.stddev_samp("TransactionAmt").over(card_history),
                F.lit(0.0),
            ).cast("double"),
        )
        .withColumn(
            "time_since_previous_card_transaction",
            (
                F.col("TransactionDT")
                - F.lag("TransactionDT").over(card_order)
            ).cast("double"),
        )
        .withColumn(
            "prior_email_transaction_count",
            F.count(F.lit(1)).over(email_history).cast("long"),
        )
        .withColumn(
            "prior_email_amount_sum",
            F.coalesce(F.sum("TransactionAmt").over(email_history), F.lit(0.0)).cast(
                "double"
            ),
        )
        .withColumn(
            "prior_email_avg_amount",
            F.coalesce(F.avg("TransactionAmt").over(email_history), F.lit(0.0)).cast(
                "double"
            ),
        )
        .withColumn(
            "prior_device_transaction_count",
            F.count(F.lit(1)).over(device_history).cast("long"),
        )
        .withColumn(
            "prior_device_amount_sum",
            F.coalesce(F.sum("TransactionAmt").over(device_history), F.lit(0.0)).cast(
                "double"
            ),
        )
        .withColumn(
            "prior_device_avg_amount",
            F.coalesce(F.avg("TransactionAmt").over(device_history), F.lit(0.0)).cast(
                "double"
            ),
        )
    )
