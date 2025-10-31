from enum import StrEnum, auto

import pycountry


class Experience(StrEnum):
    volunteer = auto()
    intern = auto()
    trainee = auto()
    employee = auto()


class School(StrEnum):
    it = auto()
    math = auto()
    non_it = auto()


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


Language = StrEnum(
    "Language",
    [
        (code, code)
        for code in filter(
            None, [getattr(lang, "alpha_2", None) for lang in pycountry.languages]
        )
    ],
)
