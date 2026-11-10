from __future__ import annotations

import os

from google.cloud import firestore, secretmanager
from PySide6.QtWidgets import QApplication

from . import theme
from .widgets import MessagePage


def main() -> None:
    """Check packaged Qt and cloud imports without loading settings or credentials."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    theme.apply(app=app)
    page = MessagePage(icon="shield", title="Portable smoke test")
    page.show()
    app.processEvents()

    for client in (firestore.Client, secretmanager.SecretManagerServiceClient):
        if not callable(client):
            raise RuntimeError("Cloud libraries are missing")

    page.close()
    print("Portable smoke test passed.")
