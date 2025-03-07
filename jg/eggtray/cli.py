import asyncio
import json
import logging
from operator import attrgetter
from pathlib import Path
from typing import Generator, Iterable

import click
import yaml
from githubkit import BaseAuthStrategy
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

from jg.eggtray.github_app import github_auth
from jg.eggtray.issue import process_issue
from jg.eggtray.models import Document, Profile, Response


logger = logging.getLogger(__name__)


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
    "-s",
    "--state",
    "states",
    multiple=True,
    default=["open"],
    type=click.Choice(["open", "closed"]),
    help="Allowed GitHub issue states, comma-separated. Useful for debugging.",
)
@github_auth
@click.option(
    "--github-event",
    "github_event_path",
    envvar="GITHUB_EVENT_PATH",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
    help="Location of GitHub's event payload. Relevant only inside GitHub Actions run.",
)
@click.option(
    "--github-run-id",
    envvar="GITHUB_RUN_ID",
    type=int,
    help="GitHub run ID. Relevant only inside GitHub Actions run.",
)
def issue(
    issue_number: int,
    owner_repo: str,
    states: list[str],
    github_auth: BaseAuthStrategy,
    github_event_path: Path | None = None,
    github_run_id: int | None = None,
):
    logger.info(f"Event payload path: {github_event_path}")
    if issue_number is None:
        if github_event_path is None:
            logger.error("Issue number or event payload path is required")
            raise click.Abort()
        payload = json.loads(github_event_path.read_text())
        logger.info(f"Event action: {payload['action']}")
        issue_number = payload["issue"]["number"]
    logger.info(f"Processing issue #{issue_number}")
    owner, repo = owner_repo.split("/")
    logger.debug(f"GitHub repository: {owner}/{repo}")
    asyncio.run(
        process_issue(
            github_auth, owner, repo, issue_number, states=states, run_id=github_run_id
        )
    )
