import pytest
from jg.hen.models import Outcome, Status, Summary

from jg.eggtray.checks import format_summary_body


CLUB_URL = "https://junior.guru/club/"


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


def test_format_summary_body_error_does_not_invite_to_club():
    summary = Summary(username="honzajavorek", outcomes=[], error=Exception("Boom"))

    assert CLUB_URL not in format_summary_body(summary)
