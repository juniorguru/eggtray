from collections import OrderedDict
from typing import cast

from strictyaml import Int, Map, load


profile = Map(
    {
        "discord_id": Int(),
    }
)


def parse(yaml_text: str) -> dict:
    data = load(yaml_text, profile).data
    data = dict(cast(OrderedDict, data))
    return data
