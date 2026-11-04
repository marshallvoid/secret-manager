from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QVBoxLayout,
)

from ... import theme
from ...widgets import (
    SEPARATOR,
    MenuItem,
    PanelHeader,
    discard,
    flat_button,
    link_button,
    menu_button,
)
from .models import NodeKey, Snapshot
from .paths import last_segment

if TYPE_CHECKING:
    from .browser import Browser

PanelData = list[str] | Snapshot


class Panel(QFrame):
    def __init__(
        self,
        browser: Browser,
        index: int,
        path: str,
        title: str,
        icon: str | None,
    ) -> None:
        super().__init__()
        self.setObjectName("Panel")
        self.browser = browser
        self.index = index
        self.path = path
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_label = QLabel(title)
        title_label.setObjectName("PanelTitle")
        title_label.setToolTip("/" + path if path else title)
        self.header = PanelHeader(icon=icon or "document", title=title_label)
        self.header.icon.setVisible(icon is not None)
        layout.addWidget(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        layout.addLayout(self.body, 1)

    def fill(self, data: PanelData) -> None:
        raise NotImplementedError

    # Width that shows the header and every list entry without cutting them
    def content_width(self) -> int:
        width = self.header.sizeHint().width()
        wide = self.findChildren(QPushButton) + self.findChildren(QLabel)

        for child in wide:
            if child.objectName() in ("Link", "FilterBar"):
                width = max(width, child.sizeHint().width())

        for items in self.findChildren(QListWidget):
            items.ensurePolished()
            metrics = items.fontMetrics()
            texts = [items.item(index).text() for index in range(items.count())]

            # item padding (44 + 28) and room for the chevron and a scroll bar
            if texts:
                longest = max(metrics.horizontalAdvance(text) for text in texts)
                width = max(width, longest + 44 + 28 + 24)

        for tree in self.findChildren(QTreeWidget):
            tree.ensurePolished()
            fields = (
                tree.sizeHintForColumn(0) + min(tree.sizeHintForColumn(1), 320) + 48
            )
            width = max(width, fields)

        return max(width, 220)

    def open_child(self, child: str) -> None:
        self.browser.select(index=self.index, child=child)

    def selected_child(self) -> str | None:
        segments = self.browser.path

        return segments[self.index] if self.index < len(segments) else None

    def item_list(
        self,
        ids: list[str],
        on_click: Callable[[str], None],
        max_rows: int | None = None,
    ) -> QListWidget:
        items = QListWidget()
        items.setObjectName("Items")
        items.setItemDelegate(theme.ChevronDelegate(parent=items))
        items.setFrameShape(QFrame.Shape.NoFrame)
        items.addItems(ids)
        chosen = self.selected_child()

        if chosen in ids:
            items.setCurrentRow(ids.index(chosen))

        items.itemClicked.connect(lambda item: on_click(item.text()))

        if max_rows is not None:
            items.ensurePolished()
            height = items.sizeHintForRow(0) if ids else 0
            items.setFixedHeight(min(len(ids), max_rows) * height + 2)
            items.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        return items

    def note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Note")
        label.setWordWrap(True)

        return label

    def show_loading(self) -> None:
        self.body.addWidget(self.note(text="Loading…"))
        self.body.addStretch(1)

    def clear_body(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)

            if item.widget() is not None:
                discard(widget=item.widget())

    def show_error(self, text: str) -> None:
        self.clear_body()
        self.body.addWidget(self.note(text=f"Could not load: {text.splitlines()[0]}"))
        self.body.addStretch(1)


class EmptyPanel(Panel):
    def __init__(self, browser: Browser) -> None:
        super().__init__(browser=browser, index=-1, path="", title="", icon=None)

    def fill(self, data: PanelData) -> None:
        return None


class RootPanel(Panel):
    def __init__(self, browser: Browser, index: int, path: str) -> None:
        store = browser.require_store()
        super().__init__(
            browser=browser,
            index=index,
            path=path,
            title=store.database,
            icon="database",
        )

        info = QLabel()
        info.setPixmap(theme.named_icon(key="info").pixmap(20, 20))
        info.setToolTip(f"Project: {store.project}\nDatabase: {store.database}")
        self.header.row.insertWidget(2, info)

        refresh = flat_button(icon="refresh", tip="Refresh")
        refresh.clicked.connect(lambda _=False: browser.refresh())
        self.header.row.addWidget(refresh)

    def fill(self, data: PanelData) -> None:
        ids = data if isinstance(data, list) else []
        self.clear_body()
        start = link_button(
            text="Start collection",
            action=lambda: self.browser.start_collection(parent_doc=""),
        )
        self.body.addWidget(start)
        self.body.addWidget(self.item_list(ids=ids, on_click=self.open_child), 1)


class CollectionPanel(Panel):
    def __init__(self, browser: Browser, index: int, path: str) -> None:
        super().__init__(
            browser=browser,
            index=index,
            path=path,
            title=last_segment(path=path),
            icon="collection",
        )
        query = browser.queries.get(path)
        active = query is not None and query.active

        filter_button = flat_button(tip="Filter and sort")
        color = theme.ACCENT if active else theme.MUTED
        filter_button.setIcon(theme.named_icon(key="filter", color=color))
        filter_button.clicked.connect(
            lambda _=False: browser.set_filter(coll_path=path)
        )
        self.header.row.addWidget(filter_button)

        items = [
            MenuItem(
                text="Copy collection path", action=lambda: browser.copy_text(text=path)
            ),
            MenuItem(
                text="Refresh",
                action=lambda: browser.invalidate(
                    keys=[NodeKey(kind="collection", path=path)]
                ),
            ),
            SEPARATOR,
            MenuItem(
                text="Delete collection",
                action=lambda: browser.delete_collection(coll_path=path),
            ),
        ]
        self.header.row.addWidget(menu_button(parent=self, items=items))

    def fill(self, data: PanelData) -> None:
        ids = data if isinstance(data, list) else []
        self.clear_body()
        query = self.browser.queries.get(self.path)
        active = query is not None and query.active

        if query is not None and active:
            bar = QLabel(f"Filtered: {query.describe()}   ✕")
            bar.setObjectName("FilterBar")
            bar.setCursor(Qt.CursorShape.PointingHandCursor)
            bar.setToolTip("Clear the filter")
            bar.mousePressEvent = self._clear_filter
            self.body.addWidget(bar)

        add = link_button(
            text="Add document",
            action=lambda: self.browser.add_document(coll_path=self.path),
        )
        self.body.addWidget(add)

        if not ids:
            text = (
                "No documents match this filter"
                if active
                else "This collection is empty"
            )
            self.body.addWidget(self.note(text=text))
            self.body.addStretch(1)

            return

        self.body.addWidget(self.item_list(ids=ids, on_click=self.open_child), 1)

    def _clear_filter(self, _event: QMouseEvent) -> None:
        self.browser.clear_filter(coll_path=self.path)
