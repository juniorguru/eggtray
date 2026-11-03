import asyncio

import pytest
from jg.hen.models import Summary

from jg.eggtray import cli


def summary(error: Exception | None = None) -> Summary:
    return Summary(username="alice", outcomes=[], error=error)


def test_fetch_summary_retries_until_success(monkeypatch: pytest.MonkeyPatch):
    results = [summary(RuntimeError("boom")), summary(RuntimeError("boom")), summary()]

    async def check_profile_url(*args, **kwargs) -> Summary:
        return results.pop(0)

    monkeypatch.setattr(cli, "check_profile_url", check_profile_url)
    result = asyncio.run(
        cli.fetch_summary("https://github.com/alice", attempts=3, retry_wait=0)
    )

    assert result.error is None
    assert results == []


def test_fetch_summary_raises_after_attempts(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def check_profile_url(*args, **kwargs) -> Summary:
        calls.append(1)
        return summary(RuntimeError(f"boom {len(calls)}"))

    monkeypatch.setattr(cli, "check_profile_url", check_profile_url)

    with pytest.raises(RuntimeError, match="boom 3"):
        asyncio.run(
            cli.fetch_summary("https://github.com/alice", attempts=3, retry_wait=0)
        )
    assert len(calls) == 3
