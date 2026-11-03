import asyncio

import pytest
import stamina
from jg.hen.models import Summary

from jg.eggtray import cli


@pytest.fixture(autouse=True)
def stamina_testing():
    with stamina.set_testing(True, attempts=3):
        yield


def test_fetch_summary_retries_until_success(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def check_profile_url(*args, **kwargs) -> Summary:
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        return Summary(username="alice", outcomes=[])

    monkeypatch.setattr(cli, "check_profile_url", check_profile_url)
    summary = asyncio.run(cli.fetch_summary("https://github.com/alice"))

    assert summary.username == "alice"
    assert len(calls) == 3


def test_fetch_summary_raises_after_attempts(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def check_profile_url(*args, **kwargs) -> Summary:
        calls.append(1)
        raise RuntimeError(f"boom {len(calls)}")

    monkeypatch.setattr(cli, "check_profile_url", check_profile_url)

    with pytest.raises(RuntimeError, match="boom 3"):
        asyncio.run(cli.fetch_summary("https://github.com/alice"))
    assert len(calls) == 3
