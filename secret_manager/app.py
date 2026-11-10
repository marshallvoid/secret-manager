from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from . import settings, theme
from .gcp.tab import GoogleTab
from .github.tab import GitHubTab
from .settings import AppSettings
from .workspace import WorkspaceHeader


class Job(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    work: Callable[[], Any]
    done: Callable[[Any], None] | None = None
    failed: Callable[[Exception], None] | None = None
    busy: str = "Working…"


class Outcome(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    job: Job
    ok: bool
    result: Any = None


# Work runs on a plain thread; the signal brings the outcome back to the GUI thread
class Runner(QObject):
    finished = Signal(object)

    def run(self, job: Job) -> None:
        def target() -> None:
            try:
                outcome = Outcome(job=job, ok=True, result=job.work())
            except Exception as exc:
                outcome = Outcome(job=job, ok=False, result=exc)

            self.finished.emit(outcome)

        threading.Thread(target=target, daemon=True).start()


class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Secret Manager")
        self.resize(1280, 760)
        self.settings: AppSettings = settings.load()
        self.runner = Runner()
        self.runner.finished.connect(self._finished)
        self.pending = 0
        self.busy_text = ""
        self.tabs: QTabWidget | None = None

        tabs = QTabWidget()
        tabs.setObjectName("Providers")
        tabs.setDocumentMode(True)
        tabs.setAccessibleName("Cloud providers")
        self.google = GoogleTab(app=self)
        self.github = GitHubTab(app=self)
        tabs.addTab(self.google, theme.named_icon(key="database"), "Google Cloud")
        tabs.addTab(self.github, theme.named_icon(key="repo"), "GitHub")
        tabs.setCurrentIndex(self.settings.tab)
        tabs.currentChanged.connect(lambda _: self.save_settings())
        self.tabs = tabs
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(WorkspaceHeader())
        layout.addWidget(tabs, 1)
        self.setCentralWidget(workspace)
        self.status(text="Ready")

        if self.google.cred_edit.text():
            QTimer.singleShot(0, self.google.connect_service_account)

    def status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def error(self, exc: Exception) -> None:
        text = str(exc) or type(exc).__name__
        self.status(text=f"Error: {text.splitlines()[0]}")
        QMessageBox.critical(self, "Error", text)

    def run(
        self,
        work: Callable[[], Any],
        done: Callable[[Any], None] | None = None,
        busy: str = "Working…",
        failed: Callable[[Exception], None] | None = None,
    ) -> None:
        self.pending += 1
        self.status(text=busy)
        self.busy_text = busy
        self.runner.run(job=Job(work=work, done=done, failed=failed, busy=busy))

    def _finished(self, outcome: Outcome) -> None:
        self.pending -= 1
        job = outcome.job

        # clear a busy message that no callback replaced
        if self.pending == 0 and self.statusBar().currentMessage() == self.busy_text:
            self.status(text="Ready")

        try:
            if outcome.ok:
                if job.done is not None:
                    job.done(outcome.result)
            elif job.failed is not None:
                job.failed(outcome.result)
                message = str(outcome.result) or type(outcome.result).__name__
                self.status(text=f"Error: {message.splitlines()[0]}")
            else:
                self.error(exc=outcome.result)
        except Exception as exc:
            self.error(exc=exc)

    def save_settings(self) -> None:
        # tabs call this while the window is still being built
        if self.tabs is None:
            return

        self.github.store_settings(settings=self.settings)
        self.google.store_settings(settings=self.settings)
        self.settings.tab = self.tabs.currentIndex()

        try:
            settings.save(settings=self.settings)
        except OSError as exc:
            self.status(text=f"Cannot save settings: {exc}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_settings()
        super().closeEvent(event)
