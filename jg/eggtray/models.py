from typing import Any, Self

from jg.hen.models import Outcome, Status, Summary
from pydantic import BaseModel

from jg.eggtray.enums import Experience, Language, School, Topic


class Document(BaseModel):
    username: str
    github_url: str
    discord_id: int | None = None
    name: str | None = None
    bio: str | None = None
    email: str | None = None
    location: str | None = None
    topics: set[Topic]
    domains: list[str] = []
    experience: set[Experience] = set()
    secondary_school: School | None
    university: School | None
    languages: list[Language]  # type: ignore

    @classmethod
    def create(cls, username: str, yaml_data: dict[str, Any]) -> Self:
        return cls(
            username=username,
            github_url=f"https://github.com/{username}",
            **yaml_data,
        )


class Profile(BaseModel):
    name: str | None
    bio: str | None
    email: str | None
    avatar_url: str
    location: str | None
    discord_id: int | None
    github_username: str
    github_url: str
    linkedin_url: str | None
    topics: set[Topic]
    domains: list[str]
    experience: set[Experience]
    secondary_school: School | None
    university: School | None
    languages: list[Language]  # type: ignore
    outcomes: list[Outcome]
    is_ready: bool

    @classmethod
    def create(cls, document: Document, summary: Summary) -> Self:
        usernames = [document.username, summary.username]
        if len(set(usernames)) != 1:
            raise ValueError(f"Usernames do not match: {usernames!r}")
        username = usernames[0]

        return cls(
            name=document.name or summary.info.name or username,
            bio=document.bio or summary.info.bio,
            email=document.email or summary.info.email,
            avatar_url=summary.info.avatar_url,
            location=document.location or summary.info.location,
            discord_id=document.discord_id,
            github_username=username,
            github_url=document.github_url,
            linkedin_url=summary.info.linkedin_url,
            topics=document.topics,
            domains=document.domains,
            experience=document.experience,
            secondary_school=document.secondary_school,
            university=document.university,
            languages=document.languages,
            outcomes=summary.outcomes,
            is_ready=all(
                outcome.status != Status.ERROR for outcome in summary.outcomes
            ),
        )


class Response(BaseModel):
    count: int
    items: list[Profile]
    item_schema: dict[str, Any]

    @classmethod
    def create(cls, profiles: list[Profile]) -> Self:
        return cls(
            count=len(profiles),
            items=profiles,
            item_schema=Profile.model_json_schema(),
        )
