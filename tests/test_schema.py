from pathlib import Path

import pytest

from jg.eggtray.schema import parse


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(path.read_text(), id=path.name)
        for path in (Path(__file__).parent.parent / "profiles").rglob("*.yml")
    ],
)
def test_schema(data: str):
    parse(data)
