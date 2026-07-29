from pathlib import Path

from fraud_model import tracking


def _capture_mlflow_calls(monkeypatch):
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        tracking.mlflow,
        "set_tracking_uri",
        lambda uri: calls.__setitem__("tracking_uri", uri),
    )
    monkeypatch.setattr(
        tracking.mlflow,
        "get_experiment_by_name",
        lambda name: None,
    )
    monkeypatch.setattr(
        tracking.mlflow,
        "create_experiment",
        lambda name, **kwargs: calls.__setitem__(
            "create_experiment",
            (name, kwargs),
        ),
    )
    monkeypatch.setattr(
        tracking.mlflow,
        "set_experiment",
        lambda name: calls.__setitem__("set_experiment", name),
    )
    return calls


def test_configure_creates_local_sqlite_and_artifact_directories(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(tracking.config, "ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setenv("MLFLOW_EXPERIMENT", "local-test")
    calls = _capture_mlflow_calls(monkeypatch)

    tracking.configure()

    assert artifacts_dir.is_dir()
    assert (artifacts_dir / "mlflow-artifacts").is_dir()
    assert calls["tracking_uri"] == (
        f"sqlite:///{(artifacts_dir / 'mlflow.db').resolve().as_posix()}"
    )
    assert calls["create_experiment"] == (
        "local-test",
        {
            "artifact_location": (
                artifacts_dir / "mlflow-artifacts"
            ).resolve().as_uri()
        },
    )
    assert calls["set_experiment"] == "local-test"


def test_configure_does_not_force_local_artifacts_for_remote_server(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "unused-artifacts"
    monkeypatch.setattr(tracking.config, "ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "https://mlflow.example.test")
    monkeypatch.setenv("MLFLOW_EXPERIMENT", "remote-test")
    calls = _capture_mlflow_calls(monkeypatch)

    tracking.configure()

    assert calls["tracking_uri"] == "https://mlflow.example.test"
    assert calls["create_experiment"] == ("remote-test", {})
    assert calls["set_experiment"] == "remote-test"
    assert not artifacts_dir.exists()
