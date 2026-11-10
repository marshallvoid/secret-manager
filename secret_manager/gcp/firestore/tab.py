from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...settings import AppSettings
from ..credentials import GoogleAccount
from .browser import Browser
from .paths import parse_path
from .store import OpenedStore, open_store

if TYPE_CHECKING:
    from ...app import App


# Which database is open, to know whether a reconnect can keep the current place
class StoreKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    credentials: str
    database: str


class FirestoreTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.account: GoogleAccount | None = None
        self.opened: StoreKey | None = None
        settings = app.settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Database"))
        self.db_box = QComboBox()
        self.db_box.setEditable(True)
        self.db_box.addItems(settings.databases)
        self.db_box.setCurrentText(settings.database)
        database_edit = self.db_box.lineEdit()
        assert database_edit is not None
        database_edit.setPlaceholderText("(default)")
        self.db_box.setMinimumWidth(220)
        database_edit.returnPressed.connect(self.connect_database)
        bar.addWidget(self.db_box)

        open_button = QPushButton("Open")
        open_button.clicked.connect(self.connect_database)
        bar.addWidget(open_button)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.browser = Browser(app=app)
        layout.addWidget(self.browser, 1)

    def store_settings(self, settings: AppSettings) -> None:
        databases = [self.db_box.itemText(index) for index in range(self.db_box.count())]
        current = self.db_box.currentText().strip()

        if current and current not in databases:
            databases.append(current)

        settings.database = current
        settings.databases = databases[-10:]
        settings.firestore_path = "/".join(self.browser.path)

    def connect_account(self, account: GoogleAccount) -> None:
        self.account = account
        self.connect_database()

    def connect_database(self) -> None:
        account = self.account

        if account is None:
            self.app.status(text="Connect a service account first")

            return

        database = self.db_box.currentText().strip()
        key = StoreKey(credentials=account.path, database=database)
        settings = self.app.settings
        saved = StoreKey(
            credentials=os.path.expanduser(settings.credentials),
            database=settings.database,
        )
        start = parse_path(text=settings.firestore_path) if key == saved else []

        # reconnecting to the same database keeps the current place
        if self.opened == key:
            start = self.browser.path

        def done(opened: OpenedStore) -> None:
            self.opened = key
            self.browser.set_store(store=opened.store, root_ids=opened.root_ids, path=start)
            self.app.status(text=f"Opened Firestore {opened.store.project} / {opened.store.database}")

        self.app.run(
            work=lambda: open_store(account=account, database=database),
            done=done,
            busy="Opening Firestore…",
        )
