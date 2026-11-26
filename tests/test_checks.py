import pytest
from jg.hen.models import Outcome, Status, Summary

from jg.eggtray.checks import (
    format_summary_body,
    get_club_url,
    get_utm_source,
    is_allowed,
)
from jg.eggtray.enums import Placement


@pytest.mark.parametrize(
    "status",
    [Status.ERROR, Status.DONE],
)
def test_format_summary_body_invites_to_club(status: Status):
    outcome = Outcome(
        rule="has_avatar",
        status=status,
        message="Profil má avatar.",
        docs_url="https://junior.guru/handbook/github-profile/",
    )
    summary = Summary(username="honzajavorek", outcomes=[outcome])

    assert "https://junior.guru/club/?" in format_summary_body(summary)


@pytest.mark.parametrize(
    "placement, expected",
    [
        (Placement.homepage, "utm_source=gh-check&"),
        (Placement.jobs, "utm_source=gh-check-jobs&"),
        (None, "utm_source=gh-check-unknown&"),
    ],
)
def test_format_summary_body_attributes_club_url(
    placement: Placement | None, expected: str
):
    summary = Summary(username="honzajavorek", outcomes=[])

    assert expected in format_summary_body(summary, placement=placement)


@pytest.mark.parametrize(
    "placement, expected",
    [
        (Placement.homepage, "gh-check"),
        (Placement.jobs, "gh-check-jobs"),
        (Placement.handbook, "gh-check-handbook"),
        (None, "gh-check-unknown"),
    ],
)
def test_get_utm_source(placement: Placement | None, expected: str):
    assert get_utm_source(placement) == expected


def test_get_utm_source_covers_all_placements():
    sources = {get_utm_source(placement) for placement in Placement}

    assert len(sources) == len(Placement)
    assert "gh-check-unknown" not in sources


def test_get_club_url():
    assert get_club_url(Placement.jobs) == (
        "https://junior.guru/club/"
        "?utm_source=gh-check-jobs&utm_medium=github&utm_campaign=jaro"
    )


def test_format_summary_body_error_does_not_invite_to_club():
    summary = Summary(username="honzajavorek", outcomes=[], error=Exception("Boom"))

    assert "https://junior.guru/club/" not in format_summary_body(summary)


@pytest.mark.parametrize(
    "author, username, expected",
    [
        ("alice", "alice", True),
        ("Alice", "alice", True),
        ("alice", "Alice", True),
        ("alice", "bob", False),
        (None, "bob", False),
        ("honzajavorek", "bob", True),
        ("HonzaJavorek", "bob", True),
        ("roboticke-kure[bot]", "bob", True),
    ],
)
def test_is_allowed(author: str | None, username: str, expected: bool):
    assert is_allowed(author, username) is expected
