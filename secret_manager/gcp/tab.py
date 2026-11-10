from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..settings import AppSettings
from ..widgets import muted
from .credentials import GoogleAccount, load_account
from .firestore.tab import FirestoreTab
from .remote_config.tab import RemoteConfigTab
from .secret_manager.tab import SecretsTab

if TYPE_CHECKING:
    from ..app import App


# One service account file shared by Firestore, Secret Manager and Remote Config
class GoogleTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.account: GoogleAccount | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 20)
        layout.setSpacing(16)

        connection = QFrame()
        connection.setObjectName("ConnectionCard")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(16, 12, 16, 12)
        connection_layout.setSpacing(8)
        bar = QHBoxLayout()
        bar.setSpacing(12)
        credential_label = QLabel("Service account")
        bar.addWidget(credential_label)
        self.cred_edit = QLineEdit(app.settings.credentials)
        self.cred_edit.setAccessibleName("Service account file path")
        credential_label.setBuddy(self.cred_edit)
        self.cred_edit.setPlaceholderText("Path to a service account JSON file")
        self.cred_edit.returnPressed.connect(self.connect_service_account)
        bar.addWidget(self.cred_edit, 1)

        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        bar.addWidget(browse)

        connect = QPushButton("Connect")
        connect.setObjectName("Primary")
        connect.clicked.connect(self.connect_service_account)
        bar.addWidget(connect)
        connection_layout.addLayout(bar)

        self.account_label = muted(text="Not connected · Choose a service account to get started.")
        self.account_label.setWordWrap(True)
        connection_layout.addWidget(self.account_label)
        layout.addWidget(connection)

        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Google Cloud services")
        self.firestore = FirestoreTab(app=app)
        self.secrets = SecretsTab(app=app)
        self.remote_config = RemoteConfigTab(app=app)
        self.tabs.addTab(self.firestore, theme.named_icon(key="database"), "Firestore")
        self.tabs.addTab(self.secrets, theme.named_icon(key="shield"), "Secret Manager")
        self.tabs.addTab(self.remote_config, theme.named_icon(key="tune"), "Remote Config")
        self.tabs.setCurrentIndex(app.settings.google_tab)
        self.tabs.currentChanged.connect(lambda _: app.save_settings())
        layout.addWidget(self.tabs, 1)

    def store_settings(self, settings: AppSettings) -> None:
        settings.credentials = self.cred_edit.text().strip()
        settings.google_tab = self.tabs.currentIndex()
        self.firestore.store_settings(settings=settings)

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Service account credentials",
            os.path.dirname(self.cred_edit.text()),
            "JSON (*.json);;All files (*)",
        )

        if path:
            self.cred_edit.setText(path)
            self.connect_service_account()

    def connect_service_account(self) -> None:
        path = os.path.expanduser(self.cred_edit.text().strip())

        if not os.path.isfile(path):
            QMessageBox.warning(self, "Credentials", "Choose a service account JSON file.")

            return

        def done(account: GoogleAccount) -> None:
            self.account = account
            self.account_label.setText(f"Project {account.project}  ·  {account.email}")
            self.firestore.connect_account(account=account)
            self.secrets.connect_account(account=account)
            self.remote_config.connect_account(account=account)
            self.app.save_settings()

        self.app.run(work=lambda: load_account(path=path), done=done, busy="Reading credentials…")
