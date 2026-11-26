import pytest

from jg.eggtray.enums import Placement
from jg.eggtray.issues import get_placement, get_username


@pytest.mark.parametrize(
    "body, expected",
    [
        (
            "Kuřátko, mrkni prosím na @alice, díky!\n\n<!-- src: jobs -->",
            Placement.jobs,
        ),
        ("<!-- src: homepage -->", Placement.homepage),
        ("<!--src:handbook-->", Placement.handbook),
        ("<!--  Src:  JOBS  -->", Placement.jobs),
        ("<!-- src: moon -->", None),
        ("<!-- src: -->", None),
        ("src: jobs", None),
        ("Kuřátko, mrkni prosím na můj profil, díky!", None),
        ("", None),
    ],
)
def test_get_placement(body: str, expected: Placement | None):
    assert get_placement(body) == expected


def test_get_username_ignores_placement_marker():
    body = "<!-- src: jobs -->\nKuřátko, mrkni prosím na @alice, díky!"

    assert get_username(body) == "alice"
