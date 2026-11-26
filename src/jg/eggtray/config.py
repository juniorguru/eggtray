from enum import StrEnum, auto


class Placement(StrEnum):
    """Where on junior.guru the check form was"""

    homepage = auto()
    jobs = auto()
    handbook = auto()


CLUB_URL_TEMPLATE = "https://junior.guru/club/?utm_source={utm_source}&utm_medium=github&utm_campaign=jaro"

UTM_SOURCES = {
    Placement.homepage: "gh-check",
    Placement.jobs: "gh-check-jobs",
    Placement.handbook: "gh-check-handbook",
}

UNKNOWN_UTM_SOURCE = "gh-check-unknown"
