import logging
import re
from typing import cast

from githubkit import BaseAuthStrategy, GitHub
from githubkit.versions.latest.models import (
    Issue,
    IssuePropLabelsItemsOneof1 as IssueLabel,
)
from jg.hen.core import check_profile_url
from jg.hen.models import Status, Summary


logger = logging.getLogger(__name__)


USERNAME_RE = re.compile(r"@(\w+)")

COLORS = {
    Status.ERROR: "🔴",
    Status.WARNING: "🟠",
    Status.INFO: "🔵",
    Status.DONE: "🟢",
}


async def process_issue(
    auth: BaseAuthStrategy, owner: str, repo: str, issue_number: int, run_id: int | None = None
) -> None:
    if run_id:
        run_url = f"https://github.com/{owner}/{repo}/actions/runs/{run_id}"
        logger.info(f"Working inside {run_url}")
    else:
        run_url = None
    async with GitHub(auth=auth) as github:
        logger.info(f"Fetching https://github.com/{owner}/{repo}/issues/{issue_number}")
        username = await fetch_username_from_issue(github, owner, repo, issue_number)
        if username:
            title = f"Zpětná vazba na profil {username}"
            await update_title(github, owner, repo, issue_number, title)
            comment_id = await post_comment(github, owner, repo, issue_number, run_url=run_url)
            profile_url = f"https://github.com/{username}"
            logger.info(f"Checking profile: {profile_url}")
            summary: Summary = await check_profile_url(profile_url, github=github)
            logger.info("Posting summary")
            await post_summary(github, owner, repo, comment_id, summary)
            await close_issue(github, owner, repo, issue_number)
        else:
            logger.info("Skipping issue as not relevant")


async def fetch_username_from_issue(
    github: GitHub, owner: str, repo: str, issue_number: int
) -> str | None:
    logger.debug(f"Fetching username from issue #{issue_number}")
    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    issue: Issue = response.parsed_data
    label_names = {label.name for label in cast(list[IssueLabel], issue.labels)}

    # if issue.state == "closed":
    #     logger.warning(f"Issue #{issue_number} is closed")
    #     return
    if "check" not in label_names:
        logger.warning(f"Issue #{issue_number} is missing the 'check' label")
        return
    if not issue.body or not issue.body.strip():
        logger.warning(f"Issue #{issue_number} is missing a body")
        return

    logger.debug(f"Getting username from issue #{issue_number}: {issue.body!r}")
    if match := USERNAME_RE.search(issue.body, re.I):
        return match.group(1)
    else:
        logger.warning(f"Issue #{issue_number} doesn't mention a username")
        return


async def update_title(github: GitHub, owner: str, repo: str, issue_number: int, title: str):
    logger.debug(f"Checking title of issue #{issue_number}")
    response = await github.rest.issues.async_get(
        owner=owner, repo=repo, issue_number=issue_number
    )
    issue: Issue = response.parsed_data
    if issue.title != title:
        logger.debug(
            f"Updating title of issue #{issue_number} from {issue.title!r} to {title!r}"
        )
        await github.rest.issues.async_update(
            owner=owner, repo=repo, issue_number=issue_number, title=title
        )


async def post_comment(github: GitHub, owner: str, repo: str, issue_number: int, run_url: str | None = None) -> int:
    logger.debug(f"Posting comment to issue #{issue_number}")
    response = await github.rest.issues.async_create_comment(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        body=format_comment_body(run_url=run_url),
    )
    return response.parsed_data.id


def format_comment_body(run_url: str | None = None) -> str:
    text = (
        "Ahoj!"
        "\n\n"
        "🔬 Koukám, že chceš, abych ti dalo zpětnou vazbu na GitHub profil. "
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


async def post_summary(
    github: GitHub,
    owner: str,
    repo: str,
    comment_id: int,
    summary: Summary,
    run_url: str | None = None,
) -> None:
    logger.debug(
        f"Updating comment #{comment_id} with summary:\n{summary.model_dump_json(indent=2)}"
    )
    await github.rest.issues.async_update_comment(
        owner=owner,
        repo=repo,
        comment_id=comment_id,
        body=format_summary_body(summary, run_url=run_url),
    )


def format_summary_body(summary: Summary, run_url: str | None = None) -> str:
    if summary.error:
        text = (
            f"Kouklo jsem na to, ale bohužel to skončilo chybou 🤕\n"
            f"```\n{summary.error}\n```\n"
            f"@honzajavorek, mrkni na to, prosím."
        )
    else:
        text = (
            "Tak jsem na to kouklo a tady je moje zpětná vazba 🔬 "
            "Pokud si opravíš chyby, stačí znovuotevřít tohle issue a já ti na to zase mrknu.\n\n"
            "| Verdikt | Popis | Vysvětlení |\n"
            "|---------|-------|------------|\n"
        )
        for outcome in summary.outcomes:
            text += (
                f"| {COLORS[outcome.status]} "
                f"| {outcome.message} "
                f"| [Proč?]({outcome.docs_url}) "
                " |\n"
            )
    text += (
        "\n\n<details>\n\n"
        "<summary>Výsledky jako JSON</summary>\n\n"
        f"```json\n{summary.model_dump_json(indent=2)}\n```\n\n"
        "</details>"
    )
    if run_url:
        text += f"\n\n---\n\n[Záznam mojí práce]({run_url}) 👀"
    return text


async def close_issue(github: GitHub, owner: str, repo: str, issue_number: int) -> None:
    logger.debug(f"Closing issue #{issue_number}")
    await github.rest.issues.async_update(
        owner=owner, repo=repo, issue_number=issue_number, state="closed"
    )
