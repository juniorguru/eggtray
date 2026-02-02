# Eggtray 🥚
Entry level candidates API

## Add yourself

If you're looking for an entry level software engineering job, send a Pull Request adding a new YAML file (RealPython has a [good intro to YAML](https://realpython.com/python-yaml/)) to the [./profiles](./profiles) directory. Each YAML file in that directory represents a profile of a single person:

- Name of the file must be your GitHub username
- The file must have the `.yml` extension
- See the YAML existing files, `models.py`, and `enums.py` to learn about the format of the YAML document
- If your skills are missing in the `Skill` enum, feel free to add them
- Members of the [junior.guru club](https://junior.guru/club/) can use `/discord_id` on Discord to learn what's their Discord ID

Once the PR gets accepted, Eggtray uses [Hen](https://github.com/juniorguru/hen) to inspect your GitHub profile. It merges the findings with data from the YAML file and creates a single data structure, which is then available in the API as your profile information.

If you want to change something in the YAML, send another PR. If you found a job (congratulations!) and now want to remove yourself from the API, send a PR removing your YAML file.

> [!NOTE]
> The API updates only once a day. If you change someting on your GitHub profile or in your YAML file, it can take up to 24 hours to take effect in the API.

## API usage

Open [juniorguru.github.io/eggtray/profiles.json](https://juniorguru.github.io/eggtray/profiles.json). That's it! As of now, there are no limitations on what you can do with the API. You can use the data for any purpose, even commercial, and there is no rate limiting.

The API has been created for the purpose of listing entry level candidates on [junior.guru/candidates](https://junior.guru/candidates/), but is open to anyone. If you use the API, [file an issue](https://github.com/juniorguru/eggtray/issues) and let's link your project from this document.

> [!CAUTION]
> As of now, the API is extremely **UNSTABLE**. There are no guarantees on schema of the response. Anything can and **will** change over night.

## Regular profile checks

Every night, each profile is reviewed. If the review uncovers any serious shortcomings, a GitHub issue labeled [profile not ready](https://github.com/juniorguru/eggtray/issues?q=is%3Aissue%20label%3A%22profile%20not%20ready%22) is created, listing the identified issues and notifying the profile owner. The profile is then demoted in the [junior.guru/candidates](https://junior.guru/candidates/) listing.

Once the shortcomings are resolved, a subsequent nightly check automatically closes the issue, and after the junior.guru website updates, the profile is promoted in the juniors listing again.

## One-off profile checks

This repository also provides one-off GitHub profile checks as a service. File a [new issue with the check template](https://github.com/juniorguru/eggtray/issues/new?template=check.md), and a bot will review your profile. You'll see the results in the comments under the issue. Once the check is done, the bot closes the issue.

## Contributing to the software behind all this

Use [uv](https://docs.astral.sh/uv/) to develop the API:

1. `git clone` this repository.
2. Run `uv run eggtray --help` to learn about what this tool can do. The `eggtray build` command does the main job of putting all the information together and creating the `profiles.json` file to the `output` directory.
3. If you want the `eggtray build` command to take screenshots, run `uv run playwright install chromium`.
4. Run `uv run pytest` to run tests or `uv run ruff` to check and format the code.

## License
[AGPL-3.0-only](LICENSE), copyright (c) 2025 Jan Javorek, and contributors.
