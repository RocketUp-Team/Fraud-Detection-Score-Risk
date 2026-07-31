"""Shared pandas evaluation helpers for validation and final holdout stages."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def binary_metrics(y_true, proba, threshold: float = 0.5) -> dict[str, float | int]:
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def threshold_table(y_true, proba, thresholds: np.ndarray | None = None) -> pd.DataFrame:
    thresholds = thresholds if thresholds is not None else np.round(np.arange(0.05, 0.951, 0.01), 2)
    return pd.DataFrame([binary_metrics(y_true, proba, float(t)) for t in thresholds])


def choose_recall_first_threshold(
    table: pd.DataFrame,
    min_precision: float = 0.30,
    min_reject_precision: float = 0.60,
) -> dict:
    eligible = table[table["precision"] >= min_precision]
    pool = eligible if not eligible.empty else table
    selected = pool.sort_values(["recall", "f1", "precision"], ascending=False).iloc[0]
    review_threshold = float(selected["threshold"])

    reject_candidates = table[
        (table["threshold"] >= review_threshold)
        & (table["precision"] >= min_reject_precision)
    ]
    if not reject_candidates.empty:
        reject = reject_candidates.sort_values(
            ["threshold", "recall", "precision"],
            ascending=[True, False, False],
        ).iloc[0]
        reject_rule = "lowest_threshold_meeting_reject_precision"
    else:
        reject_pool = table[table["threshold"] >= review_threshold]
        reject = reject_pool.sort_values(
            ["precision", "recall", "threshold"],
            ascending=[False, False, False],
        ).iloc[0]
        reject_rule = "best_available_precision_fallback"
    return {
        "review_threshold": review_threshold,
        "reject_threshold": float(reject["threshold"]),
        "selection_rule": "max_recall_then_f1_with_min_precision",
        "reject_selection_rule": reject_rule,
        "min_precision": float(min_precision),
        "min_reject_precision": float(min_reject_precision),
        "selected_review_precision": float(selected["precision"]),
        "selected_reject_precision": float(reject["precision"]),
    }
