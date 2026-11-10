from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from .. import theme
from ..dialogs import Dialog
from ..widgets import muted, read_text_file, search_box
from .models import VISIBILITY_LABELS, Access, EntryKind, EntryResult, OwnerKind

NAME_HINT = "Letters, digits and _ only; names are stored in upper case."


class EntryDialog(Dialog[EntryResult]):
    def __init__(
        self,
        parent: QWidget,
        title: str,
        kind: EntryKind,
        check_name: Callable[[str], str | None],
        name: str = "",
        value: str = "",
        fixed_name: bool = False,
        owner: OwnerKind | None = None,
        access: Access | None = None,
        repo_choices: list[str] | None = None,
    ) -> None:
        super().__init__(parent=parent, title=title, ok_text="Save", width=680)
        self.kind = kind
        self.check_name = check_name
        self.owner = owner

        self.content.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(name.upper())
        self.name_edit.setEnabled(not fixed_name)
        self.name_edit.setPlaceholderText("MY_SECRET" if kind == "secret" else "MY_VARIABLE")
        self.name_edit.textEdited.connect(self._upper)
        self.name_edit.textChanged.connect(self._check_live)
        self.content.addWidget(self.name_edit)

        self.problem = muted(text=NAME_HINT)
        self.problem.setWordWrap(True)
        self.content.addWidget(self.problem)

        row = QHBoxLayout()
        row.addWidget(QLabel("Value"))
        row.addStretch(1)
        load = QPushButton("Load from file…")
        load.clicked.connect(self._load)
        row.addWidget(load)
        self.content.addLayout(row)

        self.text = QPlainTextEdit(value)
        self.text.setMinimumHeight(140)
        self.content.addWidget(self.text, 1)

        self.visibility: QComboBox | None = None
        self.repos: QListWidget | None = None
        self.repo_filter: QLineEdit | None = None

        if owner in ("org", "user"):
            self._access_section(
                owner=owner,
                access=access or Access(),
                choices=repo_choices or [],
            )

        (self.text if fixed_name else self.name_edit).setFocus()

    def _access_section(self, owner: OwnerKind, access: Access, choices: list[str]) -> None:
        self.content.addSpacing(6)
        self.content.addWidget(QLabel("Repository access"))

        if owner == "org":
            self.visibility = QComboBox()

            for key, label in VISIBILITY_LABELS.items():
                self.visibility.addItem(label, key)

            self.visibility.setCurrentIndex(list(VISIBILITY_LABELS).index(access.visibility))
            self.visibility.currentIndexChanged.connect(lambda _: self._sync_repos())
            self.content.addWidget(self.visibility)

        self.repo_filter = search_box(placeholder="Filter repositories")
        self.repo_filter.textChanged.connect(self._filter_repos)
        self.content.addWidget(self.repo_filter)

        self.repos = QListWidget()
        self.repos.setMinimumHeight(150)

        for full_name in sorted(set(choices) | set(access.repos), key=str.lower):
            item = QListWidgetItem(full_name, self.repos)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = full_name in access.repos
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

        self.content.addWidget(self.repos)
        self._sync_repos()

    def _sync_repos(self) -> None:
        selected = self.visibility is None or self.visibility.currentData() == "selected"

        if self.repo_filter is not None:
            self.repo_filter.setVisible(selected)

        if self.repos is not None:
            self.repos.setVisible(selected)

    def _filter_repos(self, text: str) -> None:
        if self.repos is None:
            return

        for index in range(self.repos.count()):
            item = self.repos.item(index)
            item.setHidden(text.lower() not in item.text().lower())

    def _upper(self, text: str) -> None:
        cursor = self.name_edit.cursorPosition()
        self.name_edit.setText(text.upper())
        self.name_edit.setCursorPosition(cursor)

    def _check_live(self, text: str) -> None:
        problem = self.check_name(text.strip()) if text.strip() else None
        self.problem.setText(problem or NAME_HINT)
        self.problem.setStyleSheet(f"color: {theme.DANGER};" if problem else "")

    def _load(self) -> None:
        content = read_text_file(parent=self)

        if content is not None:
            self.text.setPlainText(content)

    def _access(self) -> Access | None:
        if self.repos is None:
            return None

        items = [self.repos.item(index) for index in range(self.repos.count())]
        checked = [item.text() for item in items if item.checkState() == Qt.CheckState.Checked]

        if self.visibility is None:
            return Access(visibility="selected", repos=checked)

        visibility = self.visibility.currentData()

        if visibility == "selected" and not checked:
            raise ValueError("Choose at least one repository, or another access level.")

        repos = checked if visibility == "selected" else []

        return Access(visibility=visibility, repos=repos)

    def build(self) -> EntryResult:
        name = self.name_edit.text().strip().upper()
        value = self.text.toPlainText()
        problem = self.check_name(name)

        if problem is None and not value:
            problem = "Value is empty."

        if problem:
            raise ValueError(problem)

        return EntryResult(name=name, value=value, access=self._access())

    def ask(self) -> EntryResult | None:
        return super().ask()
