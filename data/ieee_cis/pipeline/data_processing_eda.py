#!/usr/bin/env python3
"""IEEE-CIS data processing entrypoint.

The maintained implementation lives in ``ieee_cis_preprocess.py`` so the
Docker job and the original notebook share one source of truth. This small
entrypoint provides the named deliverable requested for AN and makes the run
contract explicit.
"""
from __future__ import annotations

import runpy
from pathlib import Path


IMPLEMENTATION = Path(__file__).with_name("ieee_cis_preprocess.py")


def main() -> None:
    """Run the Spark preprocessing, EDA, feature and demo pipeline."""
    if not IMPLEMENTATION.is_file():
        raise FileNotFoundError(f"Pipeline implementation not found: {IMPLEMENTATION}")
    runpy.run_path(str(IMPLEMENTATION), run_name="__main__")


if __name__ == "__main__":
    main()
