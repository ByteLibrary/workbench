"""The firewall script's parts that need no root: reading the sites files, writing the resolver's
configuration, and finding the refused names and addresses in the logs."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "firewall.py"

spec = importlib.util.spec_from_file_location("firewall", SCRIPT)
firewall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firewall)


class SitesTest(unittest.TestCase):
    def sites(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "allowed-sites"
        path.write_text(text)
        return path

    def test_domains_without_comments_and_blank_lines(self) -> None:
        path = self.sites("# GitHub\ngithub.com\n\n  pypi.org  # packages\nfiles.pythonhosted.org\n")
        self.assertEqual(firewall.domains(path), ["github.com", "pypi.org", "files.pythonhosted.org"])

    def test_a_missing_file_has_no_domains(self) -> None:
        self.assertEqual(firewall.domains(Path("/nonexistent/allowed-sites")), [])

    def test_anything_but_a_plain_domain_is_refused(self) -> None:
        for line in ("localhost", "https://github.com", "github.com/x", "-bad.com", "a.com\nserver=/x/1"):
            with self.subTest(line=line), self.assertRaises(firewall.NotADomain):
                firewall.domains(self.sites(line + "\n"))

    def test_the_shared_file_is_valid(self) -> None:
        self.assertIn("github.com", firewall.domains(firewall.SHARED_SITES))


class ConfigTest(unittest.TestCase):
    def test_each_allowed_domain_goes_to_every_server_and_fills_the_firewall_set(self) -> None:
        config = firewall.dns_config(["pypi.org", "github.com", "pypi.org"], ["10.0.0.1", "10.0.0.2"])
        lines = config.splitlines()
        self.assertIn("no-resolv", lines)
        self.assertEqual(
            [line for line in lines if line.startswith(("server=", "nftset="))],
            [
                "server=/github.com/10.0.0.1",
                "server=/github.com/10.0.0.2",
                "nftset=/github.com/4#inet#bytelibrary#allowed4,6#inet#bytelibrary#allowed6",
                "server=/pypi.org/10.0.0.1",
                "server=/pypi.org/10.0.0.2",
                "nftset=/pypi.org/4#inet#bytelibrary#allowed4,6#inet#bytelibrary#allowed6",
            ],
        )

    def test_nameservers_come_from_the_networks_resolv_conf(self) -> None:
        resolv_conf = "# managed\nnameserver 10.0.0.1\nsearch lan\nnameserver fe80::1\n"
        self.assertEqual(firewall.nameservers(resolv_conf), ["10.0.0.1", "fe80::1"])


class BlockedTest(unittest.TestCase):
    def test_names_not_covered_by_an_allowed_domain(self) -> None:
        log = (
            "query[A] api.github.com from 127.0.0.1\n"
            "query[AAAA] example.com from 172.17.0.2\n"
            "query[A] github.com.evil.org from 127.0.0.1\n"
            "query[PTR] 1.0.0.10.in-addr.arpa from 127.0.0.1\n"
            "query[A] localhost from 127.0.0.1\n"
            "forwarded api.github.com to 10.0.0.1\n"
        )
        self.assertEqual(firewall.blocked_names(log, {"github.com"}), ["example.com", "github.com.evil.org"])

    def test_addresses_refused_by_the_firewall(self) -> None:
        log = (
            "bytelibrary-blocked: IN= OUT=eth0 SRC=10.0.0.5 DST=203.0.113.7 LEN=60 PROTO=TCP\n"
            "an unrelated kernel message\n"
        )
        self.assertEqual(firewall.blocked_addresses(log), ["address 203.0.113.7"])


if __name__ == "__main__":
    unittest.main()
