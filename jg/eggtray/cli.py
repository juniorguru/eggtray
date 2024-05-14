import asyncio
import json
import logging
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import click
from jg.hen.core import Summary, check_profile_url

from jg.eggtray.profile import parse


logger = logging.getLogger("jg.eggtray")


@click.command()
@click.argument("src_dir", default="profiles", type=Path)
@click.argument("dest_dir", default="output", type=Path)
@click.option("-d", "--debug", default=False, is_flag=True, help="Show debug logs.")
@click.option("-o", "--overwrite/--no-overwrite", default=False)
@click.option("--github-api-key", envvar="GITHUB_API_KEY", help="GitHub API key.")
def main(
    src_dir: Path,
    dest_dir: Path,
    debug: bool,
    overwrite: bool,
    github_api_key: str | None = None,
):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    if not overwrite and src_dir.exists():
        logger.error(f"Destination directory {dest_dir} exists")
        raise click.Abort()
    shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    profiles_paths = list(src_dir.glob("*.yml"))
    if not profiles_paths:
        logger.error("No profiles found in the directory")
        raise click.Abort()
    logger.info(f"Found {len(profiles_paths)} profiles")
    profiles = [load_yaml(profile_path) for profile_path in profiles_paths]
    profiles = asyncio.run(add_github_data(profiles, github_api_key=github_api_key))

    logger.info(f"Writing {len(profiles)} profiles")
    for profile in profiles:
        dest_path = dest_dir / "profiles" / f"{profile['username']}.json"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(to_json(profile))
        logger.info(f"Profile {profile['username']!r} saved to {dest_path}")
    dest_path = dest_dir / "profiles.json"
    dest_path.write_text(to_json([profile["username"] for profile in profiles]))
    logger.info(f"Profiles index saved to {dest_path}")


def load_yaml(profile_path: Path) -> dict:
    profile = parse(profile_path.read_text())
    username = profile_path.stem.lower()
    profile["username"] = username
    profile["url"] = f"https://github.com/{username}"
    return profile


async def add_github_data(
    profiles: list[dict], github_api_key: str | None = None
) -> list[dict]:
    profiles_mapping = {profile["username"]: profile for profile in profiles}
    tasks = [
        check_profile_url(
            profile["url"], raise_on_error=True, github_api_key=github_api_key
        )
        for profile in profiles_mapping.values()
    ]
    for profile_checking in asyncio.as_completed(tasks):
        summary: Summary = await profile_checking
        if summary.error:
            raise summary.error
        logger.info(f"Processing {summary.username!r} done")

        profile = profiles_mapping[summary.username]
        profile["outcomes_stats"] = dict(
            Counter([outcome.status for outcome in summary.outcomes])
        )
        profile["insights"] = summary.insights
    return list(profiles_mapping.values())


def to_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=serialize)


def serialize(obj: Any) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(
        f"Object of type {obj.__class__.__name__} is not JSON serializable."
    )
