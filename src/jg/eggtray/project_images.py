import asyncio
from io import BytesIO
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from PIL import Image
import httpx
from jg.hen.models import ProjectInfo
from slugify import slugify

from jg.eggtray.models import Profile


logger = logging.getLogger(__name__)


_downloads_limit = asyncio.Semaphore(5)

_screenshots_limit = asyncio.Semaphore(2)  # TODO


@dataclass
class ImageRequest:
    project_name: str
    url: str
    screenshot: bool = False


async def create_project_images(profiles: list[Profile], output_dir: Path):
    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(create_project_image(client, project, output_dir))
            for profile in profiles
            for project in profile.projects
        ]
        await asyncio.gather(*tasks)


async def create_project_image(
    client: httpx.AsyncClient,
    project: ProjectInfo,
    output_dir: Path,
) -> None:
    for attempt_no, image_request in enumerate(
        collect_image_requests(project), start=1
    ):
        logger.info(
            f"Attempt #{attempt_no} to download image for {project.name}: {image_request.url}"
        )
        if (image_bytes := await try_download(client, image_request.url)) and (
            image_path := await try_save(image_bytes, output_dir, project.name)
        ):
            logger.info(
                f"Downloaded image for project {project.name} from {image_request.url}, "
                f"saved to {image_path.relative_to(output_dir)}"
            )
            return


def collect_image_requests(project: ProjectInfo) -> Generator[ImageRequest, None, None]:
    for image_url in project.readme_image_urls:
        yield ImageRequest(project_name=project.name, url=image_url)
    if demo_url := project.demo_url:
        yield ImageRequest(project_name=project.name, url=demo_url, screenshot=True)


async def try_download(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        async with _downloads_limit:
            response = await client.get(
                url,
                follow_redirects=True,
                timeout=10.0,
            )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        logger.debug(f"Downloaded {content_type!r} from {url}")
        return response.content
    except Exception as e:
        logger.debug(f"Error while downloading {url}: {e}")
        return None


async def try_save(
    image_bytes: bytes, output_dir: Path, project_name: str
) -> Path | None:
    try:
        image = Image.open(BytesIO(image_bytes))
        image_path = output_dir / f"{slugify(project_name)}.webp"
        image.save(
            image_path,
            format="WEBP",
            optimize=True,
            quality=80,
            method=6,
            lossless=False,
        )
        return image_path
    except Exception as e:
        logger.debug(f"Error while saving image for {project_name}: {e}")
        return None
