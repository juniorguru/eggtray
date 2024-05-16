from enum import StrEnum, auto


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
