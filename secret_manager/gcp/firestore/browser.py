from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QResizeEvent
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QSplitter, QVBoxLayout

from ...dialogs import ConfirmDialog, ask_yes_no
from ...widgets import discard
from . import values
from .breadcrumb import Breadcrumb
from .dialogs import DocumentDialog, FieldDialog, FilterDialog
from .document_panel import DocumentPanel
from .models import NodeKey, Query, Snapshot
from .panels import CollectionPanel, EmptyPanel, Panel, PanelData, RootPanel
from .paths import field_path, join, last_segment, parent_path, parse_path
from .store import DELETE, Store
from .values import KeyPath

if TYPE_CHECKING:
    from ...app import App

ROOT = NodeKey(kind="root", path="")
PANEL_TYPES: dict[str, Callable[..., Panel]] = {
    "root": RootPanel,
    "collection": CollectionPanel,
    "document": DocumentPanel,
}


def parent_key(path: str) -> NodeKey:
    parent = parent_path(path=path)

    return NodeKey(kind="document", path=parent) if parent else ROOT


class Browser(QFrame):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.setObjectName("Browser")
        self.app = app
        self.store: Store | None = None
        self.path: list[str] = []
        self.cache: dict[NodeKey, PanelData] = {}
        self.loading: set[NodeKey] = set()
        self.panels: dict[NodeKey, Panel] = {}
        self.queries: dict[str, Query] = {}
        # document path → paths of the expanded map and array fields
        self.expanded: dict[str, set[tuple[str | int, ...]]] = {}
        self.user_sized = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.breadcrumb = Breadcrumb(
            navigate=lambda segments: self.navigate(segments=segments)
        )
        layout.addWidget(self.breadcrumb)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.splitterMoved.connect(self._user_resized)
        layout.addWidget(self.splitter, 1)
        self.render()

    def require_store(self) -> Store:
        if self.store is None:
            raise RuntimeError("Firestore is not open")

        return self.store

    def set_store(self, store: Store, root_ids: list[str], path: list[str]) -> None:
        self.store = store
        self.cache = {ROOT: root_ids}
        self.loading = set()
        self.queries = {}
        self.expanded = {}
        self.navigate(segments=path)

    # node 0 is the database, odd nodes are collections, even ones documents
    def node(self, index: int) -> NodeKey:
        path = join(*self.path[:index])

        if index == 0:
            return ROOT

        return NodeKey(kind="collection" if index % 2 else "document", path=path)

    def navigate(self, segments: list[str]) -> None:
        self.path = list(segments)
        self.app.save_settings()
        self.render()

    def select(self, index: int, child: str) -> None:
        self.navigate(segments=[*self.path[:index], child])

    def _user_resized(self, *_args: int) -> None:
        self.user_sized = True

    # The first columns fit their content and the last one takes the rest, until the user drags
    def fit_columns(self) -> None:
        count = self.splitter.count()

        if self.user_sized or count < 2:
            return

        total = self.splitter.width()
        panels = [self.splitter.widget(index) for index in range(count)]
        firsts = [
            min(panel.content_width(), total // 3) if isinstance(panel, Panel) else 0
            for panel in panels[:-1]
        ]
        self.splitter.setSizes([*firsts, max(total - sum(firsts), 300)])

    def schedule_fit(self) -> None:
        QTimer.singleShot(0, self.fit_columns)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.schedule_fit()

    def render(self) -> None:
        for index in reversed(range(self.splitter.count())):
            discard(widget=self.splitter.widget(index))

        self.panels = {}
        self.user_sized = False
        self.breadcrumb.set_path(segments=self.path)

        if self.store is None:
            note = QLabel(
                "Choose a service account file and press Connect to browse Firestore."
            )
            note.setObjectName("Note")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.splitter.addWidget(note)

            return

        last = len(self.path)
        shown: list[Panel] = []

        for index in range(max(0, last - 2), last + 1):
            key = self.node(index=index)
            panel = PANEL_TYPES[key.kind](browser=self, index=index, path=key.path)
            self.panels[key] = panel

            if key in self.cache:
                panel.fill(data=self.cache[key])
            else:
                panel.show_loading()
                self.load(key=key)

            shown.append(panel)

        while len(shown) < 3:
            shown.append(EmptyPanel(browser=self))

        for index, panel in enumerate(shown):
            self.splitter.addWidget(panel)
            self.splitter.setStretchFactor(index, 1 if index == len(shown) - 1 else 0)

        self.schedule_fit()

    def load(self, key: NodeKey) -> None:
        if key in self.loading:
            return

        self.loading.add(key)
        store = self.require_store()
        path = key.path

        def work() -> PanelData:
            if key.kind == "root":
                return store.root_collections()

            if key.kind == "collection":
                return store.document_ids(coll_path=path, query=self.queries.get(path))

            return store.document(doc_path=path)

        def done(result: PanelData) -> None:
            self.loading.discard(key)

            if store is not self.store:
                return

            self.cache[key] = result
            panel = self.panels.get(key)

            if panel is not None:
                panel.fill(data=result)
                self.schedule_fit()

            self.app.status(
                text=f"Loaded /{path}" if path else f"Loaded {store.database}"
            )

        def failed(exc: Exception) -> None:
            self.loading.discard(key)
            panel = self.panels.get(key)

            if panel is not None:
                panel.show_error(text=str(exc) or type(exc).__name__)

        self.app.run(work=work, done=done, busy="Loading…", failed=failed)

    def refresh(self) -> None:
        self.cache.clear()
        self.render()

    # Drops cached panels so they reload; `prefix` also drops everything under a path
    def invalidate(self, keys: list[NodeKey] | None = None, prefix: str = "") -> None:
        for key in keys or []:
            self.cache.pop(key, None)

        if prefix:
            stale = [
                key
                for key in self.cache
                if key.path == prefix or key.path.startswith(prefix + "/")
            ]

            for key in stale:
                self.cache.pop(key)

        self.render()

    def copy_text(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.app.status(text="Copied to the clipboard")

    def doc_data(self, doc_path: str) -> dict[str, Any]:
        cached = self.cache.get(NodeKey(kind="document", path=doc_path))

        return cached.data if isinstance(cached, Snapshot) else {}

    # ---- collections and documents

    def start_collection(self, parent_doc: str) -> None:
        result = DocumentDialog(
            parent=self,
            title="Start a collection",
            parent_path="/" + parent_doc,
            ask_collection=True,
        ).ask()

        if result is None:
            return

        coll_path = join(parent_doc, result.collection)
        store = self.require_store()

        def done(_: str) -> None:
            self.invalidate(
                keys=[
                    parent_key(path=coll_path),
                    NodeKey(kind="collection", path=coll_path),
                ]
            )
            self.navigate(segments=parse_path(text=join(coll_path, result.doc_id)))

        self.app.run(
            work=lambda: store.create_document(
                coll_path=coll_path, doc_id=result.doc_id, data=result.data
            ),
            done=done,
            busy="Creating…",
        )

    def add_document(
        self,
        coll_path: str,
        data: dict[str, Any] | None = None,
        title: str = "Add a document",
    ) -> None:
        result = DocumentDialog(
            parent=self, title=title, parent_path="/" + coll_path, data=data
        ).ask()

        if result is None:
            return

        doc_path = join(coll_path, result.doc_id)
        store = self.require_store()

        def done(_: str) -> None:
            self.invalidate(
                keys=[
                    NodeKey(kind="collection", path=coll_path),
                    NodeKey(kind="document", path=doc_path),
                ]
            )
            self.navigate(segments=parse_path(text=doc_path))

        self.app.run(
            work=lambda: store.create_document(
                coll_path=coll_path, doc_id=result.doc_id, data=result.data
            ),
            done=done,
            busy="Adding…",
        )

    def add_similar(self, doc_path: str) -> None:
        self.add_document(
            coll_path=parent_path(path=doc_path),
            data=values.copy_value(value=self.doc_data(doc_path=doc_path)),
            title="Add similar document",
        )

    def delete_collection(self, coll_path: str) -> None:
        if not ConfirmDialog(
            parent=self,
            title="Delete collection",
            text=f"This permanently deletes /{coll_path}: every document in it and all of "
            "their subcollections. This cannot be undone.",
            confirm=last_segment(path=coll_path),
        ).ask():
            return

        store = self.require_store()

        def done(_: None) -> None:
            self.app.status(text=f"Deleted /{coll_path}")
            self.cache.pop(parent_key(path=coll_path), None)
            self.invalidate(prefix=coll_path)
            self.navigate(segments=parse_path(text=coll_path)[:-1])

        self.app.run(
            work=lambda: store.delete_collection(coll_path=coll_path),
            done=done,
            busy="Deleting collection…",
        )

    def delete_document(self, doc_path: str) -> None:
        if not ConfirmDialog(
            parent=self,
            title="Delete document",
            text=f"This permanently deletes /{doc_path} and all of its subcollections. "
            "This cannot be undone.",
        ).ask():
            return

        store = self.require_store()
        coll_path = parent_path(path=doc_path)

        def done(_: None) -> None:
            self.app.status(text=f"Deleted /{doc_path}")
            self.cache.pop(NodeKey(kind="collection", path=coll_path), None)
            self.invalidate(prefix=doc_path)
            self.navigate(segments=parse_path(text=coll_path))

        self.app.run(
            work=lambda: store.delete_document(doc_path=doc_path),
            done=done,
            busy="Deleting document…",
        )

    def clear_document(self, doc_path: str) -> None:
        if not ConfirmDialog(
            parent=self,
            title="Delete document fields",
            text=f"This deletes every field of /{doc_path}. Its subcollections are kept.",
        ).ask():
            return

        store = self.require_store()
        self.app.run(
            work=lambda: store.clear_document(doc_path=doc_path),
            done=lambda _: self.invalidate(
                keys=[NodeKey(kind="document", path=doc_path)]
            ),
            busy="Deleting fields…",
        )

    def set_filter(self, coll_path: str) -> None:
        dialog = FilterDialog(
            parent=self, collection="/" + coll_path, query=self.queries.get(coll_path)
        )
        query = dialog.ask()

        if query is None:
            return

        if query.active:
            self.queries[coll_path] = query
        else:
            self.queries.pop(coll_path, None)

        self.invalidate(keys=[NodeKey(kind="collection", path=coll_path)])

    def clear_filter(self, coll_path: str) -> None:
        self.queries.pop(coll_path, None)
        self.invalidate(keys=[NodeKey(kind="collection", path=coll_path)])

    # ---- fields; nested edits rewrite the whole top-level field

    def write_fields(self, doc_path: str, changes: dict[str, Any]) -> None:
        store = self.require_store()
        self.app.run(
            work=lambda: store.update_fields(doc_path=doc_path, changes=changes),
            done=lambda _: self.invalidate(
                keys=[NodeKey(kind="document", path=doc_path)]
            ),
            busy="Saving…",
        )

    def _warn(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def add_field(self, doc_path: str) -> None:
        result = FieldDialog(parent=self, title="Add a field", ok_text="Add").ask()

        if result is None or result.name is None:
            return

        if result.name in self.doc_data(doc_path=doc_path):
            self._warn(
                title="Add a field", text=f"The field '{result.name}' already exists."
            )

            return

        self.write_fields(doc_path=doc_path, changes={result.name: result.value})

    def add_child(self, doc_path: str, path: KeyPath) -> None:
        data = self.doc_data(doc_path=doc_path)
        parent = values.get_at(data=data, path=path)
        is_map = isinstance(parent, dict)
        result = FieldDialog(
            parent=self,
            title=f"Add to {field_path(path=path)}",
            named=is_map,
            ok_text="Add",
        ).ask()

        if result is None:
            return

        if is_map and result.name in parent:
            self._warn(
                title="Add a field", text=f"The field '{result.name}' already exists."
            )

            return

        if not is_map and values.type_of(value=result.value) == "array":
            self._warn(
                title="Add an item", text="An array cannot directly contain an array."
            )

            return

        key: str | int = (result.name or "") if is_map else len(parent)
        top = values.with_set(
            top=data[path[0]], path=[*path[1:], key], value=result.value
        )
        self.write_fields(doc_path=doc_path, changes={str(path[0]): top})

    def edit_field(self, doc_path: str, path: KeyPath) -> None:
        data = self.doc_data(doc_path=doc_path)
        value = values.get_at(data=data, path=path)
        in_map = len(path) == 1 or isinstance(
            values.get_at(data=data, path=path[:-1]), dict
        )
        result = FieldDialog(
            parent=self,
            title=f"Edit {field_path(path=path)}",
            name=str(path[-1]) if in_map else "",
            value=value,
            named=in_map,
        ).ask()

        if result is None:
            return

        name = result.name or ""
        renamed = in_map and name != path[-1]
        siblings = data if len(path) == 1 else values.get_at(data=data, path=path[:-1])

        if renamed and name in siblings:
            self._warn(title="Edit field", text=f"The field '{name}' already exists.")

            return

        if not in_map and values.type_of(value=result.value) == "array":
            self._warn(
                title="Edit field", text="An array cannot directly contain an array."
            )

            return

        top_name = str(path[0])

        if len(path) == 1:
            changes: dict[str, Any] = {name: result.value}

            if renamed:
                changes[top_name] = DELETE
        elif renamed:
            top = values.with_renamed(
                top=data[top_name], path=path[1:], new_key=name, value=result.value
            )
            changes = {top_name: top}
        else:
            changes = {
                top_name: values.with_set(
                    top=data[top_name], path=path[1:], value=result.value
                )
            }

        self.write_fields(doc_path=doc_path, changes=changes)

    def delete_field(self, doc_path: str, path: KeyPath) -> None:
        if not ask_yes_no(
            parent=self,
            title="Delete field",
            text=f"Delete the field {field_path(path=path)}?",
        ):
            return

        data = self.doc_data(doc_path=doc_path)
        top_name = str(path[0])

        if len(path) == 1:
            changes: dict[str, Any] = {top_name: DELETE}
        else:
            changes = {top_name: values.with_deleted(top=data[top_name], path=path[1:])}

        self.write_fields(doc_path=doc_path, changes=changes)
