from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from secret_manager import settings


class SettingsTests(unittest.TestCase):
    def test_sidebar_state_round_trip_uses_only_synthetic_config(self) -> None:

        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"

            with patch.object(target=settings, attribute="settings_path", return_value=path):
                original = settings.AppSettings(
                    github_repo_filter="without",
                    github_repo_search="demo",
                    github_collapsed_sections=["account", "repos"],
                )
                settings.save(settings=original)
                restored = settings.load()

        self.assertEqual(restored.github_repo_filter, "without")
        self.assertEqual(restored.github_repo_search, "demo")
        self.assertEqual(restored.github_collapsed_sections, ["account", "repos"])

    def test_existing_config_gets_sidebar_defaults(self) -> None:
        restored = settings.AppSettings.model_validate(obj={"github_scope": "actions"})
        self.assertEqual(restored.github_repo_filter, "all")
        self.assertEqual(restored.github_repo_search, "")
        self.assertEqual(restored.github_collapsed_sections, [])


if __name__ == "__main__":
    unittest.main()
