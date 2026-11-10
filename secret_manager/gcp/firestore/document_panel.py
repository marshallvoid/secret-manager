from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ... import theme
from ...utils.names import env_name
from ...widgets import (
    SEPARATOR,
    MenuItem,
    discard,
    flat_button,
    link_button,
    menu_button,
    muted,
    separator,
)
from . import values
from .models import NodeKey, Snapshot
from .panels import Panel, PanelData
from .paths import field_path, last_segment
from .values import KeyPath

if TYPE_CHECKING:
    from .browser import Browser

PATH_ROLE = Qt.ItemDataRole.UserRole
# a field action gets the document path and the field's path
FieldAction = Callable[[str, KeyPath], None]


class HoverFilter(QObject):
    def __init__(self, panel: DocumentPanel) -> None:
        super().__init__(panel)
        self.panel = panel

    # Moving onto the floating buttons also sends Leave, so check where the cursor really is
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Leave or not isinstance(watched, QWidget):
            return False

        if not watched.rect().contains(watched.mapFromGlobal(QCursor.pos())):
            self.panel.unhover()

        return False


class DocumentPanel(Panel):
    def __init__(self, browser: Browser, index: int, path: str) -> None:
        super().__init__(
            browser=browser,
            index=index,
            path=path,
            title=last_segment(path=path),
            icon="document",
        )
        self.data: dict[str, Any] = {}
        self.tree: QTreeWidget | None = None
        self.hovered: QTreeWidgetItem | None = None
        self.hover_box: QWidget | None = None

        items = [
            MenuItem(
                text="Add similar document",
                action=lambda: browser.add_similar(doc_path=path),
            ),
            MenuItem(text="Copy document path", action=lambda: browser.copy_text(text=path)),
            MenuItem(
                text="Refresh",
                action=lambda: browser.invalidate(keys=[NodeKey(kind="document", path=path)]),
            ),
            SEPARATOR,
            MenuItem(
                text="Delete document",
                action=lambda: browser.delete_document(doc_path=path),
            ),
            MenuItem(
                text="Delete document fields",
                action=lambda: browser.clear_document(doc_path=path),
            ),
        ]
        self.header.row.addWidget(menu_button(parent=self, items=items))

    def fill(self, data: PanelData) -> None:
        snapshot = data if isinstance(data, Snapshot) else Snapshot()
        self.unhover()
        self.clear_body()
        self.data = snapshot.data

        start = link_button(
            text="Start collection",
            action=lambda: self.browser.start_collection(parent_doc=self.path),
        )
        self.body.addWidget(start)

        if snapshot.subcollections:
            self.body.addWidget(self.item_list(ids=snapshot.subcollections, on_click=self.open_child, max_rows=6))

        self.body.addWidget(separator())
        self.body.addWidget(
            link_button(
                text="Add field",
                action=lambda: self.browser.add_field(doc_path=self.path),
            )
        )

        if not snapshot.exists:
            text = "This document does not exist, it will not appear in queries or snapshots"
            self.body.addWidget(self.note(text=text))

        self.tree = self._build_tree()
        self.body.addWidget(self.tree, 1)

    def _build_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setObjectName("Fields")
        tree.setColumnCount(2)
        tree.setHeaderHidden(True)
        tree.setIndentation(18)
        tree.setMouseTracking(True)
        tree.setExpandsOnDoubleClick(False)
        tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        tree.setFrameShape(QFrame.Shape.NoFrame)

        header = tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        expanded = self.browser.expanded.setdefault(self.path, set())

        for key in sorted(self.data):
            self._add(
                parent=tree,
                key=key,
                value=self.data[key],
                path=[key],
                expanded=expanded,
            )

        tree.itemExpanded.connect(lambda item: expanded.add(self._key(item=item)))
        tree.itemCollapsed.connect(lambda item: expanded.discard(self._key(item=item)))
        tree.itemEntered.connect(lambda item, _column: self.hover(item=item))
        tree.itemDoubleClicked.connect(lambda item, _column: self._later(action=self.browser.edit_field, item=item))
        tree.viewport().installEventFilter(HoverFilter(panel=self))
        tree.verticalScrollBar().valueChanged.connect(lambda _: self.unhover())
        tree.itemExpanded.connect(lambda _: self.unhover())
        tree.itemCollapsed.connect(lambda _: self.unhover())
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._context_menu)

        return tree

    @staticmethod
    def _key(item: QTreeWidgetItem) -> tuple[str | int, ...]:
        return tuple(item.data(0, PATH_ROLE))

    def _add(
        self,
        parent: QTreeWidget | QTreeWidgetItem,
        key: str | int,
        value: Any,
        path: KeyPath,
        expanded: set[tuple[str | int, ...]],
    ) -> None:
        kind = values.type_of(value=value)
        item = QTreeWidgetItem(parent)
        item.setData(0, PATH_ROLE, path)

        if kind in values.CONTAINERS:
            item.setText(0, str(key))
            item.setText(1, values.preview(value=value, limit=200) if kind == "array" else "")
            item.setForeground(1, QColor(theme.MUTED))
            children = sorted(value.items()) if kind == "map" else list(enumerate(value))

            for child_key, child in children:
                self._add(
                    parent=item,
                    key=child_key,
                    value=child,
                    path=[*path, child_key],
                    expanded=expanded,
                )

            if tuple(path) in expanded:
                item.setExpanded(True)
        else:
            item.setText(0, f"{key}:")
            item.setText(1, values.preview(value=value, limit=200))

        item.setToolTip(1, values.preview(value=value, limit=4000))

    # Runs after the click finishes, since the tree is rebuilt once the write lands
    def _later(self, action: FieldAction, item: QTreeWidgetItem) -> None:
        path: KeyPath = item.data(0, PATH_ROLE)
        QTimer.singleShot(0, lambda: action(self.path, path))

    def hover(self, item: QTreeWidgetItem) -> None:
        if item is self.hovered or self.tree is None:
            return

        self.unhover()
        self.hovered = item
        path: KeyPath = item.data(0, PATH_ROLE)
        kind = values.type_of(value=values.get_at(data=self.data, path=path))

        # floats over the right end of the row, as in the console
        box = QWidget(self.tree.viewport())
        box.setObjectName("HoverActions")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(16, 0, 6, 0)
        layout.setSpacing(2)
        layout.addWidget(muted(text=f"({kind})"))

        if kind in values.CONTAINERS:
            add = flat_button(icon="add", tip="Add field" if kind == "map" else "Add item")
            add.clicked.connect(lambda _=False: self._later(action=self.browser.add_child, item=item))
            layout.addWidget(add)

        edit = flat_button(icon="edit", tip="Edit field")
        edit.clicked.connect(lambda _=False: self._later(action=self.browser.edit_field, item=item))
        layout.addWidget(edit)

        delete = flat_button(icon="delete", tip="Delete field")
        delete.clicked.connect(lambda _=False: self._later(action=self.browser.delete_field, item=item))
        layout.addWidget(delete)

        rect = self.tree.visualItemRect(item)
        box.adjustSize()
        box.setFixedHeight(rect.height())
        box.move(self.tree.viewport().width() - box.width(), rect.top())
        box.show()
        self.hover_box = box

    def unhover(self) -> None:
        self.hovered = None
        box, self.hover_box = self.hover_box, None

        if box is not None:
            discard(widget=box)

    def _context_menu(self, pos: QPoint) -> None:
        if self.tree is None:
            return

        item = self.tree.itemAt(pos)

        if item is None:
            return

        path: KeyPath = item.data(0, PATH_ROLE)
        value = values.get_at(data=self.data, path=path)
        kind = values.type_of(value=value)
        browser = self.browser
        menu = QMenu(self)
        menu.addAction("Edit field…", lambda: self._later(action=browser.edit_field, item=item))

        if kind in values.CONTAINERS:
            menu.addAction(
                "Add field…" if kind == "map" else "Add item…",
                lambda: self._later(action=browser.add_child, item=item),
            )

        menu.addSeparator()
        menu.addAction("Copy value", lambda: browser.copy_value(text=values.plain(value=value)))
        menu.addAction("Copy field path", lambda: browser.copy_text(text=field_path(path=path)))

        if kind == "string":
            key = path[-1] if isinstance(path[-1], str) else path[0]
            menu.addAction(
                "Set as GitHub secret…",
                lambda: browser.app.github.push_secret(
                    parent=self,
                    name=env_name(text=str(key)),
                    value=value,
                ),
            )

        menu.addSeparator()
        menu.addAction("Delete field", lambda: self._later(action=browser.delete_field, item=item))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
