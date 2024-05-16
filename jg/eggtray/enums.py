from enum import StrEnum, auto

import pycountry


Language = StrEnum(
    "Language",
    [
        (code, code)
        for code in filter(
            None, [getattr(lang, "alpha_2", None) for lang in pycountry.languages]
        )
    ],
)


class School(StrEnum):
    secondary_unfinished = auto()
    secondary = auto()

    university_unfinished = auto()
    university = auto()

    it_secondary_unfinished = auto()
    it_secondary = auto()

    it_university_unfinished = auto()
    it_university = auto()


class Topic(StrEnum):
    # General areas
    frontend = auto()
    backend = auto()
    fullstack = auto()
    mobile = auto()

    # Mobile technologies
    swift = auto()
    kotlin = auto()
    flutter = auto()
    android = auto()

    # Backend technologies
    python = auto()
    java = auto()
    csharp = auto()

    # Frontend technologies
    typescript = auto()
    react = auto()
    vue = auto()
    angular = auto()


class CourseProvider(StrEnum):
    fourtytwoprague = "42prague"
    ajtyvit = auto()
    beeit = auto()
    coderslab = auto()
    codingbootcamppraha = auto()
    coreskill = auto()
    czechitas = auto()
    datacamp = auto()
    djangogirls = auto()
    engeto = auto()
    greenfox = auto()
    itnetwork = auto()
    kurzyvsb = auto()
    lucietvrdikova = auto()
    naucmeit = auto()
    prahacodingschool = auto()
    primakurzy = auto()
    pyladies = auto()
    radekkitner = auto()
    reactgirls = auto()
    robotdreams = auto()
    schoolofcode = auto()
    scrimba = auto()
    sdacademy = auto()
    skillmea = auto()
    step = auto()
    streetofcode = auto()
    udemy = auto()
    unicornhatchery = auto()
    webrebel = auto()
