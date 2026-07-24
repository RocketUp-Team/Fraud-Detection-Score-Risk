"""Command-line entrypoint for the local IEEE-CIS pipeline.

The implementation remains in ``ieee_cis_preprocess.py`` so the exported
notebook, local command and Docker job use the same processing logic.
"""
from __future__ import annotations

import argparse
import os
import runpy
from pathlib import Path


IMPLEMENTATION = Path(__file__).with_name("ieee_cis_preprocess.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare IEEE-CIS fraud data for model training.")
    parser.add_argument("--raw-dir", type=Path, help="Directory containing the four required Kaggle CSV files.")
    parser.add_argument("--output-dir", type=Path, help="Directory for processed data and reports.")
    parser.add_argument("--master", default="local[*]", help="Spark master, default: local[*].")
    parser.add_argument("--skip-model-demo", action="store_true", help="Skip Decision Tree training and demo outputs.")
    parser.add_argument("--skip-profile", action="store_true", help="Skip the full EDA profile.")
    parser.add_argument("--no-wide-feature-store", action="store_true", help="Do not write wide feature-store tables.")
    parser.add_argument("--imbalance-ratio", type=float, default=4.0, help="Legitimate-to-fraud ratio for training undersampling.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not IMPLEMENTATION.is_file():
        raise FileNotFoundError(f"Pipeline implementation not found: {IMPLEMENTATION}")

    values = {
        "SPARK_MASTER": args.master,
        "RUN_MODEL_DEMO": str(not args.skip_model_demo).lower(),
        "RUN_FULL_PROFILE": str(not args.skip_profile).lower(),
        "WRITE_WIDE_FEATURE_STORE": str(not args.no_wide_feature_store).lower(),
        "IMBALANCE_RATIO": str(args.imbalance_ratio),
    }
    if args.raw_dir:
        values["IEEE_CIS_DATA_DIR"] = str(args.raw_dir.resolve())
    if args.output_dir:
        values["IEEE_CIS_OUTPUT_DIR"] = str(args.output_dir.resolve())
    os.environ.update(values)
    runpy.run_path(str(IMPLEMENTATION), run_name="__main__")


if __name__ == "__main__":
    main()
