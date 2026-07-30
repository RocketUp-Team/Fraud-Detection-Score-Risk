"""Small MLflow integration shared by the training entry points.

The default tracking URI is a local file store under ``model/artifacts`` so
training remains reproducible offline and works in both Spark cluster and
Spark local Docker modes. Set ``MLFLOW_TRACKING_URI`` to a remote tracking
server when one is available.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import mlflow

from . import config


def configure() -> None:
    db_path = (config.ARTIFACTS_DIR / "mlflow.db").resolve()
    tracking_uri = os.environ.get(
        "MLFLOW_TRACKING_URI",
        f"sqlite:///{db_path.as_posix()}",
    )
    mlflow.set_tracking_uri(tracking_uri)
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT", "fraud-detection-training")
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        mlflow.create_experiment(
            experiment_name,
            artifact_location=(config.ARTIFACTS_DIR / "mlflow-artifacts").resolve().as_uri(),
        )
    mlflow.set_experiment(experiment_name)


@contextmanager
def training_run(stage: str, *, tags: dict[str, str] | None = None) -> Iterator:
    """Create one auditable run for a training stage."""
    configure()
    run_name = f"{config.TRAINING_MODEL_VERSION}-{stage}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tags(
            {
                "model_version": config.TRAINING_MODEL_VERSION,
                "stage": stage,
                "spark_master": os.environ.get("SPARK_MASTER_URL", "local[*]"),
                **(tags or {}),
            }
        )
        yield run


def log_dataset_params(train_rows: int, validation_rows: int) -> None:
    mlflow.log_params(
        {
            "training_version": config.TRAINING_MODEL_VERSION,
            "train_rows": train_rows,
            "validation_rows": validation_rows,
            "feature_contract": str(config.MODEL_READY_DIR),
        }
    )


def log_json_artifact(path: Path) -> None:
    if path.exists():
        mlflow.log_artifact(str(path), artifact_path="metadata")


def log_completed_run(
    stage: str,
    *,
    metrics: dict[str, float],
    params: dict[str, object] | None = None,
    artifacts: list[Path] | None = None,
) -> str:
    """Record a completed stage when the stage's existing code is not wrapped."""
    with training_run(stage) as run:
        if params:
            mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        for artifact in artifacts or []:
            log_json_artifact(artifact)
        return run.info.run_id
