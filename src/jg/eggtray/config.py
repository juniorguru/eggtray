from jg.eggtray.enums import Placement


CLUB_URL_TEMPLATE = "https://junior.guru/club/?utm_source={utm_source}&utm_medium=github&utm_campaign=jaro"

DEFAULT_UTM_SOURCE = "gh-check"

UTM_SOURCES = {
    Placement.homepage: DEFAULT_UTM_SOURCE,
    Placement.jobs: "gh-check-jobs",
    Placement.handbook: "gh-check-handbook",
}

CLUB_URL = CLUB_URL_TEMPLATE.format(utm_source=DEFAULT_UTM_SOURCE)
