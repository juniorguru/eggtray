import pytest
from jg.hen.models import Outcome, Status, Summary

from jg.eggtray.checks import (
    format_summary_body,
    get_club_url,
    get_utm_source,
    is_allowed,
)
from jg.eggtray.config import CLUB_URL
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

    assert CLUB_URL in format_summary_body(summary)


def test_format_summary_body_club_url_uses_placement():
    summary = Summary(username="honzajavorek", outcomes=[])
    body = format_summary_body(summary, placement=Placement.jobs)

    assert "utm_source=gh-check-jobs&" in body
    assert CLUB_URL not in body


@pytest.mark.parametrize(
    "placement, expected",
    [
        (Placement.homepage, "gh-check"),
        (Placement.jobs, "gh-check-jobs"),
        (Placement.handbook, "gh-check-handbook"),
        (None, "gh-check"),
    ],
)
def test_get_utm_source(placement: Placement | None, expected: str):
    assert get_utm_source(placement) == expected


def test_utm_sources_cover_all_placements():
    assert {get_utm_source(placement) for placement in Placement} == {
        "gh-check",
        "gh-check-jobs",
        "gh-check-handbook",
    }


def test_get_club_url_defaults_to_gh_check():
    assert get_club_url() == CLUB_URL
    assert "utm_source=gh-check&" in CLUB_URL


def test_format_summary_body_error_does_not_invite_to_club():
    summary = Summary(username="honzajavorek", outcomes=[], error=Exception("Boom"))

    assert CLUB_URL not in format_summary_body(summary)


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
