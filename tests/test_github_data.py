"""The handbook's data and repository settings against GitHub."""

import unittest

from doctor.checks.github_data import (
    ContextOptions,
    GitHubRepository,
    MergeSettings,
    merge_settings,
    repository_differences,
)
from doctor.handbook import HandbookRepository


def github(name: str, topics: list[str], **changes: object) -> GitHubRepository:
    fields = {"name": name, "archived": False, "visibility": "private", "description": "D", "topics": topics}
    return GitHubRepository.model_validate({**fields, **changes})


class HandbookTest(unittest.TestCase):
    documented = [
        HandbookRepository(
            name="handbook", status="active", kind="documentation", visibility="private", description="D"
        ),
        HandbookRepository(
            name="catalog", status="planned", kind="service", visibility="private", description="C"
        ),
    ]

    def test_matching_repositories_have_no_differences(self) -> None:
        on_github = [github("handbook", ["documentation"])]
        self.assertEqual(repository_differences(self.documented, on_github, {"documentation"}), [])

    def test_differences_are_reported_in_both_directions(self) -> None:
        on_github = [
            github("handbook", ["documentation"], visibility="public"),
            github("catalog", ["service"], description="C"),
            github("extra", ["service"], description=""),
        ]
        problems = repository_differences(self.documented, on_github, {"documentation", "service"})
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
        self.assertEqual(merge_settings(MergeSettings.model_validate(settings)), "ok")
        drift = MergeSettings.model_validate({**settings, "allow_merge_commit": True})
        self.assertEqual(merge_settings(drift), "drift")
        self.assertEqual(merge_settings(MergeSettings.model_validate({})), "unreadable")

    def test_fields_the_doctor_does_not_use_are_ignored(self) -> None:
        repository = github("handbook", [], id=1, owner={"login": "ByteLibrary"})
        self.assertEqual(repository.name, "handbook")

    def test_the_context_options_are_read_from_the_graphql_answer(self) -> None:
        answer = {"data": {"organization": {"projectV2": {"field": {"options": [{"name": "catalog"}]}}}}}
        self.assertEqual(
            [option.name for option in ContextOptions.model_validate(answer).options], ["catalog"]
        )


class TopicsTest(unittest.TestCase):
    def test_a_service_needs_its_kind_and_context_but_no_language_topic(self) -> None:
        documented = [
            HandbookRepository(
                name="catalog-service",
                status="active",
                kind="service",
                visibility="private",
                description="C",
                context="catalog",
            )
        ]
        topics = ["context-catalog", "service"]
        on_github = [github("catalog-service", topics, description="C")]
        self.assertEqual(repository_differences(documented, on_github, {"service"}), [])
        on_github = [github("catalog-service", [*topics, "language-go"], description="C")]
        self.assertEqual(len(repository_differences(documented, on_github, {"service"})), 1)


if __name__ == "__main__":
    unittest.main()
