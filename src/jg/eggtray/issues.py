import logging
import re
from typing import cast

from githubkit import GitHub
from githubkit.versions.latest.models import (
    DiffEntry,
    Issue,
    IssuePropLabelsItemsOneof1 as IssueLabel,
    PullRequest,
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


async def fetch_pull_request(
    github: GitHub, owner: str, repo: str, pr_number: int
) -> PullRequest:
    logger.debug(f"Fetching pull request #{pr_number}")
    response = await github.rest.pulls.async_get(
        owner=owner, repo=repo, pull_number=pr_number
    )
    return response.parsed_data


async def fetch_pull_request_files(
    github: GitHub, owner: str, repo: str, pr_number: int
) -> list[DiffEntry]:
    logger.debug(f"Fetching files of pull request #{pr_number}")
    return [
        diff_entry
        async for diff_entry in github.paginate(
            github.rest.pulls.async_list_files,
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            per_page=100,
        )
    ]


async def close_pull_request(
    github: GitHub, owner: str, repo: str, pr_number: int
) -> None:
    logger.debug(f"Closing pull request #{pr_number}")
    await github.rest.pulls.async_update(
        owner=owner, repo=repo, pull_number=pr_number, state="closed"
    )


async def find_comment(
    github: GitHub,
    owner: str,
    repo: str,
    issue_number: int,
    author: str,
    marker: str,
) -> int | None:
    logger.debug(
        f"Looking for a comment by @{author} with {marker!r} in #{issue_number}"
    )
    async for comment in github.paginate(
        github.rest.issues.async_list_comments,
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        per_page=100,
    ):
        if (
            comment.user
            and comment.user.login == author
            and marker in (comment.body or "")
        ):
            return comment.id
    return None


async def fetch_event_actors(
    github: GitHub, owner: str, repo: str, issue_number: int, event: str
) -> list[str]:
    logger.debug(f"Fetching actors of {event!r} events in #{issue_number}")
    actors = []
    page = 1
    while True:
        response = await github.rest.issues.async_list_events(
            owner=owner, repo=repo, issue_number=issue_number, per_page=100, page=page
        )
        # githubkit can't parse all event types, hence the raw JSON
        events = response.json()
        actors += [
            item["actor"]["login"]
            for item in events
            if item["event"] == event and item.get("actor")
        ]
        if len(events) < 100:
            return actors
        page += 1


async def update_comment(
    github: GitHub, owner: str, repo: str, comment_id: int, text: str
) -> None:
    logger.debug(f"Updating comment {comment_id}")
    await github.rest.issues.async_update_comment(
        owner=owner, repo=repo, comment_id=comment_id, body=text
    )
