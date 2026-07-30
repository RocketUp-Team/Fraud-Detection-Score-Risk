import os

import pytest

from fraud_model.spark_session import get_spark


@pytest.fixture(scope="session")
def spark():
    os.environ.setdefault("SPARK_MASTER_URL", "local[2]")
    os.environ.setdefault("SPARK_DRIVER_MEMORY", "2g")
    session = get_spark()
    yield session
    session.stop()
