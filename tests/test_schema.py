from pathlib import Path

import pytest
from strictyaml import load

from jg.eggtray.schema import profile


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(path.read_text(), id=path.name)
        for path in (Path(__file__).parent.parent / "profiles").rglob("*.yml")
    ],
)
def test_schema(data: dict):
    load(data, profile)
