from collections import OrderedDict
from typing import cast

from strictyaml import Map, Str, load


profile = Map(
    {
        "name": Str(),
    }
)


def parse(yaml_text: str) -> dict:
    data = load(yaml_text, profile).data
    data = dict(cast(OrderedDict, data))
    return data
