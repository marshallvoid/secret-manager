from __future__ import annotations

import os
import unittest
from typing import ClassVar, Set
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from secret_manager import theme
from secret_manager.github.models import Owner, Repo
from secret_manager.github.secret_index import RepoSecretStatus
from secret_manager.github.sidebar import OWNER_ROLE, Directory, Sidebar


class SidebarTests(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance() or QApplication([])
        assert isinstance(application, QApplication)
        cls.app = application
        theme.apply(app=cls.app)

    def setUp(self) -> None:
        self.sidebar = Sidebar(on_select=lambda owner: None, on_reload=lambda: None)
        self.sidebar.set_directory(
            directory=Directory(
                repos=[
                    Repo(name="full", full_name="demo/full"),
                    Repo(name="empty", full_name="demo/empty"),
                    Repo(name="denied", full_name="demo/denied"),
                    Repo(name="pending", full_name="demo/pending"),
                ],
                orgs={"example-team": [Repo(name="shared", full_name="example-team/shared")]},
            )
        )
        self.sidebar.set_secret_statuses(
            statuses=[
                RepoSecretStatus(name="demo/full", count=2),
                RepoSecretStatus(name="demo/empty", count=0),
                RepoSecretStatus(name="demo/denied", error="Access denied"),
                RepoSecretStatus(name="example-team/shared", count=1),
            ]
        )
        self.sidebar.resize(340, 700)
        self.sidebar.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.sidebar.close()
        self.sidebar.deleteLater()
        self.app.processEvents()

    def repository_names(self) -> Set[str]:
        names: Set[str] = set()

        for index in range(self.sidebar.list.count()):
            owner = self.sidebar.list.item(index).data(OWNER_ROLE)

            if isinstance(owner, Owner) and owner.kind == "repo":
                names.add(owner.name)

        return names

    def test_filters_distinguish_empty_failed_and_unchecked(self) -> None:
        self.sidebar.secret_filter.setCurrentIndex(1)
        self.assertEqual(self.repository_names(), {"demo/full", "example-team/shared"})
        self.sidebar.secret_filter.setCurrentIndex(2)
        self.assertEqual(self.repository_names(), {"demo/empty"})
        self.sidebar.secret_filter.setCurrentIndex(3)
        self.assertEqual(self.repository_names(), {"demo/denied"})
        self.sidebar.secret_filter.setCurrentIndex(0)
        self.assertEqual(len(self.repository_names()), 5)

    def test_search_combines_with_secret_filter(self) -> None:
        self.sidebar.secret_filter.setCurrentIndex(1)
        self.sidebar.search.setText("shared")
        self.assertEqual(self.repository_names(), {"example-team/shared"})

    def test_sections_toggle_with_keyboard_and_keep_state(self) -> None:

        for title, key in [
            ("Your repositories", "repos"),
            ("example-team", "org:example-team"),
            ("Account", "account"),
        ]:
            button = next(
                button
                for button in self.sidebar.findChildren(QToolButton)
                if button.objectName() == "SectionToggle" and button.text() == title
            )
            button.setFocus()
            QTest.keyClick(button, Qt.Key.Key_Space)
            self.app.processEvents()
            self.assertIn(key, self.sidebar.collapsed)
            self.sidebar.fill()
            self.assertIn(key, self.sidebar.collapsed)

            button = next(
                button
                for button in self.sidebar.findChildren(QToolButton)
                if button.objectName() == "SectionToggle" and button.text() == title
            )
            QTest.keyClick(button, Qt.Key.Key_Space)
            self.app.processEvents()
            self.assertNotIn(key, self.sidebar.collapsed)

    def test_search_actions_are_centered(self) -> None:
        edit = self.sidebar.search

        for button in edit.findChildren(QToolButton):
            self.assertLessEqual(abs(button.geometry().center().y() - edit.rect().center().y()), 2)

    def populate_long_directory(self) -> None:
        self.sidebar.set_directory(
            directory=Directory(
                repos=[Repo(name=f"repo-{index:03}", full_name=f"demo/repo-{index:03}") for index in range(80)]
            )
        )
        self.app.processEvents()

    def test_clicking_repository_preserves_scroll_and_items(self) -> None:
        self.populate_long_directory()
        self.sidebar.on_select = self.sidebar.select
        scrollbar = self.sidebar.list.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum() // 2)
        position = self.sidebar.list.viewport().rect().center()
        item = self.sidebar.list.itemAt(position)
        assert item is not None
        owner = item.data(OWNER_ROLE)
        self.assertIsInstance(owner, Owner)
        before = scrollbar.value()
        QTest.mouseClick(self.sidebar.list.viewport(), Qt.MouseButton.LeftButton, pos=position)
        self.app.processEvents()
        self.assertEqual(self.sidebar.current, owner)
        self.assertIs(self.sidebar.list.currentItem(), item)
        self.assertEqual(scrollbar.value(), before)

    def test_background_metadata_update_does_not_scroll_to_selected_repo(self) -> None:
        self.populate_long_directory()
        self.sidebar.select(owner=Owner(kind="repo", name="demo/repo-000", label="repo-000"))
        scrollbar = self.sidebar.list.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum() // 2)
        before = scrollbar.value()
        self.sidebar.set_secret_statuses(statuses=[RepoSecretStatus(name="demo/repo-000", count=1)])
        self.app.processEvents()
        self.assertEqual(scrollbar.value(), before)
        self.assertEqual(self.sidebar.list.currentItem().data(OWNER_ROLE), self.sidebar.current)

    def test_explicit_selection_reveals_offscreen_repository(self) -> None:
        self.populate_long_directory()
        self.sidebar.select(owner=Owner(kind="repo", name="demo/repo-079", label="repo-079"))
        self.app.processEvents()
        rect = self.sidebar.list.visualItemRect(self.sidebar.list.currentItem())
        self.assertTrue(self.sidebar.list.viewport().rect().contains(rect))

    def test_restoring_filter_does_not_trigger_save_or_network_callbacks(self) -> None:
        changed = Mock()
        filtering = Mock()
        self.sidebar.on_change = changed
        self.sidebar.on_filter = filtering
        self.sidebar.restore_state(repo_filter="with", search="shared", collapsed=["account"])
        self.assertEqual(self.sidebar.secret_filter.currentData(), "with")
        self.assertEqual(self.sidebar.search.text(), "shared")
        self.assertEqual(self.sidebar.collapsed, {"account"})
        self.assertEqual(self.repository_names(), {"example-team/shared"})
        changed.assert_not_called()
        filtering.assert_not_called()
        self.sidebar.search.setText("full")
        changed.assert_called_once()
        self.sidebar.secret_filter.setCurrentIndex(2)
        filtering.assert_called_once()


if __name__ == "__main__":
    unittest.main()
