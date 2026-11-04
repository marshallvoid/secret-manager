from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ... import theme
from ...dialogs import ConfirmDialog
from ...utils.dates import relative_time
from ...utils.names import env_name
from ...widgets import (
    SEPARATOR,
    MenuItem,
    MessagePage,
    PanelHeader,
    flat_button,
    link_button,
    menu_button,
    muted,
    primary_button,
    search_box,
    separator,
)
from ..credentials import GoogleAccount
from .dialogs import NewSecretDialog, NewVersionDialog, ValueDialog
from .models import SecretInfo, VersionAction, VersionInfo
from .rows import VersionRow
from .store import SecretStore

if TYPE_CHECKING:
    from ...app import App

EMPTY, LOADING, CONTENT = range(3)
ID_ROLE = Qt.ItemDataRole.UserRole
ACTION_TEXTS: dict[str, str] = {
    "disable": "Apps can no longer read it until it is enabled again.",
    "enable": "Apps can read it again.",
    "destroy": "Its value is erased for good. This cannot be undone.",
}


class SecretsTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.store: SecretStore | None = None
        self.secrets: list[SecretInfo] = []
        self.current: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("QSplitter::handle { border: none; }")
        splitter.addWidget(self._list_panel())
        splitter.addWidget(self._detail_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1000])
        layout.addWidget(splitter)

    # ---- layout

    def _list_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Browser")
        frame.setMinimumWidth(240)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("Secret Manager")
        title.setObjectName("PanelTitle")
        header = PanelHeader(icon="shield", title=title)
        refresh = flat_button(icon="refresh", tip="Reload")
        refresh.clicked.connect(lambda _=False: self.reload())
        header.row.addWidget(refresh)
        layout.addWidget(header)

        box = QVBoxLayout()
        box.setContentsMargins(10, 10, 10, 0)
        self.search = search_box(placeholder="Filter secrets")
        self.search.textChanged.connect(lambda _: self.fill())
        box.addWidget(self.search)
        layout.addLayout(box)
        layout.addWidget(link_button(text="Create secret", action=self.create_secret))

        self.list = QListWidget()
        self.list.setObjectName("Items")
        self.list.setItemDelegate(theme.ChevronDelegate(parent=self.list))
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.itemClicked.connect(
            lambda item: self.open_secret(secret_id=item.data(ID_ROLE))
        )
        layout.addWidget(self.list, 1)

        self.note = QLabel("Not connected")
        self.note.setObjectName("Note")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        return frame

    def _detail_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Browser")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title = QLabel("")
        self.title.setObjectName("RepoTitle")
        self.header = PanelHeader(icon="key", title=self.title, height=64)
        items = [
            MenuItem(text="Copy resource name", action=self.copy_resource_name),
            MenuItem(
                text="Refresh",
                action=lambda: self.open_secret(secret_id=self.current or ""),
            ),
            SEPARATOR,
            MenuItem(text="Delete secret", action=self.delete_secret),
        ]
        self.header.row.addWidget(menu_button(parent=self, items=items))
        layout.addWidget(self.header)

        self.info = muted(text="")
        self.info.setContentsMargins(16, 12, 16, 0)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 12, 16, 10)
        heading = QLabel("Versions")
        heading.setObjectName("PanelTitle")
        toolbar.addWidget(heading)
        toolbar.addStretch(1)
        self.new_version = primary_button(text="New version", action=self.add_version)
        toolbar.addWidget(self.new_version)
        layout.addLayout(toolbar)
        layout.addWidget(separator())

        self.stack = QStackedWidget()
        self.empty = MessagePage(
            icon="shield",
            title="Not connected",
            text="Choose a service account file above and press Connect.",
        )
        self.stack.addWidget(self.empty)
        self.loading = MessagePage(icon="refresh", title="Loading…")
        self.stack.addWidget(self.loading)
        self.versions = QListWidget()
        self.versions.setObjectName("Secrets")
        self.versions.setFrameShape(QFrame.Shape.NoFrame)
        self.stack.addWidget(self.versions)
        layout.addWidget(self.stack, 1)

        footer = muted(
            text="Viewing a value needs the Secret Manager Secret Accessor role. "
            "A destroyed version cannot be restored."
        )
        footer.setContentsMargins(16, 8, 16, 10)
        layout.addWidget(footer)
        self._show_detail(visible=False)

        return frame

    def _show_detail(self, visible: bool) -> None:
        self.header.setVisible(visible)
        self.info.setVisible(visible)
        self.new_version.setEnabled(visible)

    # ---- secrets

    def connect_account(self, account: GoogleAccount) -> None:
        self.store = SecretStore(account=account)
        self.current = None
        self.reload()

    def reload(self) -> None:
        store = self.store

        if store is None:
            return

        self.note.setText("Loading secrets…")
        self.note.show()

        def done(secrets: list[SecretInfo]) -> None:
            self.secrets = secrets
            self.fill()

            if self.current and self.secret(secret_id=self.current) is not None:
                self.open_secret(secret_id=self.current)

                return

            self.current = None
            self._show_detail(visible=False)
            self.empty.show_text(
                title="Choose a secret",
                text=f"{len(secrets)} secret(s) in {store.project}.",
            )
            self.stack.setCurrentIndex(EMPTY)

        def failed(exc: Exception) -> None:
            self.note.setText(f"Could not list secrets: {str(exc).splitlines()[0]}")

        self.app.run(
            work=store.list_secrets, done=done, busy="Loading secrets…", failed=failed
        )

    def fill(self) -> None:
        text = self.search.text().strip().lower()
        shown = [secret for secret in self.secrets if text in secret.id.lower()]
        self.list.clear()

        for secret in shown:
            item = QListWidgetItem(secret.id, self.list)
            item.setData(ID_ROLE, secret.id)

            if secret.id == self.current:
                self.list.setCurrentItem(item)

        if shown:
            self.note.hide()
        else:
            self.note.setText("No secret matches." if text else "No secrets yet.")
            self.note.show()

    def secret(self, secret_id: str) -> SecretInfo | None:
        return next((secret for secret in self.secrets if secret.id == secret_id), None)

    def open_secret(self, secret_id: str) -> None:
        store = self.store
        info = self.secret(secret_id=secret_id)

        if store is None or info is None:
            return

        self.current = secret_id
        self.fill()
        self.title.setText(secret_id)
        labels = "  ·  ".join(f"{key}={value}" for key, value in info.labels.items())
        parts = [
            f"Replication: {info.replication}",
            relative_time(value=info.created, prefix="Created"),
            labels,
        ]
        self.info.setText("  ·  ".join(part for part in parts if part))
        self._show_detail(visible=True)
        self.loading.show_text(title="Loading versions…")
        self.stack.setCurrentIndex(LOADING)

        def done(versions: list[VersionInfo]) -> None:
            if self.current == secret_id:
                self.paint_versions(secret_id=secret_id, versions=versions)

        def failed(exc: Exception) -> None:
            self.loading.show_text(title="Could not load versions", text=str(exc))

        self.app.run(
            work=lambda: store.list_versions(secret_id=secret_id),
            done=done,
            busy="Loading versions…",
            failed=failed,
        )

    def paint_versions(self, secret_id: str, versions: list[VersionInfo]) -> None:
        self.versions.clear()

        if not versions:
            self.empty.show_text(
                title="No versions yet",
                text="Add a version to give this secret a value.",
            )
            self.stack.setCurrentIndex(EMPTY)

            return

        for index, version in enumerate(versions):
            number = version.number
            item = QListWidgetItem(self.versions)
            row = VersionRow(
                version=version,
                latest=index == 0,
                on_view=lambda number=number: self.view(
                    secret_id=secret_id, version=number
                ),
                on_change=lambda action, number=number: self.change(
                    secret_id=secret_id,
                    version=number,
                    action=action,
                ),
            )
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            self.versions.setItemWidget(item, row)

        self.stack.setCurrentIndex(CONTENT)

    def create_secret(self) -> None:
        store = self.store

        if store is None:
            self.app.status(text="Connect first")

            return

        result = NewSecretDialog(parent=self).ask()

        if result is None:
            return

        def done(_: None) -> None:
            self.current = result.secret_id
            self.reload()

        self.app.run(
            work=lambda: store.create_secret(secret=result),
            done=done,
            busy="Creating the secret…",
        )

    def add_version(self) -> None:
        store, secret_id = self.store, self.current

        if store is None or secret_id is None:
            return

        value = NewVersionDialog(parent=self, secret_id=secret_id).ask()

        if value is None:
            return

        self.app.run(
            work=lambda: store.add_version(secret_id=secret_id, value=value),
            done=lambda _: self.open_secret(secret_id=secret_id),
            busy="Adding a version…",
        )

    def view(self, secret_id: str, version: str) -> None:
        store = self.store

        if store is None:
            return

        def push(text: str) -> None:
            self.app.github.push_secret(
                parent=self, name=env_name(text=secret_id), value=text
            )

        def done(data: bytes) -> None:
            ValueDialog(
                parent=self,
                title=f"{secret_id} · version {version}",
                data=data,
                on_push=push,
            ).ask()

        self.app.run(
            work=lambda: store.access(secret_id=secret_id, version=version),
            done=done,
            busy="Reading the value…",
        )

    def change(self, secret_id: str, version: str, action: VersionAction) -> None:
        store = self.store

        if store is None:
            return

        verb = action.title()

        if not ConfirmDialog(
            parent=self,
            title=f"{verb} version {version}",
            text=f"{verb} version {version} of {secret_id}? {ACTION_TEXTS[action]}",
            ok_text=verb,
        ).ask():
            return

        self.app.run(
            work=lambda: store.change_version(
                secret_id=secret_id, version=version, action=action
            ),
            done=lambda _: self.open_secret(secret_id=secret_id),
            busy=f"{verb}…",
        )

    def delete_secret(self) -> None:
        store, secret_id = self.store, self.current

        if store is None or secret_id is None:
            return

        if not ConfirmDialog(
            parent=self,
            title="Delete secret",
            text=f"This deletes {secret_id} and every version of it. This cannot be undone.",
            confirm=secret_id,
        ).ask():
            return

        def done(_: None) -> None:
            self.current = None
            self.reload()

        self.app.run(
            work=lambda: store.delete_secret(secret_id=secret_id),
            done=done,
            busy="Deleting the secret…",
        )

    def copy_resource_name(self) -> None:
        if self.store is not None and self.current:
            QGuiApplication.clipboard().setText(
                f"{self.store.parent}/secrets/{self.current}"
            )
            self.app.status(text="Copied the resource name")
