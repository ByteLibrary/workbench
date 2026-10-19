"""Repository settings, and the handbook's data, against GitHub."""

from collections.abc import Iterator

from doctor.commands import gh_json
from doctor.handbook import rows
from doctor.results import Result
from doctor.settings import HANDBOOK_DATA, ORGANIZATION, PROJECT_NUMBER


def convention_repositories() -> list[dict]:
    kinds = {kind["code"] for kind in rows("repository-kinds")}
    repositories = gh_json("api", "--paginate", f"orgs/{ORGANIZATION}/repos?per_page=100") or []
    return [r for r in repositories if not r["archived"] and kinds & set(r.get("topics") or [])]


def merge_settings(repository: dict) -> str:
    if repository.get("allow_squash_merge") is None:
        return "unreadable"
    expected = (
        repository["allow_squash_merge"]
        and not repository["allow_merge_commit"]
        and not repository["allow_rebase_merge"]
        and repository.get("squash_merge_commit_title") == "PR_TITLE"
        and repository.get("squash_merge_commit_message") == "PR_BODY"
        and repository.get("delete_branch_on_merge")
    )
    return "ok" if expected else "drift"


def repository_differences(documented: list[dict], on_github: list[dict], kinds: set[str]) -> list[str]:
    """Differences between the handbook's repositories and GitHub's, in both directions."""
    github = {repository["name"]: repository for repository in on_github if not repository["archived"]}
    problems = []
    for entry in documented:
        name = entry["name"]
        if entry["status"] == "planned":
            if name in github:
                problems.append(f"{name} exists on GitHub but is planned in the handbook")
            continue
        if name not in github:
            problems.append(f"{name} is active in the handbook but does not exist on GitHub")
            continue
        repository = github[name]
        expected_topics = sorted(
            [entry["kind"]]
            + ([f"context-{entry['context']}"] if entry.get("context") else [])
            + ([f"language-{entry['language']}"] if entry.get("language") else [])
        )
        differences = []
        if repository["visibility"] != entry["visibility"]:
            differences.append(
                f"visibility is {repository['visibility']}, the handbook says {entry['visibility']}"
            )
        if (repository.get("description") or "") != entry["description"]:
            differences.append("description differs from the handbook")
        if sorted(repository.get("topics") or []) != expected_topics:
            differences.append(
                f"topics are {sorted(repository.get('topics') or [])}, the handbook implies {expected_topics}"
            )
        if differences:
            problems.append(f"{name}: {'; '.join(differences)}")
    named = {entry["name"] for entry in documented}
    for name, repository in github.items():
        if name not in named and kinds & set(repository.get("topics") or []):
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
        repositories = gh_json("api", "--paginate", f"orgs/{ORGANIZATION}/repos?per_page=100") or []
        kinds = {kind["code"] for kind in rows("repository-kinds")}
        convention = [r for r in repositories if not r["archived"] and kinds & set(r.get("topics") or [])]
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
        state = merge_settings(gh_json("api", f"repos/{ORGANIZATION}/{repository['name']}") or {})
        if state == "unreadable":
            yield Result(
                section, f"{repository['name']}: settings not visible without administration access", None
            )
        else:
            yield Result(
                section,
                f"{repository['name']}: repository settings",
                state == "ok",
                "Set squash merges only, with the pull request's title and description, "
                "and delete merged branches.",
            )

    section = "Handbook data matches GitHub"
    problems = repository_differences(rows("repositories"), repositories, kinds)
    yield Result(
        section,
        "the handbook's repositories match GitHub",
        not problems,
        "Correct GitHub or data/repositories.yaml in the handbook.",
        details=problems,
    )
    expected = {context["code"] for context in rows("contexts")} | {"organization"}
    query = """query($organization: String!, $number: Int!) {
      organization(login: $organization) { projectV2(number: $number) { field(name: "Context") {
        ... on ProjectV2SingleSelectField { options { name } } } } } }"""
    data = gh_json(
        "api",
        "graphql",
        "-F",
        f"number={PROJECT_NUMBER}",
        "-f",
        f"organization={ORGANIZATION}",
        "-f",
        f"query={query}",
    )
    actual = {option["name"] for option in data["data"]["organization"]["projectV2"]["field"]["options"]}
    yield Result(
        section,
        "the project's Context options match the handbook's contexts",
        expected == actual,
        "Correct the project's Context field or data/contexts.yaml in the handbook.",
        details=[f"missing: {', '.join(sorted(expected - actual))}"] * bool(expected - actual)
        + [f"not in the handbook: {', '.join(sorted(actual - expected))}"] * bool(actual - expected),
    )
