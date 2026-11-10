from __future__ import annotations

import os
import unittest
from typing import ClassVar
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from secret_manager.widgets import MessagePage
from secret_manager.widgets_links import LinkLabel


class LinkTests(unittest.TestCase):
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance() or QApplication([])
        assert isinstance(application, QApplication)
        cls.app = application

    def test_links_escape_message_and_url(self) -> None:
        label = LinkLabel(text="<script>bad</script> Retry https://example.invalid/api?a=1&b=2.")
        self.assertIn("&lt;script&gt;", label.text())
        self.assertIn('href="https://example.invalid/api?a=1&amp;b=2"', label.text())
        self.assertIn("</a>.", label.text())

    def test_mouse_and_keyboard_activation_use_system_browser(self) -> None:
        label = LinkLabel(text="https://example.invalid/help")

        with patch("secret_manager.widgets_links.QDesktopServices.openUrl") as opened:
            label.linkActivated.emit("https://example.invalid/help")
            self.assertEqual(opened.call_args.args[0].toString(), "https://example.invalid/help")
            label.linkActivated.emit("file:///tmp/example")
            label.linkActivated.emit("javascript:alert(1)")
            self.assertEqual(opened.call_count, 1)

    def test_message_is_centered_and_updated_links_stay_clickable(self) -> None:
        page = MessagePage(icon="info", title="Error")
        page.resize(800, 600)
        url = "https://example.invalid/api/configuration/enable?project=demo-project&retry=true"
        page.show_text(title="Could not load", text=f"API is disabled. Enable it at {url} then retry.")
        page.show()
        self.app.processEvents()
        self.assertIn('href="https://example.invalid/api/', page.body.text())
        self.assertGreaterEqual(page.body.height(), page.body.heightForWidth(page.body.width()))
        self.assertLessEqual(abs(page.body.geometry().center().x() - page.rect().center().x()), 2)
        layout = page.content.layout()
        assert layout is not None
        item = layout.itemAt(1)
        assert item is not None
        first = item.widget()
        assert first is not None
        center = (first.geometry().top() + page.body.geometry().bottom()) / 2
        self.assertLessEqual(abs(center - page.rect().center().y()), 2)
        page.close()

    def test_long_error_scrolls_without_growing_the_page(self) -> None:
        page = MessagePage(icon="info", title="Could not load")
        page.resize(800, 400)
        page.show_text(
            title="Could not load",
            text="Enable https://example.invalid/help then retry.\n" + "Diagnostic details\n" * 100,
        )
        page.show()
        self.app.processEvents()
        self.assertEqual(page.height(), 400)
        self.assertGreater(page.message_scroll.verticalScrollBar().maximum(), 0)
        self.assertEqual(page.message_scroll.horizontalScrollBar().maximum(), 0)
        page.message_scroll.verticalScrollBar().setValue(page.message_scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        bottom = page.body.mapTo(page.message_scroll.viewport(), QPoint(0, page.body.height()))
        self.assertLessEqual(bottom.y(), page.message_scroll.viewport().height())
        self.assertIn('href="https://example.invalid/help"', page.body.text())
        page.show_text(title="Ready", text="Short message")
        self.app.processEvents()
        self.app.processEvents()
        self.assertEqual(page.message_scroll.verticalScrollBar().maximum(), 0)
        page.close()


if __name__ == "__main__":
    unittest.main()
