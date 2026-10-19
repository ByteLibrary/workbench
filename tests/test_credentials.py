"""Credentials the doctor reports, and how it says to remove them."""

import json
import tempfile
import unittest
from pathlib import Path

from doctor.checks.credentials import stray_credentials


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
        self.assertEqual(stray_credentials(self.home, {}), [])

    def test_each_kind_is_reported_with_how_to_remove_it(self) -> None:
        self.write(".config/gh/hosts.yml", "github.com:\n  user: someone\n")
        self.write(".git-credentials", "https://x:token@github.com\n")
        self.write(".ssh/id_ed25519", "-----BEGIN OPENSSH PRIVATE KEY-----\n")
        self.write(".aws/credentials", "[default]\n")
        self.write(".docker/config.json", json.dumps({"auths": {"ghcr.io": {"auth": "eA=="}}}))
        self.write(".npmrc", "//registry.npmjs.org/:_authToken=abc\n")
        self.write(".pypirc", "[pypi]\npassword = abc\n")
        found = stray_credentials(self.home, {"GH_TOKEN": "x"})
        self.assertEqual(len(found), 8, found)
        self.assertTrue(any("gh auth logout" in finding for finding in found))
        self.assertTrue(any("docker logout" in finding and "ghcr.io" in finding for finding in found))

    def test_docker_settings_without_logins_are_fine(self) -> None:
        self.write(".docker/config.json", json.dumps({"auths": {}, "currentContext": "default"}))
        self.assertEqual(stray_credentials(self.home, {}), [])


if __name__ == "__main__":
    unittest.main()
