import logging

from githubkit import BaseAuthStrategy, GitHub
from githubkit.versions.latest.models import Issue

from jg.eggtray.checks import render_table
from jg.eggtray.issues import (
    create_issue,
    fetch_report_issues,
    get_username,
    update_issue,
)
from jg.eggtray.models import Profile


logger = logging.getLogger(__name__)


async def report_profiles(
    auth: BaseAuthStrategy,
    owner: str,
    repo: str,
    profiles: list[Profile],
    label: str,
    run_url: str | None = None,
) -> list[Issue]:
    issues = []
    async with GitHub(auth) as github:
        logger.info("Fetching existing report issues")
        issues = await fetch_report_issues(github, owner, repo, label=label)
        logger.info(f"Found {len(issues)} reports")
        issues_mapping = {get_username(issue.title): issue for issue in issues}
        logger.debug(f"Reports: {list(issues_mapping.keys())}")
        for profile in profiles:
            logger.info(f"Processing {profile.github_url}")
            title = f"Profil @{profile.github_username} má nedostatky"
            body = format_body(profile, run_url=run_url)
            if issue := issues_mapping.get(profile.github_username):
                logger.info(f"Updating issue {issue.html_url}")
                await update_issue(
                    github, owner, repo, issue.number, title=title, body=body
                )
            else:
                logger.info(f"Creating issue for {profile.github_url}")
                issue = await create_issue(
                    github,
                    owner,
                    repo,
                    title=title,
                    body=body,
                    labels=[label] if label else None,
                )
                logger.info(f"Issue: {issue.html_url}")
            issues.append(issue)
    return issues


def format_body(profile: Profile, run_url: str | None = None) -> str:
    text = (
        f"Při namátkové kontrole profilu od @{profile.github_username} "
        "jsem našlo následující nedostatky 🚨 "
        "Dokud nebude všechno OK, tak **profil není připravený "
        "na hledání práce** a na "
        "[junior.guru/candidates](https://junior.guru/candidates/) "
        "bude upozaděn 💔"
        "\n\n"
    )
    text += render_table(profile.issues)
    if run_url:
        text += f"\n\n---\n\n[Záznam mojí práce]({run_url})"
    return text
