"""The handbook's data and repository settings against GitHub."""

import unittest

from doctor.checks.github_data import merge_settings, repository_differences


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
        self.assertEqual(repository_differences(self.documented, self.github(), {"documentation"}), [])

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
        problems = repository_differences(self.documented, github, {"documentation", "service"})
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
        self.assertEqual(merge_settings(settings), "ok")
        self.assertEqual(merge_settings({**settings, "allow_merge_commit": True}), "drift")
        self.assertEqual(merge_settings({}), "unreadable")


if __name__ == "__main__":
    unittest.main()
