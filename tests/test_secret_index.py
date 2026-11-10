from __future__ import annotations

import unittest
from unittest.mock import patch

from secret_manager.github import cli
from secret_manager.github.models import Entry
from secret_manager.github.secret_index import inspect_repositories, inspect_repository


class SecretIndexTests(unittest.TestCase):
    def test_inspects_only_secret_metadata_in_repository_scope(self) -> None:

        with patch.object(target=cli, attribute="list_entries", return_value=[Entry(name="DEMO")]) as listing:
            result = inspect_repository(name="demo/sample")

        self.assertEqual(result.count, 1)
        target = listing.call_args.kwargs["target"]
        self.assertEqual(target.kind, "secret")
        self.assertEqual(target.app, "actions")
        self.assertEqual(target.owner, "repo")
        self.assertFalse(target.environment)

    def test_permission_failure_is_unknown_not_empty(self) -> None:

        with patch.object(target=cli, attribute="list_entries", side_effect=cli.GhError("Denied")):
            result = inspect_repository(name="demo/denied")

        self.assertIsNone(result.count)
        self.assertEqual(result.error, "Denied")

    def test_batch_keeps_each_repository_result(self) -> None:

        with patch.object(target=cli, attribute="list_entries", return_value=[]):
            statuses = inspect_repositories(names=["demo/first", "demo/second"])

        self.assertEqual([status.name for status in statuses], ["demo/first", "demo/second"])
        self.assertTrue(all(status.count == 0 for status in statuses))


if __name__ == "__main__":
    unittest.main()
