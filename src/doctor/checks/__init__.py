"""Every group of checks, and running them."""

from collections.abc import Callable, Collection, Iterator

from doctor.checks import credentials, firewall, github_data, ports, sign_in, tools, workspace
from doctor.results import Result

# Each group of checks, by the name --skip takes, in the order they run.
CHECKS: dict[str, Callable[[], Iterator[Result]]] = {
    "tools": tools.check,
    "firewall": firewall.check,
    "credentials": credentials.check,
    "ports": ports.check,
    "sign-in": sign_in.check,
    "github-data": github_data.check,
    "workspace": workspace.check,
}


def check_everything(skip: Collection[str] = ()) -> list[Result]:
    results: list[Result] = []
    for name, check in CHECKS.items():
        if name in skip:
            results.append(Result(name, f"skipped on request (--skip {name})", None))
            continue
        try:
            results += list(check())
        except Exception as error:  # A broken check is a failure to report, not a crash.
            results.append(Result(name, f"the check could not run: {error}", False))
    return results
