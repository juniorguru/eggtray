import asyncio
import json
import logging
from collections import Counter
from datetime import date, datetime
from operator import attrgetter
from pathlib import Path
from typing import Any, Generator, Iterable, Self

import click
import yaml
from jg.hen.core import Summary, check_profile_url
from pydantic import BaseModel


logger = logging.getLogger("jg.eggtray")


class DocumentData(BaseModel):
    username: str
    url: str
    discord_id: int


class GitHubData(BaseModel):
    username: str
    outcomes_stats: dict[str, int]
    insights: dict[str, Any]


class Profile(BaseModel):
    username: str
    url: str
    discord_id: int
    outcomes_stats: dict[str, int]
    insights: dict[str, Any]

    @classmethod
    def create(cls, document: DocumentData, github: GitHubData) -> Self:
        usernames = [document.username, github.username]
        if len(set(usernames)) != 1:
            raise ValueError(f"Usernames do not match: {usernames!r}")
        return cls(
            username=document.username,
            url=document.url,
            discord_id=document.discord_id,
            outcomes_stats=github.outcomes_stats,
            insights=github.insights,
        )


class Response(BaseModel):
    profiles: list[Profile]
    count: int
    schema: dict[str, Any]


@click.command()
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
@click.option("-d", "--debug", default=False, is_flag=True, help="Show debug logs.")
@click.option("--github-api-key", envvar="GITHUB_API_KEY", help="GitHub API key.")
def main(
    documents_dir: Path,
    output_path: Path,
    debug: bool,
    github_api_key: str | None = None,
):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
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

    logger.info("Fetching corresponding GitHub data")
    githubs = asyncio.run(fetch_github(documents, github_api_key=github_api_key))

    logger.info("Creating profiles")
    profiles = list(create_profiles(documents, githubs))

    logger.info(f"Writing {len(profiles)} profiles to {output_path}")
    response = Response(
        profiles=profiles,
        count=len(profiles),
        schema=Profile.model_json_schema(),
    )
    output_path.write_text(response.model_dump_json())


async def fetch_github(
    documents: Iterable[DocumentData], github_api_key: str | None = None
) -> list[GitHubData]:
    documents_mapping = {document.username: document for document in documents}
    tasks = [
        check_profile_url(
            profile.url, raise_on_error=True, github_api_key=github_api_key
        )
        for profile in documents_mapping.values()
    ]
    githubs = []
    for github_checking in asyncio.as_completed(tasks):
        summary: Summary = await github_checking
        if summary.error:
            raise summary.error
        logger.info(f"Processing {summary.username!r} done")
        githubs.append(
            GitHubData(
                username=summary.username,
                outcomes_stats=dict(
                    Counter([outcome.status for outcome in summary.outcomes])
                ),
                insights=summary.insights,
            )
        )
    return githubs


def create_profiles(
    documents: Iterable[DocumentData], githubs: Iterable[GitHubData]
) -> Generator[Profile, None, None]:
    for document, github in zip(
        sorted(documents, key=attrgetter("username")),
        sorted(githubs, key=attrgetter("username")),
    ):
        yield Profile.create(document, github)


def load_document(profile_path: Path) -> DocumentData:
    return parse_document(profile_path.stem.lower(), profile_path.read_text())


def parse_document(username: str, yaml_text: str) -> DocumentData:
    return DocumentData(
        username=username,
        url=f"https://github.com/{username}",
        **yaml.safe_load(yaml_text),
    )
