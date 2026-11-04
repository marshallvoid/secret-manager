from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QToolButton

from ...widgets import discard, flat_button, muted
from .paths import parse_path


# The path above the panels: click a segment to go back, or the pencil to type a path
class Breadcrumb(QFrame):
    def __init__(self, navigate: Callable[[list[str]], None]) -> None:
        super().__init__()
        self.setObjectName("Breadcrumb")
        self.navigate = navigate
        self.segments: list[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        home = flat_button(icon="home", tip="Root")
        home.clicked.connect(lambda _=False: navigate([]))
        layout.addWidget(home)

        self.crumbs = QHBoxLayout()
        self.crumbs.setSpacing(2)
        layout.addLayout(self.crumbs)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("/collection/document/…")
        self.edit.hide()
        self.edit.returnPressed.connect(self._go)
        self.edit.installEventFilter(self)
        layout.addWidget(self.edit, 1)
        layout.addStretch(1)

        edit_button = flat_button(icon="edit", tip="Edit path")
        edit_button.clicked.connect(self._start_edit)
        layout.addWidget(edit_button)

    def set_path(self, segments: list[str]) -> None:
        self.segments = list(segments)

        while self.crumbs.count():
            widget = self.crumbs.takeAt(0).widget()

            if widget is not None:
                discard(widget=widget)

        for index, segment in enumerate(segments):
            self.crumbs.addWidget(muted(text="›"))
            crumb = QToolButton()
            crumb.setObjectName("Crumb")
            crumb.setText(segment)
            crumb.setProperty("current", index == len(segments) - 1)
            crumb.setCursor(Qt.CursorShape.PointingHandCursor)
            crumb.clicked.connect(
                lambda _=False, i=index: self.navigate(self.segments[: i + 1])
            )
            self.crumbs.addWidget(crumb)

    def _start_edit(self) -> None:
        self.edit.setText("/" + "/".join(self.segments))
        self.edit.show()
        self.edit.setFocus()
        self.edit.selectAll()

    def _go(self) -> None:
        self.edit.hide()
        self.navigate(parse_path(text=self.edit.text()))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self.edit:
            return False

        if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Escape:
            self.edit.hide()

            return True

        if event.type() == QEvent.Type.FocusOut:
            self.edit.hide()

        return False
