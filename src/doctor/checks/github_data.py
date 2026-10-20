"""Repository settings, and the handbook's data, against GitHub."""

from collections.abc import Iterator

from pydantic import AliasPath, Field, TypeAdapter

from doctor.commands import gh_json
from doctor.handbook import Code, HandbookRepository, rows
from doctor.outside import Outside
from doctor.results import Result
from doctor.settings import HANDBOOK_DATA, ORGANIZATION, PROJECT_NUMBER


class GitHubRepository(Outside):
    """A repository, as GitHub's API lists it."""

    name: str
    archived: bool
    visibility: str
    description: str | None = None
    topics: list[str] = []


class MergeSettings(Outside):
    """A repository's merge settings; GitHub leaves them out without administration access."""

    allow_squash_merge: bool | None = None
    allow_merge_commit: bool = False
    allow_rebase_merge: bool = False
    squash_merge_commit_title: str | None = None
    squash_merge_commit_message: str | None = None
    delete_branch_on_merge: bool = False


class Option(Outside):
    name: str


class ContextOptions(Outside):
    """The project's Context field's options, from the GraphQL query in check()."""

    options: list[Option] = Field(
        validation_alias=AliasPath("data", "organization", "projectV2", "field", "options")
    )


REPOSITORIES = TypeAdapter(list[GitHubRepository])


def organization_repositories() -> list[GitHubRepository]:
    return REPOSITORIES.validate_python(
        gh_json("api", "--paginate", f"orgs/{ORGANIZATION}/repos?per_page=100") or []
    )


def convention_repositories() -> list[GitHubRepository]:
    kinds = {kind.code for kind in rows("repository-kinds", Code)}
    return [r for r in organization_repositories() if not r.archived and kinds & set(r.topics)]


def merge_settings(settings: MergeSettings) -> str:
    if settings.allow_squash_merge is None:
        return "unreadable"
    expected = (
        settings.allow_squash_merge
        and not settings.allow_merge_commit
        and not settings.allow_rebase_merge
        and settings.squash_merge_commit_title == "PR_TITLE"
        and settings.squash_merge_commit_message == "PR_BODY"
        and settings.delete_branch_on_merge
    )
    return "ok" if expected else "drift"


def repository_differences(
    documented: list[HandbookRepository], on_github: list[GitHubRepository], kinds: set[str]
) -> list[str]:
    """Differences between the handbook's repositories and GitHub's, in both directions."""
    github = {repository.name: repository for repository in on_github if not repository.archived}
    problems: list[str] = []
    for entry in documented:
        name = entry.name
        if entry.status == "planned":
            if name in github:
                problems.append(f"{name} exists on GitHub but is planned in the handbook")
            continue
        if name not in github:
            problems.append(f"{name} is active in the handbook but does not exist on GitHub")
            continue
        repository = github[name]
        # Topics are the kind and the context; GitHub detects the language (40-conventions/repositories.md).
        expected_topics = sorted([entry.kind] + ([f"context-{entry.context}"] if entry.context else []))
        differences: list[str] = []
        if repository.visibility != entry.visibility:
            differences.append(f"visibility is {repository.visibility}, the handbook says {entry.visibility}")
        if (repository.description or "") != entry.description:
            differences.append("description differs from the handbook")
        if sorted(repository.topics) != expected_topics:
            differences.append(
                f"topics are {sorted(repository.topics)}, the handbook implies {expected_topics}"
            )
        if differences:
            problems.append(f"{name}: {'; '.join(differences)}")
    named = {entry.name for entry in documented}
    for name, repository in github.items():
        if name not in named and kinds & set(repository.topics):
            problems.append(f"{name} follows the conventions on GitHub but is missing from the handbook")
    return problems


def check() -> Iterator[Result]:
    if not HANDBOOK_DATA.is_dir():
        yield Result(
            "Handbook data matches GitHub",
            "the handbook is not cloned, so its data cannot be compared with GitHub",
            False,
            "Run mise run doctor -- --fix.",
            "clone",
        )
        return
    try:
        repositories = organization_repositories()
        kinds = {kind.code for kind in rows("repository-kinds", Code)}
        convention = [r for r in repositories if not r.archived and kinds & set(r.topics)]
    except RuntimeError as error:
        yield Result(
            "Handbook data matches GitHub",
            f"GitHub could not be read: {error}",
            False,
            "Run mise run sign-in.",
        )
        return

    section = "Repository settings"
    for repository in convention:
        settings = MergeSettings.model_validate(
            gh_json("api", f"repos/{ORGANIZATION}/{repository.name}") or {}
        )
        state = merge_settings(settings)
        if state == "unreadable":
            yield Result(
                section, f"{repository.name}: settings not visible without administration access", None
            )
        else:
            yield Result(
                section,
                f"{repository.name}: repository settings",
                state == "ok",
                "Set squash merges only, with the pull request's title and description, "
                "and delete merged branches.",
            )

    section = "Handbook data matches GitHub"
    problems = repository_differences(rows("repositories", HandbookRepository), repositories, kinds)
    yield Result(
        section,
        "the handbook's repositories match GitHub",
        not problems,
        "Correct GitHub or data/repositories.yaml in the handbook.",
        details=problems,
    )
    expected = {context.code for context in rows("contexts", Code)} | {"organization"}
    query = """query($organization: String!, $number: Int!) {
      organization(login: $organization) { projectV2(number: $number) { field(name: "Context") {
        ... on ProjectV2SingleSelectField { options { name } } } } } }"""
    data = ContextOptions.model_validate(
        gh_json(
            "api",
            "graphql",
            "-F",
            f"number={PROJECT_NUMBER}",
            "-f",
            f"organization={ORGANIZATION}",
            "-f",
            f"query={query}",
        )
    )
    actual = {option.name for option in data.options}
    yield Result(
        section,
        "the project's Context options match the handbook's contexts",
        expected == actual,
        "Correct the project's Context field or data/contexts.yaml in the handbook.",
        details=[f"missing: {', '.join(sorted(expected - actual))}"] * bool(expected - actual)
        + [f"not in the handbook: {', '.join(sorted(actual - expected))}"] * bool(actual - expected),
    )
