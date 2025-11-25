from enum import StrEnum, auto, unique

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


@unique
class Skill(StrEnum):
    # General areas
    backend = auto()
    frontend = auto()
    fullstack = auto()
    mobile = auto()
    testing = auto()

    # Mobile technologies
    android = auto()
    flutter = auto()
    kotlin = auto()
    swift = auto()

    # Backend technologies
    apachespark = auto()
    csharp = auto()
    django = auto()
    fastapi = auto()
    java = auto()
    kafka = auto()
    kubernetes = auto()
    laravel = auto()
    php = auto()
    postgresql = auto()
    python = auto()
    rabbitmq = auto()
    redis = auto()
    springboot = auto()
    sql = auto()
    wpf = auto()

    # Low-level technologies
    arduino = auto()
    c = auto()
    cpp = auto()
    rust = auto()
    zig = auto()

    # GIS technologies
    postgis = auto()

    # Data-related technologies
    pandas = auto()
    matplotlib = auto()
    opencv = auto()
    tensorflow = auto()

    # Frontend technologies
    angular = auto()
    css = auto()
    html = auto()
    javascript = auto()
    jquery = auto()
    react = auto()
    scss = auto()
    typescript = auto()
    vue = auto()

    # Tools
    docker = auto()
    git = auto()


Language = StrEnum(
    "Language",
    [
        (code, code)
        for code in filter(
            None, [getattr(lang, "alpha_2", None) for lang in pycountry.languages]
        )
    ],
)
