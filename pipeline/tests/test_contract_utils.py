import json
import math

from pipeline.contract_utils import atomic_write_json


def test_atomic_write_json_converts_non_finite_numbers_to_null(tmp_path):
    path = tmp_path / "manifest.json"

    atomic_write_json(
        {
            "missing_float": math.nan,
            "nested": {"positive_infinity": math.inf},
            "values": [1.0, -math.inf],
        },
        path,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "missing_float": None,
        "nested": {"positive_infinity": None},
        "values": [1.0, None],
    }
