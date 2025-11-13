import logging

from githubkit import BaseAuthStrategy, GitHub
from githubkit.exception import RequestFailed
from jg.hen.core import check_profile_url
from jg.hen.models import Outcome, Status, Summary

from jg.eggtray.issues import (
    close_issue,
    fetch_issue,
    get_username,
    has_label,
    post_comment,
    update_issue,
)
from jg.eggtray.models import is_ready


logger = logging.getLogger(__name__)


COLORS = {
    Status.ERROR: "🔴",
    Status.WARNING: "🟠",
    Status.INFO: "🔵",
    Status.DONE: "🟢",
}


async def check_profile(
    auth: BaseAuthStrategy,
    owner: str,
    repo: str,
    issue_number: int,
    states: list[str] | None = None,
    run_url: str | None = None,
) -> None:
    if not states:
        states = ["open"]
    async with GitHub(auth=auth) as github:
        logger.info(f"Fetching https://github.com/{owner}/{repo}/issues/{issue_number}")
        issue = await fetch_issue(github, owner, repo, issue_number)
        if issue.state not in states:
            logger.warning(
                f"Issue #{issue_number} is {issue.state}, allowed states: {','.join(states)}"
            )
            return
        if not has_label(issue, "check"):
            logger.warning(f"Issue #{issue_number} is missing the 'check' label")
            return

        logger.info(f"Figuring out GitHub username from issue #{issue_number}")
        if username := get_username(issue.body or ""):
            logger.info(f"Issue #{issue_number} mentions @{username}")
        elif issue.user:
            logger.info(
                f"Issue #{issue_number} doesn't mention a username, assuming author"
            )
            username = issue.user.login
        else:
            logger.warning(
                f"Issue #{issue_number} doesn't mention a username and has no author"
            )
            return

        profile_url = f"https://github.com/{username}"
        if await profile_exists(github, username):
            logger.info(f"Checking profile {profile_url}")
            title = f"Zpětná vazba na profil @{username}"
            await update_issue(github, owner, repo, issue_number, title=title)
            await post_comment(
                github,
                owner,
                repo,
                issue_number,
                get_wait_comment_text(username, run_url=run_url),
            )
            summary: Summary = await check_profile_url(profile_url, github=github)
            logger.info("Posting summary")
            logger.debug("Summary:\n%s", summary.model_dump_json(indent=2))
            await post_comment(
                github,
                owner,
                repo,
                issue_number,
                format_summary_body(summary, run_url=run_url),
            )
        else:
            logger.error(f"Profile {profile_url} doesn't exist")
            await post_comment(
                github,
                owner,
                repo,
                issue_number,
                get_missing_profile_comment_text(username, run_url=run_url),
            )
        await close_issue(github, owner, repo, issue_number)


async def profile_exists(github: GitHub, username: str) -> bool:
    logger.debug(f"Checking if profile {username} exists")
    try:
        await github.rest.users.async_get_by_username(username)
        return True
    except RequestFailed as e:
        if e.response.status_code == 404:
            return False
        raise


def get_wait_comment_text(username: str, run_url: str | None = None) -> str:
    text = (
        "Ahoj!"
        "\n\n"
        "🔬 Koukám, že chceš, abych ti dalo zpětnou vazbu na GitHub profil "
        f"[github.com/{username}](https://github.com/{username}). "
        "Tak jo, letím na to! "
        "Až budu mít hotovo, objeví se tady výsledky a zavřu tohle issue. "
        "\n\n"
        "⏳ Projít velké profily mi trvá i několik minut"
    )
    if run_url:
        text += (
            ", tak pokud se dlouho nic neděje, "
            f"můžeš mi [koukat pod zobáček]({run_url}). "
            "Ale možná se spíš koukni z okna a protáhni si záda."
        )
    else:
        text += ", tak si zatím třeba protáhni záda."
    return text


def get_missing_profile_comment_text(username: str, run_url: str | None = None) -> str:
    text = (
        "Ahoj! "
        f"Vypadá to, že chceš, ať se podívám na profil [github.com/{username}](https://github.com/{username}), "
        "jenže ten podle všeho neexistuje 🤷"
    )
    if run_url:
        text += f"\n\n---\n\n[Záznam mojí práce]({run_url})"
    return text


def format_summary_body(summary: Summary, run_url: str | None = None) -> str:
    if summary.error:
        data = summary.model_dump(mode="json")
        text = (
            f"Na profil jsem kouklo, ale bohužel to skončilo chybou 🤕\n"
            f"```\n{data['error']}\n```\n"
            f"@honzajavorek, mrkni na to, prosím."
        )
    else:
        text = (
            "Tak jsem si poctivě prošlo celý profil "
            f"[github.com/{summary.username}](https://github.com/{summary.username}) "
            "a tady je moje zpětná vazba 🔬\n\n"
        )
        if is_ready(summary.outcomes):
            text += (
                "Nevidím žádné zásadní nedostatky, takže si klidně můžeš hledat práci v oboru! 💪"
                "Pokud to dokážeš, vytvoř si profil na [junior.guru/candidates](https://junior.guru/candidates/)!\n\n"
            )
        else:
            text += (
                "Vidím zásadní nedostatky 🔴 Oprav si to, než si začneš hledat práci. Klidně si to tady pak znovu nech zkontrolovat. "
                "Až to bude OK, nezapomeň si vytvořit profil na [junior.guru/candidates](https://junior.guru/candidates/)!\n\n"
            )
        text += render_table(summary.outcomes)
    text += (
        "\n\n<details>\n\n"
        "<summary>Výsledky jako JSON</summary>\n\n"
        f"```json\n{summary.model_dump_json(indent=2)}\n```\n\n"
        "</details>"
    )
    if run_url:
        text += f"\n\n---\n\n[Záznam mojí práce]({run_url})"
    return text


def render_table(outcomes: list[Outcome]) -> str:
    # The purpose of the comments below is just to prevent auto-formatting
    table = (
        "| Verdikt | Popis | Vysvětlení |\n"  # don't
        "|---------|-------|------------|\n"  # wrap
    )
    for outcome in outcomes:
        table += (
            f"| {COLORS[outcome.status]} "
            f"| {outcome.message} "
            f"| [Proč?]({outcome.docs_url}) "
            " |\n"
        )
    return table
