import logging
import re
from typing import cast

from githubkit import GitHub
from githubkit.exception import RequestFailed
from githubkit.versions.latest.models import (
    Issue,
    IssuePropLabelsItemsOneof1 as IssueLabel,
)


USERNAME_RE = re.compile(r"@([\w\-]+)")


logger = logging.getLogger(__name__)


async def fetch_issue(
    github: GitHub, owner: str, repo: str, issue_number: int
) -> Issue:
    logger.debug(f"Fetching issue #{issue_number}")
    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    return response.parsed_data


def has_label(issue: Issue, label_name: str) -> bool:
    return any(
        label.name == label_name for label in cast(list[IssueLabel], issue.labels)
    )


def get_username(body: str) -> str | None:
    if match := USERNAME_RE.search(body):
        return match.group(1)
    return None


async def profile_exists(github: GitHub, username: str) -> bool:
    logger.debug(f"Checking if profile {username} exists")
    try:
        await github.rest.users.async_get_by_username(username)
        return True
    except RequestFailed as e:
        if e.response.status_code == 404:
            return False
        raise


async def update_title(
    github: GitHub, owner: str, repo: str, issue_number: int, title: str
):
    logger.debug(f"Checking title of issue #{issue_number}")
    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    issue: Issue = response.parsed_data
    if issue.title != title:
        logger.debug(
            f"Updating title of issue #{issue_number} from {issue.title!r} to {title!r}"
        )
        await github.rest.issues.async_update(
            owner=owner, repo=repo, issue_number=issue_number, title=title
        )


async def post_comment(
    github: GitHub,
    owner: str,
    repo: str,
    issue_number: int,
    text: str,
) -> int:
    logger.debug(f"Posting comment to issue #{issue_number}")
    response = await github.rest.issues.async_create_comment(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        body=text,
    )
    return response.parsed_data.id


async def close_issue(github: GitHub, owner: str, repo: str, issue_number: int) -> None:
    logger.debug(f"Closing issue #{issue_number}")
    await github.rest.issues.async_update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )
