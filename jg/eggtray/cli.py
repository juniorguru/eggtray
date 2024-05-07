from pathlib import Path

import click

from jg.eggtray.profile import parse


@click.command()
@click.argument("profiles_dir", type=Path)
def main(profiles_dir: Path):
    profiles_paths = profiles_dir.glob("*.yml")
    if not profiles_paths:
        click.echo("No profiles found in the directory")
        raise click.Abort()
    for profile_path in profiles_paths:
        click.echo(parse(profile_path.read_text()))
