from pathlib import Path

import pytest

from jg.eggtray.profile import parse


PROFILES_DIR = Path(__file__).parent.parent / "profiles"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(path.read_text(), id=path.name)
        for path in PROFILES_DIR.glob("*.yml")
    ],
)
def test_schema(data: str):
    parse(data)


def test_unique():
    usernames = [path.stem.lower() for path in PROFILES_DIR.glob("*.yml")]
    assert len(usernames) == len(set(usernames))


def test_extra_files():
    extra_paths = set(PROFILES_DIR.glob("*")) - set(PROFILES_DIR.glob("*.yml"))
    assert not extra_paths
