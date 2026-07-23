#!/usr/bin/env python3
"""Verify the AN model-ready output contract inside Docker."""
from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    root = Path(os.getenv("IEEE_CIS_OUTPUT_DIR", "/app/data/processed/ieee_cis_spark"))
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Processed-data manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = ["train_original", "train_weighted", "train_balanced", "validation", "holdout", "kaggle_test"]
    missing = [name for name in required if not (root / "model_ready" / name).is_dir()]
    if missing:
        raise FileNotFoundError(f"Missing model-ready datasets: {missing}")

    print(json.dumps({
        "status": "ready_for_training",
        "root": str(root),
        "datasets": required,
        "numeric_feature_count": len(manifest.get("numeric_features", [])),
        "categorical_feature_count": len(manifest.get("categorical_features", [])),
    }, indent=2))


if __name__ == "__main__":
    main()
