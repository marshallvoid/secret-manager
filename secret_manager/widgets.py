from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme


class MenuItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    # an item without text is a separator
    text: str | None = None
    action: Callable[[], None] | None = None


SEPARATOR = MenuItem()


# Removes a widget from view at once instead of waiting for deleteLater
def discard(widget: QWidget) -> None:
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


def flat_button(text: str = "", icon: str | None = None, tip: str = "") -> QToolButton:
    button = QToolButton()
    button.setObjectName("Flat")

    if icon:
        button.setIcon(theme.named_icon(key=icon))

    if text:
        button.setText(text)

    button.setToolTip(tip)
    button.setIconSize(QSize(22, 22))
    button.setCursor(Qt.CursorShape.PointingHandCursor)

    return button


def menu_button(parent: QWidget, items: list[MenuItem]) -> QToolButton:
    button = flat_button(icon="more", tip="More")
    menu = QMenu(parent)

    for item in items:
        if item.text is None or item.action is None:
            menu.addSeparator()
        else:
            menu.addAction(item.text, item.action)

    button.setMenu(menu)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    return button


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")

    return label


def icon_label(key: str, size: int, color: str = theme.MUTED) -> QLabel:
    label = QLabel()
    label.setPixmap(theme.named_icon(key=key, color=color).pixmap(size, size))

    return label


def link_button(text: str, action: Callable[[], None]) -> QPushButton:
    button = QPushButton(f"+   {text}")
    button.setObjectName("Link")
    button.setFlat(True)
    button.clicked.connect(lambda _=False: action())

    return button


def primary_button(
    text: str, action: Callable[[], None], icon: str = "add"
) -> QPushButton:
    button = QPushButton(f"  {text}")
    button.setObjectName("Primary")
    button.setIcon(theme.named_icon(key=icon, color=theme.BG))
    button.clicked.connect(lambda _=False: action())

    return button


def search_box(placeholder: str) -> QLineEdit:
    edit = QLineEdit()
    edit.setObjectName("Search")
    edit.setPlaceholderText(placeholder)
    edit.setClearButtonEnabled(True)
    edit.addAction(
        theme.named_icon(key="search"), QLineEdit.ActionPosition.LeadingPosition
    )

    return edit


def chip(text: str, checkable: bool = True) -> QToolButton:
    button = QToolButton()
    button.setObjectName("Chip")
    button.setText(text)
    button.setCheckable(checkable)
    button.setCursor(Qt.CursorShape.PointingHandCursor)

    return button


def badge(text: str, color: str = theme.MUTED) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Badge")
    label.setStyleSheet(f"color: {color}; border-color: {color};")

    return label


def separator() -> QWidget:
    line = QWidget()
    line.setObjectName("Separator")
    line.setFixedHeight(1)
    line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    return line


def read_text_file(parent: QWidget, title: str = "Load value from file") -> str | None:
    path, _ = QFileDialog.getOpenFileName(parent, title)

    if not path:
        return None

    try:
        with open(file=path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        QMessageBox.warning(parent, "Cannot read file", str(exc))

        return None


# The header row of a panel: an icon, a title, then any buttons added to `row`
class PanelHeader(QWidget):
    def __init__(self, icon: str, title: QLabel, height: int = 56) -> None:
        super().__init__()
        self.setObjectName("PanelHeader")
        self.setFixedHeight(height)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(16, 4, 8, 4)
        self.icon = icon_label(key=icon, size=24)
        self.row.addWidget(self.icon)
        self.row.addWidget(title, 1)

    def set_icon(self, key: str) -> None:
        self.icon.setPixmap(theme.named_icon(key=key).pixmap(24, 24))


# A centered icon, heading and text, with an optional main action
class MessagePage(QWidget):
    def __init__(
        self,
        icon: str,
        title: str,
        text: str = "",
        action_text: str = "",
        action: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addStretch(1)

        art = icon_label(key=icon, size=56)
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(art)

        self.heading = QLabel(title)
        self.heading.setObjectName("EmptyTitle")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.heading)

        self.body = muted(text=text)
        self.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.body)

        if action is not None:
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(primary_button(text=action_text, action=action))
            row.addStretch(1)
            layout.addSpacing(8)
            layout.addLayout(row)

        layout.addStretch(2)

    def show_text(self, title: str, text: str = "") -> None:
        self.heading.setText(title)
        self.body.setText(text)


# A text box that grows with its text, from one line up to eight
class AutoText(QPlainTextEdit):
    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.setPlainText(text)
        self.setTabChangesFocus(True)
        self.setPlaceholderText("Value")
        self.textChanged.connect(self._fit)
        self._fit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        lines = max(1, min(8, int(self.document().size().height())))
        margin = 2 * (self.document().documentMargin() + self.frameWidth()) + 2
        self.setFixedHeight(int(lines * self.fontMetrics().lineSpacing() + margin))
