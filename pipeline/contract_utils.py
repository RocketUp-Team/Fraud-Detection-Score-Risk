from __future__ import annotations

import hashlib
import json
import math
import numbers
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_VERSION = "2.1.0"
PROCESSING_VERSION = "ieee-cis-preprocess-2.1.0"
FEATURE_SCHEMA_VERSION = "ieee-cis-features-1.1.0"
RISK_BAND_POLICY_VERSION = "risk-bands-1.0.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_yaml_config(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def schema_hash(columns: list[dict[str, Any]]) -> str:
    canonical = json.dumps(columns, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_safe(value: Any) -> Any:
    """Convert non-finite numeric values to JSON ``null`` recursively.

    Pandas uses ``NaN`` for missing numeric cells.  The manifest deliberately
    uses ``allow_nan=False`` so that it stays standards-compliant JSON; a
    missing inventory value must therefore become ``null`` rather than the
    invalid JSON token ``NaN``.
    """
    if isinstance(value, numbers.Real) and not math.isfinite(float(value)):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            _json_safe(payload),
            handle,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            default=json_default,
        )
        handle.write("\n")
    json.loads(tmp_path.read_text(encoding="utf-8"))
    tmp_path.replace(path)


def atomic_write_text(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    tmp_path.replace(path)


def safe_copy_if_exists(source: Path, target: Path) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def environment_metadata() -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "pipeline_version": PIPELINE_VERSION,
        "processing_version": PROCESSING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "risk_band_policy_version": RISK_BAND_POLICY_VERSION,
        "cwd": str(Path.cwd().resolve()),
        "project_root": str(PROJECT_ROOT),
        "environment": {
            "IEEE_CIS_DATA_DIR": os.getenv("IEEE_CIS_DATA_DIR"),
            "IEEE_CIS_OUTPUT_DIR": os.getenv("IEEE_CIS_OUTPUT_DIR"),
            "SPARK_MASTER": os.getenv("SPARK_MASTER"),
            "PROJECT_ROOT": os.getenv("PROJECT_ROOT"),
        },
    }
