import pytest

from fraud_model.spark_session import get_spark


@pytest.fixture(scope="session")
def spark():
    session = get_spark()
    yield session
    session.stop()
