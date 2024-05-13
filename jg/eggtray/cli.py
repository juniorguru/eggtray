import asyncio
import logging
from pathlib import Path

import click
from jg.hen.core import check_profile_url

from jg.eggtray.profile import parse


logger = logging.getLogger("jg.eggtray")


@click.command()
@click.argument("profiles_dir", type=Path)
@click.option("-d", "--debug", default=False, is_flag=True, help="Show debug logs.")
@click.option("--github-api-key", envvar="GITHUB_API_KEY", help="GitHub API key.")
def main(profiles_dir: Path, debug: bool, github_api_key: str | None = None):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    profiles_paths = profiles_dir.glob("*.yml")
    if not profiles_paths:
        logger.error("No profiles found in the directory")
        raise click.Abort()
    profiles = [load_profile(profile_path) for profile_path in profiles_paths]
    asyncio.run(check_profiles(profiles, github_api_key=github_api_key))


def load_profile(profile_path: Path) -> dict:
    profile = parse(profile_path.read_text())
    profile["username"] = profile_path.stem
    profile["url"] = f"http://github.com/{profile_path.stem}"
    return profile


async def check_profiles(profiles: list[dict], github_api_key: str | None = None):
    for profile in profiles:
        logger.info(profile["url"])
        summary = await check_profile_url(
            profile["url"], raise_on_error=True, github_api_key=github_api_key
        )
        logger.info(summary)
