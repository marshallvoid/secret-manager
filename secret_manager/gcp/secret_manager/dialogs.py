from __future__ import annotations

import base64
import re
from collections.abc import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import theme
from ...clipboard import CLEAR_SECONDS, copy_secret
from ...dialogs import Dialog
from ...widgets import muted, read_text_file
from .models import NewSecret
from .store import check_id

LABEL_RE = re.compile(pattern=r"[a-z][a-z0-9_-]{0,62}")
ID_HINT = "Letters, digits, - and _; at most 255 characters."


def parse_labels(text: str) -> dict[str, str]:
    labels: dict[str, str] = {}

    for part in filter(None, (piece.strip() for piece in text.split(","))):
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()

        if not LABEL_RE.fullmatch(key):
            raise ValueError(
                f"Label key '{key}' must start with a lowercase letter and use a-z, 0-9, - or _."
            )

        labels[key] = value

    return labels


class ValueInput(QWidget):
    def __init__(self, value: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        row.addWidget(QLabel("Value"))
        row.addStretch(1)
        load = QPushButton("Load from file…")
        load.clicked.connect(self._load)
        row.addWidget(load)
        layout.addLayout(row)

        self.text = QPlainTextEdit(value)
        self.text.setMinimumHeight(160)
        self.text.setStyleSheet(f"font-family: {theme.MONO};")
        layout.addWidget(self.text, 1)

    def _load(self) -> None:
        content = read_text_file(parent=self)

        if content is not None:
            self.text.setPlainText(content)

    def value(self) -> str:
        return self.text.toPlainText()


class NewSecretDialog(Dialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(
            parent=parent, title="Create a secret", ok_text="Create", width=680
        )
        self.content.addWidget(QLabel("Name"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("my-secret")
        self.id_edit.textChanged.connect(self._check_live)
        self.content.addWidget(self.id_edit)
        self.problem = muted(text=ID_HINT)
        self.content.addWidget(self.problem)

        self.input = ValueInput()
        self.content.addWidget(self.input, 1)
        self.content.addWidget(
            muted(text="Leave the value empty to create the secret without a version.")
        )

        self.content.addWidget(QLabel("Labels"))
        self.labels = QLineEdit()
        self.labels.setPlaceholderText("env=prod, team=backend")
        self.content.addWidget(self.labels)
        self.id_edit.setFocus()

    def _check_live(self, text: str) -> None:
        problem = check_id(secret_id=text.strip()) if text.strip() else None
        self.problem.setText(problem or ID_HINT)
        self.problem.setStyleSheet(f"color: {theme.DANGER};" if problem else "")

    def build(self) -> NewSecret:
        secret_id = self.id_edit.text().strip()
        problem = check_id(secret_id=secret_id)

        if problem:
            raise ValueError(problem)

        return NewSecret(
            secret_id=secret_id,
            value=self.input.value(),
            labels=parse_labels(text=self.labels.text()),
        )

    def ask(self) -> NewSecret | None:
        return super().ask()


class NewVersionDialog(Dialog):
    def __init__(self, parent: QWidget, secret_id: str) -> None:
        super().__init__(
            parent=parent,
            title=f"New version of {secret_id}",
            ok_text="Add version",
            width=640,
        )
        self.input = ValueInput()
        self.content.addWidget(self.input, 1)
        self.content.addWidget(
            muted(text="The new version becomes latest; older versions stay enabled.")
        )
        self.input.text.setFocus()

    def build(self) -> str:
        value = self.input.value()

        if not value:
            raise ValueError("Value is empty.")

        return value

    def ask(self) -> str | None:
        return super().ask()


class ValueDialog(Dialog):
    def __init__(
        self,
        parent: QWidget,
        title: str,
        data: bytes,
        on_push: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent=parent, title=title, ok_text="Close", width=680)
        self.resize(680, 420)

        try:
            text = data.decode("utf-8")
            note = f"{len(data)} bytes"
        except UnicodeDecodeError:
            text = base64.b64encode(data).decode("ascii")
            note = f"{len(data)} bytes of binary data, shown as base64"
            on_push = None

        self.view = QPlainTextEdit(text)
        self.view.setReadOnly(True)
        self.view.setStyleSheet(f"font-family: {theme.MONO};")
        self.content.addWidget(self.view, 1)
        self.content.addWidget(muted(text=note))

        copy = QPushButton("Copy")
        copy.setToolTip(f"The clipboard clears again after {CLEAR_SECONDS} seconds")
        copy.clicked.connect(lambda _=False: copy_secret(text=text))
        self.buttons.insertWidget(0, copy)

        if on_push is not None:
            push_to = on_push
            push = QPushButton("Set as GitHub secret…")
            push.clicked.connect(lambda _=False: push_to(text))
            self.buttons.insertWidget(1, push)

    def build(self) -> bool:
        return True
