import asyncio
import logging
from operator import attrgetter
from pathlib import Path
from typing import Generator, Iterable

import click
import yaml
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

from jg.eggtray.models import Document, Profile, Response


logger = logging.getLogger("jg.eggtray")


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
