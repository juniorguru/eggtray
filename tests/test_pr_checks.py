import pytest
from githubkit.versions.latest.models import DiffEntry
from jg.hen.models import Outcome, Status, Summary

from jg.eggtray.pr_checks import (
    COMMENT_MARKER,
    format_summary_body,
    format_summary_section,
    get_checked_usernames,
    get_not_allowed_comment_text,
    get_touched_usernames,
    get_username,
    get_wait_comment_text,
)


def create_diff_entry(
    filename: str, status: str = "added", previous_filename: str | None = None
) -> DiffEntry:
    return DiffEntry(
        sha="0" * 40,
        filename=filename,
        status=status,
        additions=0,
        deletions=0,
        changes=0,
        blob_url="https://example.com",
        raw_url="https://example.com",
        contents_url="https://example.com",
        previous_filename=previous_filename,
    )


@pytest.mark.parametrize(
    "path, expected",
    [
        ("profiles/alice.yml", "alice"),
        ("profiles/Alice.yml", "Alice"),
        ("profiles/alice.yaml", "alice"),
        ("profiles/nested/alice.yml", None),
        ("README.md", None),
        ("src/jg/eggtray/enums.py", None),
    ],
)
def test_get_username(path: str, expected: str | None):
    assert get_username(path) == expected


def test_get_touched_usernames():
    files = [
        create_diff_entry("profiles/alice.yml", "added"),
        create_diff_entry("profiles/bob.yml", "modified"),
        create_diff_entry("profiles/carol.yml", "removed"),
        create_diff_entry("profiles/dave.yml", "renamed", "profiles/eve.yml"),
        create_diff_entry("src/jg/eggtray/enums.py", "modified"),
    ]

    assert get_touched_usernames(files) == ["alice", "bob", "carol", "dave", "eve"]


def test_get_touched_usernames_unique():
    files = [
        create_diff_entry("profiles/alice.yml", "renamed", "profiles/alice.yml"),
    ]

    assert get_touched_usernames(files) == ["alice"]


def test_get_checked_usernames():
    files = [
        create_diff_entry("profiles/alice.yml", "added"),
        create_diff_entry("profiles/bob.yml", "modified"),
        create_diff_entry("profiles/carol.yml", "removed"),
        create_diff_entry("profiles/dave.yml", "renamed", "profiles/eve.yml"),
        create_diff_entry("src/jg/eggtray/enums.py", "modified"),
    ]

    assert get_checked_usernames(files) == ["alice", "bob", "dave"]


def test_get_not_allowed_comment_text():
    text = get_not_allowed_comment_text("alice", ["bob"])

    assert "github.com/bob" in text
    assert "`profiles/alice.yml`" in text


def test_get_not_allowed_comment_text_no_author():
    text = get_not_allowed_comment_text(None, ["bob"])

    assert "github.com/bob" in text
    assert "`profiles/" not in text


def test_wait_comment_has_marker():
    assert COMMENT_MARKER in get_wait_comment_text(["alice"])


def test_summary_body_has_marker():
    assert COMMENT_MARKER in format_summary_body(["section"])


@pytest.mark.parametrize(
    "status, expected",
    [
        (Status.ERROR, "upozaděný"),
        (Status.DONE, "Nevidím žádné zásadní nedostatky"),
    ],
)
def test_format_summary_section(status: Status, expected: str):
    outcome = Outcome(
        rule="has_avatar",
        status=status,
        message="Profil má avatar.",
        docs_url="https://junior.guru/handbook/github-profile/",
    )
    summary = Summary(username="alice", outcomes=[outcome])

    assert expected in format_summary_section(summary)


def test_format_summary_section_error():
    summary = Summary(username="alice", outcomes=[], error=Exception("Boom"))

    assert "Boom" in format_summary_section(summary)
