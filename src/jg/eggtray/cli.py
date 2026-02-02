import asyncio
import json
import logging
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path
from pprint import pformat
from typing import Any, Coroutine, Generator, Iterable, TypeVar, cast

import click
import yaml
from diskcache import Cache
from githubkit import BaseAuthStrategy
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

from jg.eggtray.checks import check_profile
from jg.eggtray.github_app import github_auth
from jg.eggtray.models import Listing, Profile, ProfileConfig
from jg.eggtray.reports import report_profiles


T = TypeVar("T")


logger = logging.getLogger(__name__)


@dataclass
class ContextObj:
    loop: asyncio.AbstractEventLoop | None = None

    def run_async(self, coro: Coroutine[Any, Any, T]) -> T:
        if not self.loop:
            raise RuntimeError("Event loop not initialized")
        return self.loop.run_until_complete(coro)


@click.group()
@click.option("-d", "--debug", default=False, is_flag=True, help="Show debug logs.")
@click.pass_context
def main(context: click.Context, debug: bool):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    obj = context.ensure_object(ContextObj)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    obj.loop = asyncio.get_event_loop()
    context.call_on_close(loop.close)


@main.command()
@click.pass_obj
@click.argument(
    "configs_dir",
    default="profiles",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=Path),
)
@click.argument(
    "output_dir",
    default="output",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=Path),
)
@click.option(
    "--cache-dir",
    default=".cache",
    type=click.Path(dir_okay=True, file_okay=False, path_type=Path),
)
@click.option("--cache-hours", default=3, type=int)
@click.option("--github-api-key", envvar="GITHUB_API_KEY")
def build(
    obj: ContextObj,
    configs_dir: Path,
    output_dir: Path,
    cache_dir: Path,
    cache_hours: int,
    github_api_key: str | None = None,
):
    logger.info(f"Using GitHub token: {'yes' if github_api_key else 'no'}")
    logger.info(f"Output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Cache: {cache_dir}")
    cache = Cache(cache_dir)

    logger.info(f"Profile configs directory: {configs_dir}")
    configs_paths = sorted(configs_dir.glob("*.yml"))
    if not configs_paths:
        logger.error("No profile configs found in the directory")
        raise click.Abort()
    logger.info(f"Found {len(configs_paths)} profile configs")
    configs = list(map(load_profile_config, configs_paths))

    cache_key = get_cache_key(configs)
    if summaries := cast(list[Summary], cache.get(cache_key)):
        logger.warning("Using cached summaries of GitHub profiles")
    else:
        logger.info("Analyzing GitHub profiles")
        summaries = obj.run_async(
            fetch_summaries(configs, github_api_key=github_api_key)
        )
        cache.set(cache_key, summaries, expire=cache_hours * 3600)

    logger.info("Creating profiles")
    profiles = list(create_profiles(configs, summaries))

    profiles_json_path = output_dir / "profiles.json"
    logger.info(f"Writing {len(profiles)} profiles to {profiles_json_path}")
    listing = Listing.create(profiles)
    profiles_json_path.write_text(listing.model_dump_json(indent=2))


def load_profile_config(profile_path: Path) -> ProfileConfig:
    return ProfileConfig.create(
        profile_path.stem.lower(),
        yaml.safe_load(profile_path.read_text()),
    )


def get_cache_key(configs: Iterable[ProfileConfig]) -> str:
    return "|".join(sorted(config.username.lower() for config in configs))


async def fetch_summaries(
    configs: Iterable[ProfileConfig], github_api_key: str | None = None
) -> list[Summary]:
    configs_mapping = {config.username: config for config in configs}
    tasks = [
        check_profile_url(
            config.github_url, raise_on_error=True, github_api_key=github_api_key
        )
        for config in configs_mapping.values()
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
    configs: Iterable[ProfileConfig], summaries: Iterable[Summary]
) -> Generator[Profile, None, None]:
    for config, github in zip(
        sorted(configs, key=attrgetter("username")),
        sorted(summaries, key=attrgetter("username")),
    ):
        yield Profile.create(config, github)


@main.command()
@click.pass_obj
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
def check(
    obj: ContextObj,
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
    if run_url := get_run_url(owner, repo, github_run_id):
        logger.info(f"Working inside {run_url}")
    obj.run_async(
        check_profile(
            github_auth,
            owner,
            repo,
            issue_number,
            states=states,
            run_url=run_url,
        )
    )


@main.command()
@click.pass_obj
@click.argument(
    "data_path",
    default="output/profiles.json",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
@click.option(
    "--repo", "owner_repo", default="juniorguru/eggtray", help="GitHub repository."
)
@click.option("--label", default="profile not ready", help="GitHub issue label.")
@github_auth
@click.option(
    "--github-run-id",
    envvar="GITHUB_RUN_ID",
    type=int,
    help="GitHub run ID. Relevant only inside GitHub Actions run.",
)
def report(
    obj: ContextObj,
    data_path: Path,
    owner_repo: str,
    label: str,
    github_auth: BaseAuthStrategy,
    github_run_id: int | None = None,
):
    logger.debug(f"Data path: {data_path}")
    listing = Listing.model_validate_json(data_path.read_text())
    logger.debug(f"Profiles loaded: {len(listing.items)}")
    owner, repo = owner_repo.split("/")
    logger.debug(f"GitHub repository: {owner}/{repo}")
    if run_url := get_run_url(owner, repo, github_run_id):
        logger.info(f"Working inside {run_url}")
    issues_by_username = obj.run_async(
        report_profiles(
            github_auth,
            owner,
            repo,
            listing.items,
            label=label,
            run_url=run_url,
        )
    )
    issue_urls_by_username = {
        username: issue.html_url for username, issue in issues_by_username.items()
    }
    logger.debug(f"Updates:\n{pformat(issue_urls_by_username)}")
    for profile in listing.items:
        profile.report_url = issue_urls_by_username.get(profile.github_username)
    logger.info(f"Saving updated profiles to {data_path}")
    data_path.write_text(listing.model_dump_json(indent=2))


def get_run_url(owner: str, repo: str, run_id: int | None = None) -> str | None:
    if run_id:
        return f"https://github.com/{owner}/{repo}/actions/runs/{run_id}"
    return None
