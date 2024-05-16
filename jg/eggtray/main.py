import asyncio
import logging
from operator import attrgetter
from pathlib import Path
from typing import Any, Generator, Iterable, Self

import click
import yaml
from jg.hen.core import check_profile_url
from jg.hen.models import Outcome, Status, Summary
from pydantic import BaseModel

from jg.eggtray.topics import Topic


logger = logging.getLogger("jg.eggtray")


class Document(BaseModel):
    username: str
    github_url: str
    discord_id: int | None = None
    name: str | None = None
    bio: str | None = None
    location: str | None = None
    topics: set[Topic] = set()


class Profile(BaseModel):
    name: str | None = None
    bio: str | None = None
    avatar_url: str
    location: str | None = None
    discord_id: int | None = None
    github_username: str
    github_url: str
    linkedin_url: str | None = None
    outcomes: list[Outcome]
    is_ready: bool

    @classmethod
    def create(cls, document: Document, summary: Summary) -> Self:
        usernames = [document.username, summary.username]
        if len(set(usernames)) != 1:
            raise ValueError(f"Usernames do not match: {usernames!r}")
        username = usernames[0]

        return cls(
            name=document.name or summary.info.name or username,
            bio=document.bio or summary.info.bio,
            avatar_url=summary.info.avatar_url,
            location=document.location or summary.info.location,
            discord_id=document.discord_id,
            github_username=username,
            github_url=document.github_url,
            linkedin_url=summary.info.linkedin_url,
            outcomes=summary.outcomes,
            is_ready=all(
                outcome.status != Status.ERROR for outcome in summary.outcomes
            ),
        )


class Response(BaseModel):
    count: int
    items: list[Profile]
    item_schema: dict[str, Any]


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

    logger.info("Analyzing GitHub profiles")
    summaries = asyncio.run(fetch_summaries(documents, github_api_key=github_api_key))

    logger.info("Creating profiles")
    profiles = list(create_profiles(documents, summaries))

    logger.info(f"Writing {len(profiles)} profiles to {output_path}")
    response = Response(
        count=len(profiles),
        items=profiles,
        item_schema=Profile.model_json_schema(),
    )
    output_path.write_text(response.model_dump_json(indent=2))


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


def load_document(profile_path: Path) -> Document:
    return parse_document(profile_path.stem.lower(), profile_path.read_text())


def parse_document(username: str, yaml_text: str) -> Document:
    return Document(
        username=username,
        github_url=f"https://github.com/{username}",
        **yaml.safe_load(yaml_text),
    )
