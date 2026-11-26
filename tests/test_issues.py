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
        ("<!-- src: jobs --> <!-- src: homepage -->", Placement.jobs),
        ("<!-- src: moon -->", None),
        ("<!-- src: -->", None),
        ("src: jobs", None),
        ("Kuřátko, mrkni prosím na můj profil, díky!", None),
        ("", None),
    ],
)
def test_get_placement(body: str, expected: Placement | None):
    assert get_placement(body) == expected


def test_parses_body_from_junior_guru_form():
    body = "Kuřátko, mrkni prosím na @alice, díky!\n\n<!-- src: handbook -->"

    assert get_username(body) == "alice"
    assert get_placement(body) == Placement.handbook
