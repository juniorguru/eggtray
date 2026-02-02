import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import httpx
from jg.hen.models import ProjectInfo

from jg.eggtray.models import Profile


logger = logging.getLogger(__name__)

limit = asyncio.Semaphore(5)


@dataclass
class ImageRequest:
    project_name: str
    url: str
    screenshot: bool = False


async def create_project_images(
    profiles: list[Profile], output_dir: Path, github_api_key: str | None = None
):
    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(
                create_project_image(
                    client, project, output_dir, github_api_key=github_api_key
                )
            )
            for profile in profiles
            for project in profile.projects
        ]
        await asyncio.gather(*tasks)


async def create_project_image(
    client: httpx.AsyncClient,
    project: ProjectInfo,
    output_dir: Path,
    github_api_key: str | None = None,
) -> None:
    for attempt_no, image_request in enumerate(
        collect_image_requests(project), start=1
    ):
        logger.info(
            f"Attempt #{attempt_no} to download image for {project.name}: {image_request.url}"
        )
        if image_bytes := await try_download(
            client, image_request.url, github_api_key=github_api_key
        ):
            # TODO save image_bytes to output_dir with appropriate filename
            logger.info(
                f"Downloaded image for project {project.name} from {image_request.url}"
            )
            break


def collect_image_requests(project: ProjectInfo) -> Generator[ImageRequest, None, None]:
    for image_url in project.readme_image_urls:
        yield ImageRequest(project_name=project.name, url=image_url)
    if demo_url := project.demo_url:
        yield ImageRequest(project_name=project.name, url=demo_url, screenshot=True)


def is_private_github_url(url: str) -> bool:
    return url.startswith("https://private-user-images.githubusercontent.com/")


async def try_download(
    client: httpx.AsyncClient, url: str, github_api_key: str | None = None
) -> bytes | None:
    headers = {}
    if github_api_key and is_private_github_url(url):
        headers["Authorization"] = f"Bearer {github_api_key}"
    try:
        async with limit:
            response = await client.get(
                url,
                headers=headers,
                follow_redirects=True,
                timeout=10.0,
            )
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.debug(f"Error while downloading {url}: {e}")
        return None
