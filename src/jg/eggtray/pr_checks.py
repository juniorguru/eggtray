import logging
from pathlib import PurePosixPath

from githubkit import BaseAuthStrategy, GitHub
from githubkit.versions.latest.models import DiffEntry
from jg.hen.core import check_profile_url
from jg.hen.models import Summary

from jg.eggtray.checks import is_allowed, profile_exists, render_table
from jg.eggtray.issues import (
    close_pull_request,
    fetch_pull_request,
    fetch_pull_request_files,
    find_comment,
    post_comment,
    update_comment,
)
from jg.eggtray.models import is_ready


logger = logging.getLogger(__name__)


PROFILES_DIR = PurePosixPath("profiles")

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
        touched_usernames = get_touched_usernames(files)
        logger.info(f"Touched profiles: {', '.join(touched_usernames) or 'none'}")
        if not touched_usernames:
            return

        if foreign_usernames := [
            username
            for username in touched_usernames
            if not is_allowed(author, username)
        ]:
            logger.error(
                f"@{author} isn't allowed to touch profiles: {', '.join(foreign_usernames)}"
            )
            await post_comment(
                github,
                owner,
                repo,
                pr_number,
                get_not_allowed_comment_text(
                    author, foreign_usernames, run_url=run_url
                ),
            )
            await close_pull_request(github, owner, repo, pr_number)
            return

        usernames = get_checked_usernames(files)
        logger.info(f"Profiles to check: {', '.join(usernames) or 'none'}")
        if not usernames:
            return

        wait_text = get_wait_comment_text(usernames, run_url=run_url)
        if comment_id := await find_comment(
            github, owner, repo, pr_number, COMMENT_MARKER
        ):
            logger.info(f"Reusing comment {comment_id}")
            await update_comment(github, owner, repo, comment_id, wait_text)
        else:
            comment_id = await post_comment(github, owner, repo, pr_number, wait_text)

        sections = []
        for username in usernames:
            profile_url = f"https://github.com/{username}"
            if await profile_exists(github, username):
                logger.info(f"Checking profile {profile_url}")
                summary: Summary = await check_profile_url(profile_url, github=github)
                logger.debug("Summary:\n%s", summary.model_dump_json(indent=2))
                sections.append(format_summary_section(summary))
            else:
                logger.error(f"Profile {profile_url} doesn't exist")
                sections.append(format_missing_profile_section(username))

        logger.info("Posting summary")
        await update_comment(
            github,
            owner,
            repo,
            comment_id,
            format_summary_body(sections, run_url=run_url),
        )


def get_touched_usernames(files: list[DiffEntry]) -> list[str]:
    paths = [file.filename for file in files] + [
        file.previous_filename for file in files if file.previous_filename
    ]
    return unique(username for path in paths if (username := get_username(path)))


def get_checked_usernames(files: list[DiffEntry]) -> list[str]:
    return unique(
        username
        for file in files
        if file.status != "removed" and (username := get_username(file.filename))
    )


def get_username(path: str) -> str | None:
    path = PurePosixPath(path)
    if path.parent == PROFILES_DIR:
        return path.stem
    return None


def unique(usernames) -> list[str]:
    return list(dict.fromkeys(usernames))


def format_profile_links(usernames: list[str]) -> str:
    return ", ".join(
        f"[github.com/{username}](https://github.com/{username})"
        for username in usernames
    )


def get_not_allowed_comment_text(
    author: str | None, usernames: list[str], run_url: str | None = None
) -> str:
    text = (
        "Ahoj! "
        f"Tenhle PR mění cizí profil ({format_profile_links(usernames)}), "
        "ale každý může přidat, upravit nebo odebrat jen ten svůj 🙅 "
    )
    if author:
        text += (
            "Soubor se musí jmenovat podle tvého uživatelského jména na GitHubu, "
            f"tedy `profiles/{author}.yml`. "
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
                "Po začlenění tohoto PR se profil do 24 hodin objeví na "
                "[junior.guru/candidates](https://junior.guru/candidates/).\n\n"
            )
        else:
            text += (
                "Vidím zásadní nedostatky 🔴 "
                "Po začlenění tohoto PR se profil objeví na "
                "[junior.guru/candidates](https://junior.guru/candidates/), "
                "ale dokud nebudou 🔴 červené věci opravené, bude upozaděný 💔 "
                "Opravit je můžeš ještě před začleněním, nebo kdykoliv potom. "
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


def format_missing_profile_section(username: str) -> str:
    return (
        f"### @{username}\n\n"
        f"Profil [github.com/{username}](https://github.com/{username}) "
        "podle všeho neexistuje 🤷 "
        "Soubor se musí jmenovat přesně podle tvého uživatelského jména na GitHubu."
    )
