"""The doctor's command: exit codes, --json, --quiet, --fix, --dry-run and --skip."""

import contextlib
import io
import json
import os
import unittest
from collections.abc import Callable, Iterator
from unittest import mock

from doctor import checks, cli, repairs
from doctor.results import Result


class RunTest(unittest.TestCase):
    def results(self) -> list[Result]:
        return [
            Result("Tools", "Docker daemon is reachable", False, "Start Docker.", "docker"),
            Result("Credentials", "no credentials", False, "Remove them."),
            Result("Firewall", "the site allowlist is active", False, "Fix.", "firewall"),
            Result("Firewall", "a site is blocked", False, "Fix.", "firewall"),
            Result("Tools", "git is installed", True),
        ]

    def run_doctor(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with (
            mock.patch.object(cli, "check_everything", return_value=self.results()),
            mock.patch.object(repairs, "succeeds", return_value=True) as succeeds,
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = cli.main(list(arguments))
        self.succeeds = succeeds
        return code, output.getvalue()

    def test_failures_exit_with_1_and_say_how_to_fix(self) -> None:
        code, output = self.run_doctor()
        self.assertEqual(code, 1)
        self.assertIn("Fix: Start Docker.", output)
        self.assertIn("ERR 4 check(s) failed", output)

    def test_json_has_every_check_and_its_fix(self) -> None:
        code, output = self.run_doctor("--json")
        document = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(document["failures"], 4)
        self.assertEqual(document["checks"][0]["fix"], "Start Docker.")

    def test_dry_run_lists_each_repair_once_and_changes_nothing(self) -> None:
        code, output = self.run_doctor("--fix", "--dry-run", "--json")
        repairs = [repair["repair"] for repair in json.loads(output)["repairs"]]
        self.assertEqual(repairs, ["start Docker", "apply the site allowlist again"])
        self.succeeds.assert_not_called()

    def test_fix_repairs_only_what_is_safe_then_checks_again(self) -> None:
        code, output = self.run_doctor("--fix", "--json")
        commands = [call.args[0] for call in self.succeeds.call_args_list]
        self.assertIn(["sudo", "systemctl", "start", "docker"], commands)
        self.assertFalse(any("credential" in " ".join(command) for command in commands))
        self.assertTrue(all(repair["done"] for repair in json.loads(output)["repairs"]))

    def test_quiet_shows_only_failures(self) -> None:
        _, output = self.run_doctor("--quiet")
        self.assertNotIn("git is installed", output)
        self.assertIn("Docker daemon is reachable", output)


class SkipTest(unittest.TestCase):
    def test_a_skipped_group_is_not_run_and_is_reported(self) -> None:
        ran: list[str] = []

        def group(name: str) -> Callable[[], Iterator[Result]]:
            def check() -> Iterator[Result]:
                ran.append(name)
                yield Result(name, f"{name} check", True)

            return check

        groups = {"tools": group("tools"), "credentials": group("credentials")}
        with mock.patch.dict(checks.CHECKS, groups, clear=True):
            results = checks.check_everything(["credentials"])
        self.assertEqual(ran, ["tools"])
        self.assertEqual(results[1].name, "skipped on request (--skip credentials)")
        self.assertIsNone(results[1].ok)

    def test_an_unknown_group_is_wrong_usage(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
            cli.main(["--skip", "everything"])
        self.assertEqual(exit.exception.code, 2)

    def test_an_unknown_group_in_the_environment_is_wrong_usage(self) -> None:
        with (
            mock.patch.dict(os.environ, {"BYTELIBRARY_DOCTOR_SKIP": "credentials bogus"}),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as exit,
        ):
            cli.main([])
        self.assertEqual(exit.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
