import asyncio
import json
import logging
from operator import attrgetter
from pathlib import Path
from typing import Generator, Iterable, cast

import click
from githubkit import GitHub
import yaml
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

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
@click.option(
    "--user-agent", default="JuniorGuruBot (+https://junior.guru)", help="User agent."
)
@click.option(
    "--event",
    "event_path",
    envvar="GITHUB_EVENT_PATH",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
@click.option("--github-api-key", envvar="GITHUB_API_KEY", help="GitHub API key.")
def issue(
    issue_number: int,
    owner_repo: str,
    user_agent: str,
    event_path: Path | None = None,
    github_api_key: str | None = None,
):
    logger.info(f"Using GitHub token: {'yes' if github_api_key else 'no'}")
    logger.info(f"Event payload path: {event_path}")
    if issue_number is None:
        if event_path is None:
            logger.error("Issue number or event payload path is required")
            raise click.Abort()
        payload = json.loads(event_path.read_text())
        issue_number = payload["issue"]["number"]
    logger.info(f"Processing issue #{issue_number}")
    print(
        asyncio.run(
            fetch_username_from_issue(
                owner_repo, issue_number, user_agent, github_api_key
            )
        )
    )


async def fetch_username_from_issue(
    owner_repo: str,
    issue_number: int,
    user_agent: str,
    github_api_key: str | None = None,
) -> str | None:
    logger.debug(f"GitHub repository: {owner_repo}")
    owner, repo = owner_repo.split("/")

    logger.debug(f"User agent: {user_agent}")
    async with GitHub(github_api_key, user_agent=user_agent) as github:
        response = await github.rest.issues.async_get(
            owner=owner, repo=repo, issue_number=issue_number
        )
    issue = response.parsed_data
    label_names = {label.name for label in issue.labels}  # type: ignore

    if issue.state == "closed":
        logger.warning(f"Issue #{issue_number} is closed")
        return
    if "check" not in label_names:
        logger.warning(f"Issue #{issue_number} is missing the 'check' label")
        return

    logger.info(f"Title: {issue.title}")
    logger.info(f"Body: {issue.body!r}")
