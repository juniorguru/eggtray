from collections import OrderedDict
from typing import cast

from strictyaml import Map, Str, load


profile = Map(
    {
        "name": Str(),
    }
)


def parse(yaml_text: str) -> OrderedDict:
    return cast(OrderedDict, load(yaml_text, profile).data)
