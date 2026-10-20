"""Tools at their pinned versions."""

import unittest

from doctor.checks.tools import MISE_LISTING, missing_tools


class ToolsTest(unittest.TestCase):
    def test_only_tools_not_installed_are_missing(self) -> None:
        listing = MISE_LISTING.validate_python(
            {
                "python": [{"version": "3.14.8", "requested_version": "3.14.8", "installed": True}],
                "go": [{"version": "1.25.3", "requested_version": "1.25.3", "installed": False}],
            }
        )
        self.assertEqual(missing_tools(listing), ["go@1.25.3"])


if __name__ == "__main__":
    unittest.main()
