import asyncio
import json
import logging
import re
from operator import attrgetter
from pathlib import Path
from typing import Generator, Iterable

import click
import yaml
from githubkit import BaseAuthStrategy, GitHub
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

from jg.eggtray.github_app import github_auth
from jg.eggtray.models import Document, Profile, Response


logger = logging.getLogger("jg.eggtray")


@click.group()
@click.option("-d", "--debug", default=False, is_flag=True, help="Show debug logs.")
def main(
    debug: bool,
):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


@main.command()
@click.argument(
    "documents_dir",
    default="profiles",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=Path),
)
@click.argument(
    "output_path",
    default="output/profiles.json",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
)
@click.option("--github-api-key", envvar="GITHUB_API_KEY", help="GitHub API key.")
def build(
    documents_dir: Path,
    output_path: Path,
    github_api_key: str | None = None,
):
    logger.info(f"Using GitHub token: {'yes' if github_api_key else 'no'}")
    logger.info(f"Output path: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Profile documents directory: {documents_dir}")
    documents_paths = list(documents_dir.glob("*.yml"))
    if not documents_paths:
        logger.error("No profile documents found in the directory")
        raise click.Abort()
    logger.info(f"Found {len(documents_paths)} profile documents")
    documents = list(map(load_document, documents_paths))

    logger.info("Analyzing GitHub profiles")
    summaries = asyncio.run(fetch_summaries(documents, github_api_key=github_api_key))

    logger.info("Creating profiles")
    profiles = list(create_profiles(documents, summaries))

    logger.info(f"Writing {len(profiles)} profiles to {output_path}")
    response = Response.create(profiles)
    output_path.write_text(response.model_dump_json(indent=2))


def load_document(profile_path: Path) -> Document:
    return Document.create(
        profile_path.stem.lower(),
        yaml.safe_load(profile_path.read_text()),
    )


async def fetch_summaries(
    documents: Iterable[Document], github_api_key: str | None = None
) -> list[Summary]:
    documents_mapping = {document.username: document for document in documents}
    tasks = [
        check_profile_url(
            document.github_url, raise_on_error=True, github_api_key=github_api_key
        )
        for document in documents_mapping.values()
    ]
    summaries = []
    for github_checking in asyncio.as_completed(tasks):
        summary: Summary = await github_checking
        if summary.error:
            raise summary.error
        logger.info(f"Processing {summary.username!r} done")
        summaries.append(summary)
    return summaries


def create_profiles(
    documents: Iterable[Document], summaries: Iterable[Summary]
) -> Generator[Profile, None, None]:
    for document, github in zip(
        sorted(documents, key=attrgetter("username")),
        sorted(summaries, key=attrgetter("username")),
    ):
        yield Profile.create(document, github)


@main.command()
@click.argument("issue_number", type=int, required=False)
@click.option(
    "--repo", "owner_repo", default="juniorguru/eggtray", help="GitHub repository."
)
@github_auth
@click.option(
    "--event",
    "event_path",
    envvar="GITHUB_EVENT_PATH",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
def issue(
    issue_number: int,
    owner_repo: str,
    github_auth: BaseAuthStrategy,
    event_path: Path | None = None,
):
    logger.info(f"Event payload path: {event_path}")
    if issue_number is None:
        if event_path is None:
            logger.error("Issue number or event payload path is required")
            raise click.Abort()
        payload = json.loads(event_path.read_text())
        issue_number = payload["issue"]["number"]
    logger.info(f"Processing issue #{issue_number}")
    asyncio.run(process_issue(github_auth, owner_repo, issue_number))


async def process_issue(
    github_auth: BaseAuthStrategy,
    owner_repo: str,
    issue_number: int,
):
    async with GitHub(auth=github_auth) as github:
        logger.info(f"Fetching https://github.com/{owner_repo}/issues/{issue_number}")
        username = await fetch_username_from_issue(github, owner_repo, issue_number)
        if username:
            title = f"Profile check: {username}"
            await update_title(github, owner_repo, issue_number, title)
            comment_id = await post_comment(github, owner_repo, issue_number)
            profile_url = f"https://github.com/{username}"
            logger.info(f"Checking profile: {profile_url}")
            summary: Summary = await check_profile_url(profile_url, github=github)
            logger.info("Posting summary")
            await post_summary(github, owner_repo, comment_id, summary)
            await close_issue(github, owner_repo, issue_number)
        else:
            logger.info("Skipping issue as not relevant")


async def fetch_username_from_issue(
    github: GitHub, owner_repo: str, issue_number: int
) -> str | None:
    logger.debug(f"GitHub repository: {owner_repo}")
    owner, repo = owner_repo.split("/")

    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    issue = response.parsed_data
    label_names = {label.name for label in issue.labels}  # type: ignore

    # if issue.state == "closed":
    #     logger.warning(f"Issue #{issue_number} is closed")
    #     return
    if "check" not in label_names:
        logger.warning(f"Issue #{issue_number} is missing the 'check' label")
        return
    if not issue.body or not issue.body.strip():
        logger.warning(f"Issue #{issue_number} is missing a body")
        return

    logger.debug(f"Getting username from issue #{issue_number}: {issue.body!r}")
    if match := re.search(r"\bcheck\s+@(\w+)", issue.body, re.I):
        return match.group(1)


async def update_title(github: GitHub, owner_repo: str, issue_number: int, title: str):
    owner, repo = owner_repo.split("/")
    logger.debug(f"Checking title of issue #{issue_number}")
    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    issue = response.parsed_data
    if issue.title != title:
        logger.debug(
            f"Updating title of issue #{issue_number} from {issue.title!r} to {title!r}"
        )
        await github.rest.issues.async_update(
            owner=owner, repo=repo, issue_number=issue_number, title=title
        )


async def post_comment(github: GitHub, owner_repo: str, issue_number: int) -> int:
    owner, repo = owner_repo.split("/")
    logger.debug(f"Posting comment to issue #{issue_number}")
    response = await github.rest.issues.async_create_comment(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        body="Checking the profile...",
    )
    return response.parsed_data.id


async def post_summary(
    github: GitHub, owner_repo: str, comment_id: int, summary: Summary
) -> None:
    owner, repo = owner_repo.split("/")
    logger.debug(
        f"Updating comment #{comment_id} with summary:\n{summary.model_dump_json(indent=2)}"
    )
    await github.rest.issues.async_update_comment(
        owner=owner,
        repo=repo,
        comment_id=comment_id,
        body=(
            f"<details>\n\n"
            f"<summary>JSON</summary>\n\n"
            f"```json\n{summary.model_dump_json(indent=2)}\n```\n\n"
            f"</details>"
        ),
    )


async def close_issue(github: GitHub, owner_repo: str, issue_number: int):
    owner, repo = owner_repo.split("/")
    logger.debug(f"Closing issue #{issue_number}")
    await github.rest.issues.async_update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )
