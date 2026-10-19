"""The doctor's logic: what it reports, and what --fix repairs, from given inputs."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import doctor  # noqa: E402

RANGES = [
    {"code": "shared-components", "first": 8000, "last": 8099},
    {"code": "services", "first": 8100, "last": 8999},
]


class CredentialsTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)

    def write(self, path: str, text: str) -> None:
        (self.home / path).parent.mkdir(parents=True, exist_ok=True)
        (self.home / path).write_text(text)

    def test_a_clean_home_has_none(self) -> None:
        self.write(".ssh/authorized_keys", "ssh-ed25519 AAAA editor")
        self.write(".config/gh-bytelibrary/hosts.yml", "github.com:\n  user: someone\n")
        self.assertEqual(doctor.stray_credentials(self.home, {}), [])

    def test_each_kind_is_reported_with_how_to_remove_it(self) -> None:
        self.write(".config/gh/hosts.yml", "github.com:\n  user: someone\n")
        self.write(".git-credentials", "https://x:token@github.com\n")
        self.write(".ssh/id_ed25519", "-----BEGIN OPENSSH PRIVATE KEY-----\n")
        self.write(".aws/credentials", "[default]\n")
        self.write(".docker/config.json", json.dumps({"auths": {"ghcr.io": {"auth": "eA=="}}}))
        self.write(".npmrc", "//registry.npmjs.org/:_authToken=abc\n")
        self.write(".pypirc", "[pypi]\npassword = abc\n")
        found = doctor.stray_credentials(self.home, {"GH_TOKEN": "x"})
        self.assertEqual(len(found), 8, found)
        self.assertTrue(any("gh auth logout" in finding for finding in found))
        self.assertTrue(any("docker logout" in finding and "ghcr.io" in finding for finding in found))

    def test_docker_settings_without_logins_are_fine(self) -> None:
        self.write(".docker/config.json", json.dumps({"auths": {}, "currentContext": "default"}))
        self.assertEqual(doctor.stray_credentials(self.home, {}), [])


class PortsTest(unittest.TestCase):
    owners = doctor.port_owners(RANGES, [{"name": "catalog", "port_block": 8100}, {"name": "handbook"}])

    def test_owners_cover_the_shared_range_and_each_block(self) -> None:
        self.assertEqual(self.owners[8000], "deployments")
        self.assertEqual(self.owners[8109], "catalog")
        self.assertNotIn(8110, self.owners)

    def test_listening_ports_are_read_from_ss(self) -> None:
        output = "LISTEN 0 4096 0.0.0.0:8102 0.0.0.0:*\nLISTEN 0 128 [::]:22 [::]:*\n"
        self.assertEqual(doctor.listening_ports(output), {8102, 22})

    def test_published_ports_are_read_from_docker(self) -> None:
        output = "catalog-db-1\tcatalog\t0.0.0.0:8102->5432/tcp, [::]:8102->5432/tcp\n"
        self.assertEqual(doctor.container_ports(output), {8102: ("catalog-db-1", "catalog")})

    def test_a_port_used_by_its_repository_is_fine(self) -> None:
        self.assertEqual(doctor.port_problems(self.owners, {8102}, {8102: ("catalog-db-1", "catalog")}), [])

    def test_a_port_used_by_another_project_or_outside_docker_is_reported(self) -> None:
        problems = doctor.port_problems(self.owners, {8102, 8001, 9000}, {8102: ("old-db", "old-test")})
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("docker stop old-db", problems[1])
        self.assertIn("8001 (deployments's ports) is used by a process outside Docker", problems[0])


class ToolsTest(unittest.TestCase):
    def test_only_tools_not_installed_are_missing(self) -> None:
        listing = {
            "python": [{"version": "3.14.8", "requested_version": "3.14.8", "installed": True}],
            "go": [{"version": "1.25.3", "requested_version": "1.25.3", "installed": False}],
        }
        self.assertEqual(doctor.missing_tools(listing), ["go@1.25.3"])


class HandbookTest(unittest.TestCase):
    documented = [
        {
            "name": "handbook",
            "status": "active",
            "kind": "documentation",
            "visibility": "private",
            "description": "D",
        },
        {
            "name": "catalog",
            "status": "planned",
            "kind": "service",
            "visibility": "private",
            "description": "C",
        },
    ]

    def github(self, **changes) -> list[dict]:
        repository = {
            "name": "handbook",
            "archived": False,
            "visibility": "private",
            "description": "D",
            "topics": ["documentation"],
        }
        return [{**repository, **changes}]

    def test_matching_repositories_have_no_differences(self) -> None:
        self.assertEqual(doctor.repository_differences(self.documented, self.github(), {"documentation"}), [])

    def test_differences_are_reported_in_both_directions(self) -> None:
        github = self.github(visibility="public") + [
            {
                "name": "catalog",
                "archived": False,
                "visibility": "private",
                "description": "C",
                "topics": ["service"],
            },
            {
                "name": "extra",
                "archived": False,
                "visibility": "private",
                "description": "",
                "topics": ["service"],
            },
        ]
        problems = doctor.repository_differences(self.documented, github, {"documentation", "service"})
        self.assertEqual(len(problems), 3, problems)

    def test_merge_settings(self) -> None:
        settings = {
            "allow_squash_merge": True,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY",
            "delete_branch_on_merge": True,
        }
        self.assertEqual(doctor.merge_settings(settings), "ok")
        self.assertEqual(doctor.merge_settings({**settings, "allow_merge_commit": True}), "drift")
        self.assertEqual(doctor.merge_settings({}), "unreadable")


class RunTest(unittest.TestCase):
    def results(self) -> list:
        return [
            doctor.Result("Tools", "Docker daemon is reachable", False, "Start Docker.", "docker"),
            doctor.Result("Credentials", "no credentials", False, "Remove them."),
            doctor.Result("Firewall", "the site allowlist is active", False, "Fix.", "firewall"),
            doctor.Result("Firewall", "a site is blocked", False, "Fix.", "firewall"),
            doctor.Result("Tools", "git is installed", True),
        ]

    def run_doctor(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with (
            mock.patch.object(doctor, "check_everything", return_value=self.results()),
            mock.patch.object(doctor, "succeeds", return_value=True) as succeeds,
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = doctor.main(list(arguments))
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
        ran = []

        def group(name):
            def check():
                ran.append(name)
                yield doctor.Result(name, f"{name} check", True)

            return check

        with mock.patch.object(
            doctor, "CHECKS", {"tools": group("tools"), "credentials": group("credentials")}
        ):
            results = doctor.check_everything(["credentials"])
        self.assertEqual(ran, ["tools"])
        self.assertEqual(results[1].name, "skipped on request (--skip credentials)")
        self.assertIsNone(results[1].ok)

    def test_an_unknown_group_is_wrong_usage(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
            doctor.main(["--skip", "everything"])
        self.assertEqual(exit.exception.code, 2)

    def test_an_unknown_group_in_the_environment_is_wrong_usage(self) -> None:
        with (
            mock.patch.dict(doctor.os.environ, {"BYTELIBRARY_DOCTOR_SKIP": "credentials bogus"}),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as exit,
        ):
            doctor.main([])
        self.assertEqual(exit.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
