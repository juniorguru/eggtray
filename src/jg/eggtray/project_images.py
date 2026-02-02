import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import AsyncGenerator, Generator

import httpx
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.async_api import async_playwright
from playwright.async_api._generated import Browser
from slugify import slugify

from jg.eggtray.models import Profile, ProjectInfo


THUMBNAIL_SIZE = (1280, 800)


logger = logging.getLogger(__name__)


_downloads_limit = asyncio.Semaphore(5)

_screenshots_limit = asyncio.Semaphore(2)


@dataclass
class ImageRequest:
    project_name: str
    url: str
    screenshot: bool = False


@asynccontextmanager
async def start_browser() -> AsyncGenerator[Browser | None, None]:
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch()
        except PlaywrightError as e:
            logger.error(f"Failed to launch browser: {e}")
            yield None
        else:
            try:
                yield browser
            finally:
                await browser.close()


async def download_project_images(
    profiles: list[Profile], output_dir: Path
) -> list[tuple[ProjectInfo, Path]]:
    async with httpx.AsyncClient() as http_client, start_browser() as browser:
        tasks = [
            asyncio.create_task(
                download_project_image(http_client, browser, project, output_dir)
            )
            for profile in profiles
            for project in profile.projects
        ]
        results = await asyncio.gather(*tasks)
    return list(filter(None, results))


async def download_project_image(
    http_client: httpx.AsyncClient,
    browser: Browser | None,
    project: ProjectInfo,
    output_dir: Path,
) -> tuple[ProjectInfo, Path] | None:
    image_requests = list(collect_image_requests(project))
    for attempt_no, image_request in enumerate(image_requests, start=1):
        logger.info(
            f"Attempt {attempt_no}/{len(image_requests)} to get an image for {project.name}: "
            f"{image_request.url} ({'image' if not image_request.screenshot else 'screenshot'})"
        )
        if image_request.screenshot:
            if browser:
                image_bytes = await try_screenshot(browser, image_request.url)
            else:
                logger.warning("No browser, skipping screenshot")
                image_bytes = None
        else:
            image_bytes = await try_download(http_client, image_request.url)

        if image_bytes and (
            image_path := await try_save(image_bytes, output_dir, project.name)
        ):
            logger.info(
                f"Downloaded image for project {project.name} from {image_request.url}, "
                f"saved to {image_path.relative_to(output_dir)}"
            )
            return (project, image_path)
    return None


def collect_image_requests(project: ProjectInfo) -> Generator[ImageRequest, None, None]:
    for image_url in project.readme_image_urls:
        yield ImageRequest(project_name=project.name, url=image_url)
    if demo_url := project.demo_url:
        yield ImageRequest(project_name=project.name, url=demo_url, screenshot=True)


async def try_download(
    http_client: httpx.AsyncClient, url: str, timeout_s: float = 10.0
) -> bytes | None:
    try:
        async with _downloads_limit:
            response = await http_client.get(
                url,
                follow_redirects=True,
                timeout=timeout_s,
            )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        logger.debug(f"Downloaded {content_type!r} from {url}")
        return response.content
    except Exception as e:
        logger.debug(f"Error while downloading {url}: {e}")
        return None


async def try_screenshot(
    browser: Browser,
    url: str,
    timeout_s: float = 40.0,
    min_bytes: int = 10000,
    width: int = 1280,
    height: int = 720,
) -> bytes | None:
    try:
        async with _screenshots_limit:
            page = await browser.new_page(viewport={"width": width, "height": height})
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_s * 1000)
                image_bytes = await page.screenshot(full_page=True)
            finally:
                await page.close()
        if len(image_bytes) < min_bytes:
            raise Exception(f"Suspiciously small image: {len(image_bytes)} bytes")
        return image_bytes
    except Exception as e:
        logger.debug(f"Error while screenshotting {url}: {e}")
        return None


async def try_save(
    image_bytes: bytes, output_dir: Path, project_name: str
) -> Path | None:
    image_path = output_dir / f"{slugify(project_name)}.webp"
    try:
        image = Image.open(BytesIO(image_bytes))

        if image.format in ("PNG", "JPEG"):
            image = image.convert("RGB")

        target_ratio = THUMBNAIL_SIZE[0] / THUMBNAIL_SIZE[1]
        current_ratio = image.width / image.height

        if current_ratio > target_ratio:
            # too wide → crop sides, centered
            new_width = int(image.height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))
        elif current_ratio < target_ratio:
            # too tall (screenshots) → crop from the top
            new_height = int(image.width / target_ratio)
            image = image.crop((0, 0, image.width, new_height))

        image = image.resize(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
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
