import logging
import re
from pathlib import PurePosixPath

from githubkit import BaseAuthStrategy, GitHub
from githubkit.versions.latest.models import DiffEntry
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

from jg.eggtray.checks import (
    BOT_USERNAME,
    PRIVILEGED_USERNAMES,
    is_allowed,
    profile_exists,
    render_table,
)
from jg.eggtray.issues import (
    close_pull_request,
    fetch_event_actors,
    fetch_pull_request,
    fetch_pull_request_files,
    find_comment,
    post_comment,
    update_comment,
)
from jg.eggtray.models import is_ready


logger = logging.getLogger(__name__)


PROFILES_DIR = PurePosixPath("profiles")

PROFILE_SUFFIX = ".yml"

USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

COMMENT_MARKER = "<!-- eggtray:check-pr -->"


async def check_pull_request(
    auth: BaseAuthStrategy,
    owner: str,
    repo: str,
    pr_number: int,
    run_url: str | None = None,
) -> None:
    async with GitHub(auth=auth) as github:
        logger.info(f"Fetching https://github.com/{owner}/{repo}/pull/{pr_number}")
        pr = await fetch_pull_request(github, owner, repo, pr_number)
        if pr.state != "open":
            logger.warning(f"Pull request #{pr_number} is {pr.state}")
            return
        author = pr.user.login if pr.user else None
        logger.info(f"Pull request #{pr_number} is by @{author}")

        files = await fetch_pull_request_files(github, owner, repo, pr_number)
        touched_profiles = get_touched_profiles(files)
        logger.info(f"Touched profiles: {', '.join(touched_profiles) or 'none'}")
        present_profiles = get_checked_profiles(files)
        wrong_paths = get_wrong_paths(files)
        logger.info(f"Wrong paths: {', '.join(wrong_paths) or 'none'}")

        foreign_usernames = [
            username
            for username in touched_profiles
            if not is_allowed(author, username)
        ]
        if foreign_usernames and await is_accepted(github, owner, repo, pr_number):
            logger.warning(
                "Reopened by a privileged user, skipping the ownership check"
            )
        elif foreign_usernames:
            existing_usernames = [
                username
                for username in foreign_usernames
                if await profile_exists(github, username)
            ]
            if existing_usernames:
                logger.error(
                    f"@{author} isn't allowed to touch profiles: {', '.join(existing_usernames)}"
                )
                await post_comment(
                    github,
                    owner,
                    repo,
                    pr_number,
                    get_not_allowed_comment_text(
                        author, existing_usernames, run_url=run_url
                    ),
                )
                await close_pull_request(github, owner, repo, pr_number)
                return
            logger.warning(f"Accounts don't exist: {', '.join(foreign_usernames)}")
            if typo_paths := [
                path
                for username, path in present_profiles.items()
                if username in foreign_usernames
            ]:
                logger.warning(f"Probably typos: {', '.join(typo_paths)}")
                wrong_paths += typo_paths

        checked_profiles = {
            username: path
            for username, path in present_profiles.items()
            if author and username.lower() == author.lower()
        }
        logger.info(f"Profiles to check: {', '.join(checked_profiles) or 'none'}")

        comment_id = await find_comment(
            github, owner, repo, pr_number, BOT_USERNAME, COMMENT_MARKER
        )
        if not checked_profiles and not wrong_paths:
            if comment_id:
                logger.info(f"Nothing to check, updating comment {comment_id}")
                await update_comment(
                    github,
                    owner,
                    repo,
                    comment_id,
                    format_summary_body(
                        [get_nothing_to_check_section()], run_url=run_url
                    ),
                )
            return

        sections = []
        if wrong_paths:
            sections.append(format_wrong_paths_section(author, wrong_paths))
        if checked_profiles:
            wait_text = get_wait_comment_text(list(checked_profiles), run_url=run_url)
            if comment_id:
                logger.info(f"Reusing comment {comment_id}")
                await update_comment(github, owner, repo, comment_id, wait_text)
            else:
                comment_id = await post_comment(
                    github, owner, repo, pr_number, wait_text
                )
            for username in checked_profiles:
                profile_url = f"https://github.com/{username}"
                logger.info(f"Checking profile {profile_url}")
                summary: Summary = await check_profile_url(profile_url, github=github)
                logger.debug("Summary:\n%s", summary.model_dump_json(indent=2))
                sections.append(format_summary_section(summary))

        logger.info("Posting summary")
        body = format_summary_body(sections, run_url=run_url)
        if comment_id:
            await update_comment(github, owner, repo, comment_id, body)
        else:
            await post_comment(github, owner, repo, pr_number, body)


async def is_accepted(github: GitHub, owner: str, repo: str, pr_number: int) -> bool:
    # A privileged user reopening a PR closed by the bot means they want to accept it
    actors = await fetch_event_actors(github, owner, repo, pr_number, "reopened")
    return any(actor.lower() in PRIVILEGED_USERNAMES for actor in actors)


def get_touched_profiles(files: list[DiffEntry]) -> dict[str, str]:
    paths = [file.filename for file in files] + [
        file.previous_filename for file in files if file.previous_filename
    ]
    return {
        username: path for path in paths if (username := get_username_from_path(path))
    }


def get_checked_profiles(files: list[DiffEntry]) -> dict[str, str]:
    return {
        username: file.filename
        for file in files
        if file.status != "removed"
        and (username := get_username_from_path(file.filename))
    }


def get_wrong_paths(files: list[DiffEntry]) -> list[str]:
    return [
        file.filename
        for file in files
        if file.status != "removed"
        and is_in_profiles_dir(file.filename)
        and not get_username_from_path(file.filename)
    ]


def is_in_profiles_dir(path: str) -> bool:
    return PurePosixPath(path).parent == PROFILES_DIR


def get_username_from_path(path: str) -> str | None:
    path = PurePosixPath(path)
    if (
        path.parent == PROFILES_DIR
        and path.suffix == PROFILE_SUFFIX
        and USERNAME_RE.match(path.stem)
    ):
        return path.stem
    return None


def format_profile_links(usernames: list[str]) -> str:
    return ", ".join(
        f"[github.com/{username}](https://github.com/{username})"
        for username in usernames
    )


def format_paths(paths: list[str]) -> str:
    return ", ".join(f"`{path.replace('`', '')}`" for path in paths)


def format_profile_path(author: str | None) -> str:
    return f"`{PROFILES_DIR / (author or 'tvoje-uzivatelske-jmeno')}{PROFILE_SUFFIX}`"


def get_not_allowed_comment_text(
    author: str | None, usernames: list[str], run_url: str | None = None
) -> str:
    text = (
        "Ahoj! "
        f"Tenhle PR mění cizí profil ({format_profile_links(usernames)}), "
        "ale každý může přidat, upravit, nebo odebrat jen ten svůj 🙅 "
    )
    if author:
        text += (
            "Soubor se musí jmenovat podle tvého uživatelského jména na GitHubu, "
            f"tedy {format_profile_path(author)}. "
        )
    text += (
        "Proto PR zavírám. Pokud jde o omyl, pošli prosím nový PR se správným souborem."
    )
    if run_url:
        text += f"\n\n---\n\n[Záznam mojí práce]({run_url})"
    return text


def get_wait_comment_text(usernames: list[str], run_url: str | None = None) -> str:
    text = (
        f"{COMMENT_MARKER}\n"
        "Ahoj!"
        "\n\n"
        f"🔬 Mrknu na GitHub profil {format_profile_links(usernames)}, "
        "ať víš, jestli je připravený na hledání práce. "
        "Až budu mít hotovo, objeví se tady výsledky."
        "\n\n"
        "⏳ Projít velké profily mi trvá i několik minut"
    )
    if run_url:
        text += (
            ", tak pokud se dlouho nic neděje, "
            f"můžeš mi [koukat pod zobáček]({run_url})."
        )
    else:
        text += ", tak si zatím třeba protáhni záda."
    return text


def format_summary_body(sections: list[str], run_url: str | None = None) -> str:
    text = f"{COMMENT_MARKER}\n" + "\n\n".join(sections)
    if run_url:
        text += f"\n\n---\n\n[Záznam mojí práce]({run_url})"
    return text


def format_summary_section(summary: Summary) -> str:
    text = f"### @{summary.username}\n\n"
    if summary.error:
        data = summary.model_dump(mode="json")
        text += (
            f"Na profil jsem kouklo, ale bohužel to skončilo chybou 🤕\n"
            f"```\n{data['error']}\n```\n"
            f"@honzajavorek, mrkni na to, prosím."
        )
    else:
        text += (
            "Tak jsem si poctivě prošlo celý profil "
            f"[github.com/{summary.username}](https://github.com/{summary.username}) "
            "a tady je moje zpětná vazba 🔬\n\n"
        )
        if is_ready(summary.outcomes):
            text += (
                "Nevidím žádné zásadní nedostatky! 💪 "
                "Pokud projdou ostatní testy, po začlenění tohoto PR se profil "
                "do 24 hodin objeví na "
                "[junior.guru/candidates](https://junior.guru/candidates/).\n\n"
            )
        else:
            text += (
                "Vidím zásadní nedostatky 🔴 "
                "Dokud nebudou 🔴 červené věci opravené, bude profil na "
                "[junior.guru/candidates](https://junior.guru/candidates/) "
                "upozaděný 💔 "
                "Každý den to znova zkontroluju.\n\n"
            )
        text += render_table(summary.outcomes)
    text += (
        "\n\n<details>\n\n"
        "<summary>Výsledky jako JSON</summary>\n\n"
        f"```json\n{summary.model_dump_json(indent=2)}\n```\n\n"
        "</details>"
    )
    return text


def format_wrong_paths_section(author: str | None, paths: list[str]) -> str:
    return (
        "### Špatný název souboru\n\n"
        f"Tyhle soubory mají špatný název: {format_paths(paths)} 🤷 "
        "Profil musí být v souboru pojmenovaném přesně podle tvého "
        f"uživatelského jména na GitHubu a s příponou `{PROFILE_SUFFIX}`, "
        f"tedy {format_profile_path(author)}. "
        "Přejmenuj ho prosím, jinak se profil nezobrazí."
    )


def get_nothing_to_check_section() -> str:
    return (
        "Tenhle PR už nepřidává ani nemění žádný profil, takže tu není co kontrolovat."
    )
