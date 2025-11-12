import logging
import re
from typing import cast

from githubkit import GitHub
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


async def fetch_report_issues(
    github: GitHub,
    owner: str,
    repo: str,
    label: str,
) -> list[Issue]:
    logger.debug("Searching for report issues")
    response = await github.rest.issues.async_list_for_repo(
        owner=owner, repo=repo, state="open", labels=label
    )
    return response.parsed_data


async def create_issue(
    github: GitHub,
    owner: str,
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> Issue:
    logger.debug(f"Creating issue in {owner}/{repo} with title {title!r}")
    response = await github.rest.issues.async_create(
        owner=owner,
        repo=repo,
        title=title,
        body=body,
        labels=labels or [],  # type: ignore
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


async def update_issue(
    github: GitHub,
    owner: str,
    repo: str,
    issue_number: int,
    title: str | None = None,
    body: str | None = None,
):
    logger.debug(f"Checking contents of issue #{issue_number}")
    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    issue: Issue = response.parsed_data
    data = {}
    if title is not None and issue.title != title:
        logger.debug(
            f"Updating title of issue #{issue_number} from {issue.title!r} to {title!r}"
        )
        data["title"] = title
    if body is not None and issue.body != body:
        logger.debug(f"Updating body of issue #{issue_number}")
        data["body"] = body
    if data:
        await github.rest.issues.async_update(
            owner=owner, repo=repo, issue_number=issue_number, **data
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
