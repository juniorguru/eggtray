from functools import wraps
from typing import Callable

import click
from githubkit import AppInstallationAuthStrategy


def multiline_str(string: str) -> str:
    return string.replace("\\n", "\n")


client_id_option = click.option(
    "--github-client-id",
    envvar="GITHUB_CLIENT_ID",
    help="GitHub app's client ID.",
    required=True,
)


installation_id_option = click.option(
    "--github-installation-id",
    envvar="GITHUB_INSTALLATION_ID",
    help="GitHub app's installation ID.",
    type=int,
    required=True,
)


private_key_option = click.option(
    "--github-private-key",
    envvar="GITHUB_PRIVATE_KEY",
    help="GitHub app's private key.",
    type=multiline_str,
    required=True,
)


def github_auth(command: Callable) -> Callable:
    command = client_id_option(command)
    command = installation_id_option(command)
    command = private_key_option(command)

    @wraps(command)
    def wrapper(*args, **kwargs):
        return command(
            *args,
            github_auth=AppInstallationAuthStrategy(
                kwargs.pop("github_client_id"),
                kwargs.pop("github_private_key"),
                kwargs.pop("github_installation_id"),
            ),
            **kwargs,
        )

    return wrapper
