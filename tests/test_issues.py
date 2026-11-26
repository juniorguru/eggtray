import pytest

from jg.eggtray.enums import Placement
from jg.eggtray.issues import get_placement, get_username


@pytest.mark.parametrize(
    "body, expected",
    [
        (
            "Kuřátko, mrkni prosím na @alice, díky!\n\n<!-- placement: jobs -->",
            Placement.jobs,
        ),
        ("<!-- placement: homepage -->", Placement.homepage),
        ("<!--placement:handbook-->", Placement.handbook),
        ("<!--  Placement:  JOBS  -->", Placement.jobs),
        ("<!-- placement: moon -->", None),
        ("<!-- placement: -->", None),
        ("placement: jobs", None),
        ("Kuřátko, mrkni prosím na můj profil, díky!", None),
        ("", None),
    ],
)
def test_get_placement(body: str, expected: Placement | None):
    assert get_placement(body) == expected


def test_get_username_ignores_placement_marker():
    body = "<!-- placement: jobs -->\nKuřátko, mrkni prosím na @alice, díky!"

    assert get_username(body) == "alice"
