import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from githubkit.versions.latest.models import DiffEntry
from jg.hen.models import Outcome, Status, Summary

from jg.eggtray import pr_checks
from jg.eggtray.pr_checks import (
    COMMENT_MARKER,
    check_pull_request,
    format_summary_body,
    format_summary_section,
    format_wrong_paths_section,
    get_checked_profiles,
    get_not_allowed_comment_text,
    get_touched_profiles,
    get_username_from_path,
    get_wait_comment_text,
    get_wrong_paths,
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
        ("profiles/alice-bob.yml", "alice-bob"),
        ("profiles/alice.yaml", None),
        ("profiles/alice.json", None),
        ("profiles/alice.backup.yml", None),
        ("profiles/-alice.yml", None),
        ("profiles/al`ice.yml", None),
        ("profiles/nested/alice.yml", None),
        ("README.md", None),
        ("src/jg/eggtray/enums.py", None),
    ],
)
def test_get_username_from_path(path: str, expected: str | None):
    assert get_username_from_path(path) == expected


def test_get_touched_profiles():
    files = [
        create_diff_entry("profiles/alice.yml", "added"),
        create_diff_entry("profiles/bob.yml", "modified"),
        create_diff_entry("profiles/carol.yml", "removed"),
        create_diff_entry("profiles/dave.yml", "renamed", "profiles/eve.yml"),
        create_diff_entry("profiles/frank.yaml", "added"),
        create_diff_entry("src/jg/eggtray/enums.py", "modified"),
    ]

    assert list(get_touched_profiles(files)) == [
        "alice",
        "bob",
        "carol",
        "dave",
        "eve",
    ]


def test_get_touched_profiles_unique():
    files = [
        create_diff_entry("profiles/alice.yml", "renamed", "profiles/alice.yml"),
    ]

    assert get_touched_profiles(files) == {"alice": "profiles/alice.yml"}


def test_get_checked_profiles():
    files = [
        create_diff_entry("profiles/alice.yml", "added"),
        create_diff_entry("profiles/bob.yml", "modified"),
        create_diff_entry("profiles/carol.yml", "removed"),
        create_diff_entry("profiles/dave.yml", "renamed", "profiles/eve.yml"),
        create_diff_entry("src/jg/eggtray/enums.py", "modified"),
    ]

    assert get_checked_profiles(files) == {
        "alice": "profiles/alice.yml",
        "bob": "profiles/bob.yml",
        "dave": "profiles/dave.yml",
    }


def test_get_wrong_paths():
    files = [
        create_diff_entry("profiles/alice.yml", "added"),
        create_diff_entry("profiles/bob.yaml", "added"),
        create_diff_entry("profiles/carol.json", "removed"),
        create_diff_entry("profiles/dave.backup.yml", "modified"),
        create_diff_entry("README.md", "modified"),
    ]

    assert get_wrong_paths(files) == [
        "profiles/bob.yaml",
        "profiles/dave.backup.yml",
    ]


def test_get_not_allowed_comment_text():
    text = get_not_allowed_comment_text("alice", ["bob"])

    assert "github.com/bob" in text
    assert "`profiles/alice.yml`" in text


def test_get_not_allowed_comment_text_no_author():
    text = get_not_allowed_comment_text(None, ["bob"])

    assert "github.com/bob" in text
    assert "`profiles/" not in text


def test_format_wrong_paths_section():
    text = format_wrong_paths_section("alice", ["profiles/al`ice.yaml"])

    assert "`profiles/alice.yaml`" in text
    assert "`profiles/alice.yml`" in text


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


class FakeGitHub:
    def __init__(self, **kwargs: Any):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object):
        pass


class FakeAPI:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        author: str,
        files: list[DiffEntry],
        existing_usernames: set[str] | None = None,
        comment_id: int | None = None,
        reopened_by: list[str] | None = None,
    ):
        self.calls: list[tuple[str, Any]] = []
        self.existing_usernames = existing_usernames or set()
        self.pr = SimpleNamespace(
            state="open",
            user=SimpleNamespace(login=author),
        )

        async def fetch_pull_request(*args: Any):
            return self.pr

        async def fetch_pull_request_files(*args: Any):
            return files

        async def find_comment(*args: Any):
            return comment_id

        async def post_comment(github, owner, repo, number, text):
            self.calls.append(("post_comment", text))
            return 42

        async def update_comment(github, owner, repo, comment_id, text):
            self.calls.append(("update_comment", comment_id, text))

        async def close_pull_request(*args: Any):
            self.calls.append(("close_pull_request",))

        async def fetch_event_actors(github, owner, repo, number, event):
            assert event == "reopened"
            return reopened_by or []

        async def profile_exists(github, username):
            return username in self.existing_usernames

        async def check_profile_url(profile_url, **kwargs):
            self.calls.append(("check_profile_url", profile_url))
            return Summary(username=profile_url.split("/")[-1], outcomes=[])

        monkeypatch.setattr(pr_checks, "GitHub", FakeGitHub)
        for fn in [
            fetch_pull_request,
            fetch_pull_request_files,
            find_comment,
            post_comment,
            update_comment,
            close_pull_request,
            fetch_event_actors,
            profile_exists,
            check_profile_url,
        ]:
            monkeypatch.setattr(pr_checks, fn.__name__, fn)

    def run(self, **kwargs: Any) -> list[tuple[str, Any]]:
        asyncio.run(
            check_pull_request(None, "juniorguru", "eggtray", 1, **kwargs)  # type: ignore
        )
        return self.calls

    def names(self) -> list[str]:
        return [call[0] for call in self.calls]


def test_check_pull_request_own_profile(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(monkeypatch, "alice", [create_diff_entry("profiles/alice.yml")])
    api.run()

    assert api.names() == [
        "post_comment",
        "check_profile_url",
        "update_comment",
    ]
    assert api.calls[-1][1] == 42
    assert "Nevidím žádné zásadní nedostatky" in api.calls[-1][2]


def test_check_pull_request_reuses_comment(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(
        monkeypatch,
        "alice",
        [create_diff_entry("profiles/alice.yml")],
        comment_id=7,
    )
    api.run()

    assert "post_comment" not in api.names()
    assert {call[1] for call in api.calls if call[0] == "update_comment"} == {7}


def test_check_pull_request_foreign_profile(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(
        monkeypatch,
        "alice",
        [create_diff_entry("profiles/bob.yml", "removed")],
        existing_usernames={"bob"},
    )
    api.run()

    assert api.names() == ["post_comment", "close_pull_request"]
    assert "github.com/bob" in api.calls[0][1]


@pytest.mark.parametrize("reopened_by", [["honzajavorek"], ["alice", "HonzaJavorek"]])
def test_check_pull_request_foreign_profile_reopened_by_privileged(
    monkeypatch: pytest.MonkeyPatch, reopened_by: list[str]
):
    api = FakeAPI(
        monkeypatch,
        "alice",
        [create_diff_entry("profiles/bob.yml")],
        existing_usernames={"bob"},
        reopened_by=reopened_by,
    )
    api.run()

    assert api.names() == []


def test_check_pull_request_foreign_profile_reopened_by_author(
    monkeypatch: pytest.MonkeyPatch,
):
    api = FakeAPI(
        monkeypatch,
        "alice",
        [create_diff_entry("profiles/bob.yml")],
        existing_usernames={"bob"},
        reopened_by=["alice"],
    )
    api.run()

    assert api.names() == ["post_comment", "close_pull_request"]


def test_check_pull_request_typo(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(monkeypatch, "alice", [create_diff_entry("profiles/alcie.yml")])
    api.run()

    assert api.names() == ["post_comment"]
    assert "`profiles/alcie.yml`" in api.calls[0][1]
    assert "`profiles/alice.yml`" in api.calls[0][1]


@pytest.mark.parametrize(
    "file",
    [
        create_diff_entry("profiles/alice.yml", "renamed", "profiles/OldAlice.yml"),
        create_diff_entry("profiles/OldAlice.yml", "removed"),
    ],
)
def test_check_pull_request_gone_account_not_reported(
    monkeypatch: pytest.MonkeyPatch, file: DiffEntry
):
    api = FakeAPI(monkeypatch, "alice", [file])
    api.run()

    assert "Špatný název souboru" not in "".join(str(call[-1]) for call in api.calls)
    assert "close_pull_request" not in api.names()


def test_check_pull_request_wrong_suffix(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(monkeypatch, "alice", [create_diff_entry("profiles/alice.yaml")])
    api.run()

    assert api.names() == ["post_comment"]
    assert "`profiles/alice.yaml`" in api.calls[0][1]


def test_check_pull_request_privileged_doesnt_check_others(
    monkeypatch: pytest.MonkeyPatch,
):
    api = FakeAPI(
        monkeypatch,
        "honzajavorek",
        [create_diff_entry(f"profiles/user{i}.yml", "modified") for i in range(30)],
    )
    api.run()

    assert api.names() == []


def test_check_pull_request_stale_comment(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(
        monkeypatch,
        "alice",
        [create_diff_entry("profiles/alice.yml", "removed")],
        comment_id=7,
    )
    api.run()

    assert api.names() == ["update_comment"]
    assert "nepřidává ani nemění žádný profil" in api.calls[0][2]


def test_check_pull_request_nothing_to_do(monkeypatch: pytest.MonkeyPatch):
    api = FakeAPI(
        monkeypatch, "alice", [create_diff_entry("profiles/alice.yml", "removed")]
    )
    api.run()

    assert api.names() == []
