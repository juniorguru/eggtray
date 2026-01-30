from pathlib import Path
from typing import Any

import pytest
import yaml

from jg.eggtray.models import ProfileConfig


PROFILES_DIR = Path(__file__).parent.parent / "profiles"


@pytest.mark.parametrize(
    "username, data",
    [
        pytest.param(path.stem, yaml.safe_load(path.read_text()), id=path.name)
        for path in PROFILES_DIR.glob("*.yml")
    ],
)
def test_schema(username: str, data: dict[str, Any]):
    ProfileConfig.create(username, data)


def test_unique():
    usernames = [path.stem.lower() for path in PROFILES_DIR.glob("*.yml")]
    assert len(usernames) == len(set(usernames))


def test_extra_files():
    extra_paths = set(PROFILES_DIR.glob("*")) - set(PROFILES_DIR.glob("*.yml"))
    assert not extra_paths
