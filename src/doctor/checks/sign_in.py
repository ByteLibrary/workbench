"""The developer's sign-in: gh and git use the ByteLibrary Developer Access App, from the workspace only."""

from collections.abc import Iterator

from doctor.commands import gh, run
from doctor.results import Result
from doctor.settings import (
    GIT_CREDENTIALS_FILE,
    NON_INTERACTIVE,
    ORGANIZATION,
    REPOSITORY,
    WORKSPACE_GITCONFIG,
)


def check() -> Iterator[Result]:
    section = "GitHub access"
    if NON_INTERACTIVE:
        yield Result(section, "skipped without questions: the checks of a person's sign-in", None)
    else:
        yield Result(
            section,
            "gh is logged in, in its ByteLibrary-only configuration",
            gh("auth", "status", "--hostname", "github.com").returncode == 0,
            "Run mise run sign-in.",
        )
        token = gh("auth", "token").stdout.strip()
        yield Result(
            section,
            "signed in through the ByteLibrary Developer Access App",
            token.startswith("ghu_"),
            "Run mise run sign-in.",
        )
        outside = gh(
            "api",
            "--paginate",
            "/user/repos",
            "--jq",
            f'.[] | select(.private and .owner.login != "{ORGANIZATION}") | .full_name',
        ).stdout.split()
        yield Result(
            section,
            f"the sign-in reaches no private repositories outside {ORGANIZATION}",
            not outside,
            "Sign in through the App (mise run sign-in), not with a personal token.",
            details=outside,
        )
    helper = run(
        ["git", "-C", str(REPOSITORY), "config", "--get-all", "credential.https://github.com.helper"]
    ).stdout
    private = (
        GIT_CREDENTIALS_FILE.exists()
        and GIT_CREDENTIALS_FILE.stat().st_size > 0
        and (GIT_CREDENTIALS_FILE.stat().st_mode & 0o777 == 0o600)
    )
    yield Result(
        section,
        "workspace repositories authenticate with the sign-in, from a private file",
        private and f"store --file={GIT_CREDENTIALS_FILE}" in helper.splitlines(),
        "Run mise run sign-in.",
    )
    origin = run(["git", "-C", str(REPOSITORY), "config", "--show-origin", "user.email"]).stdout
    yield Result(
        section, "workspace commit identity is set", str(WORKSPACE_GITCONFIG) in origin, "Run setup.sh again."
    )
