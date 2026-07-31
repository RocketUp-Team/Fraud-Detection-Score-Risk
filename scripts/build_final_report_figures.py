"""Build evidence-backed figures for the final architecture report.

All plotted values are read from generated CSV/JSON artifacts; no metrics are
embedded in the plotting code.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data/processed/ieee_cis_fraud_risk/reports"
ARTIFACTS = ROOT / "model/artifacts"
OUT = ROOT / "docs/figures/final_report"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def part_file(directory: Path) -> Path:
    files = sorted(directory.glob("part-*.csv"))
    if not files:
        raise FileNotFoundError(f"No Spark CSV part file in {directory}")
    return files[0]


def style(ax: plt.Axes, ylabel: str) -> None:
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#d9dee7", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#8a94a6")
    ax.spines["bottom"].set_color("#8a94a6")
    ax.tick_params(colors="#263238")
    ax.set_facecolor("#ffffff")
    ax.figure.patch.set_facecolor("#ffffff")


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def class_distribution() -> None:
    rows = read_csv(part_file(REPORTS / "class_distribution.csv"))
    labels = ["Legitimate" if row["isFraud"] == "0" else "Fraud" for row in rows]
    values = [int(row["transaction_count"]) for row in rows]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    bars = ax.bar(labels, values, color=["#3b82f6", "#d97706"], width=0.58)
    style(ax, "Transactions")
    ax.set_title("Class distribution", loc="left", weight="bold")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,}", ha="center", va="bottom")
    save(fig, "class-distribution")


def category_rate(directory: str, category: str, name: str, title: str) -> None:
    rows = read_csv(part_file(REPORTS / directory))
    rows.sort(key=lambda row: float(row["fraud_rate_pct"]), reverse=True)
    labels = [row[category] for row in rows]
    values = [float(row["fraud_rate_pct"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.barh(labels[::-1], values[::-1], color="#2563eb")
    style(ax, "Fraud rate (%)")
    ax.set_title(title, loc="left", weight="bold")
    for bar, value in zip(bars, values[::-1]):
        ax.text(value, bar.get_y() + bar.get_height() / 2, f"{value:.2f}", va="center", ha="left", fontsize=9)
    save(fig, name)


def identity_rate() -> None:
    rows = read_csv(part_file(REPORTS / "fraud_by_has_identity_csv"))
    labels = ["No identity match" if row["has_identity"] == "0" else "Identity match" for row in rows]
    values = [float(row["fraud_rate_pct"]) for row in rows]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    bars = ax.bar(labels, values, color=["#94a3b8", "#7c3aed"], width=0.58)
    style(ax, "Fraud rate (%)")
    ax.set_title("Fraud rate by identity presence", loc="left", weight="bold")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}%", ha="center", va="bottom")
    save(fig, "fraud-rate-by-identity-presence")


def hour_rate() -> None:
    rows = read_csv(part_file(REPORTS / "fraud_by_hour_csv"))
    hours = [int(row["transaction_hour"]) for row in rows]
    values = [float(row["fraud_rate_pct"]) for row in rows]
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.plot(hours, values, color="#2563eb", marker="o", markersize=3.5, linewidth=2)
    style(ax, "Fraud rate (%)")
    ax.set_xlabel("Transaction hour derived from TransactionDT")
    ax.set_title("Fraud rate by transaction hour", loc="left", weight="bold")
    ax.set_xticks(range(0, 24, 2))
    save(fig, "fraud-rate-by-transaction-hour")


def model_performance() -> None:
    v1 = json.loads((ARTIFACTS / "model_comparison.json").read_text(encoding="utf-8"))
    v2 = json.loads((ARTIFACTS / "v2/model_comparison_v2.json").read_text(encoding="utf-8"))
    v1_name = v1["best_model"]
    v2_name = v2["best_model"]
    labels = ["V1\n" + v1_name, "V2\n" + v2_name]
    roc = [v1["results"][v1_name]["roc_auc"], v2["results"][v2_name]["roc_auc"]]
    pr = [v1["results"][v1_name]["pr_auc"], v2["results"][v2_name]["pr_auc"]]
    positions = [0, 1]
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.bar([p - width / 2 for p in positions], roc, width, label="ROC-AUC", color="#2563eb")
    ax.bar([p + width / 2 for p in positions], pr, width, label="PR-AUC", color="#d97706")
    style(ax, "Validation metric")
    ax.set_xticks(positions, labels)
    ax.set_ylim(0, 1)
    ax.set_title("V1 and V2 validation performance", loc="left", weight="bold")
    ax.legend(frameon=False, ncols=2, loc="upper left")
    ax.text(0, -0.22, "Source: model_comparison.json and model_comparison_v2.json;\nmodels and dataset variants differ, so this is descriptive rather than causal.", transform=ax.transAxes, fontsize=8.5, color="#5b6573")
    save(fig, "v1-v2-validation-performance")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    class_distribution()
    category_rate("fraud_by_product_csv", "ProductCD", "fraud-rate-by-product", "Fraud rate by ProductCD")
    identity_rate()
    hour_rate()
    model_performance()


if __name__ == "__main__":
    main()
