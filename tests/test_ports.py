"""Local ports against the handbook's port data."""

import unittest

from doctor.checks.ports import container_ports, listening_ports, port_owners, port_problems

RANGES = [
    {"code": "shared-components", "first": 8000, "last": 8099},
    {"code": "services", "first": 8100, "last": 8999},
]


class PortsTest(unittest.TestCase):
    owners = port_owners(RANGES, [{"name": "catalog", "port_block": 8100}, {"name": "handbook"}])

    def test_owners_cover_the_shared_range_and_each_block(self) -> None:
        self.assertEqual(self.owners[8000], "deployments")
        self.assertEqual(self.owners[8109], "catalog")
        self.assertNotIn(8110, self.owners)

    def test_listening_ports_are_read_from_ss(self) -> None:
        output = "LISTEN 0 4096 0.0.0.0:8102 0.0.0.0:*\nLISTEN 0 128 [::]:22 [::]:*\n"
        self.assertEqual(listening_ports(output), {8102, 22})

    def test_published_ports_are_read_from_docker(self) -> None:
        output = "catalog-db-1\tcatalog\t0.0.0.0:8102->5432/tcp, [::]:8102->5432/tcp\n"
        self.assertEqual(container_ports(output), {8102: ("catalog-db-1", "catalog")})

    def test_a_port_used_by_its_repository_is_fine(self) -> None:
        self.assertEqual(port_problems(self.owners, {8102}, {8102: ("catalog-db-1", "catalog")}), [])

    def test_a_port_used_by_another_project_or_outside_docker_is_reported(self) -> None:
        problems = port_problems(self.owners, {8102, 8001, 9000}, {8102: ("old-db", "old-test")})
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("docker stop old-db", problems[1])
        self.assertIn("8001 (deployments's ports) is used by a process outside Docker", problems[0])


if __name__ == "__main__":
    unittest.main()
