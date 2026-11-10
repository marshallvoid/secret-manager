from __future__ import annotations

import os
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, List

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..clipboard import copy_secret
from ..dialogs import ConfirmDialog
from ..settings import AppSettings
from ..widgets import (
    MessagePage,
    chip,
    discard,
    flat_button,
    icon_label,
    muted,
    primary_button,
    search_box,
    separator,
)
from . import cli
from .dialogs import EntryDialog
from .envfile import env_names
from .models import Access, AppName, Entry, EntryKind, EntryResult, Owner, Repo, Scope, Target
from .rows import EntryRow
from .secret_index import RepoSecretStatus, inspect_repositories
from .sidebar import OWNER_ICONS, Directory, Sidebar, repo_owner

if TYPE_CHECKING:
    from ..app import App

PLACEHOLDER, LOADING, LIST, EMPTY = range(4)
NAME_ROLE = Qt.ItemDataRole.UserRole
SECRET_NOTE = "GitHub never shows a secret value again after it is saved; you can only replace or delete it."
VARIABLE_NOTE = "Variables are plain configuration values: anyone who can run workflows can read them."
KIND_LABELS: dict[EntryKind, str] = {"secret": "Secrets", "variable": "Variables"}
SHORTCUTS = "Ctrl+N new · F5 refresh · Del delete · Ctrl+F search"


def load_directory() -> Directory:
    orgs: dict[str, list[Repo]] = {}

    for org in cli.list_orgs():
        try:
            orgs[org] = cli.list_repos(owner=org)
        except cli.GhError:
            orgs[org] = []

    return Directory(repos=cli.list_repos(), orgs=orgs)


def scopes_for(owner: Owner, kind: EntryKind, environments: list[str]) -> list[Scope]:
    if owner.kind == "user":
        return [Scope(key="codespaces", label="Codespaces")]

    first = "Repository" if owner.kind == "repo" else "Actions"
    scopes = [Scope(key="actions", label=first)]

    if owner.kind == "repo":
        scopes += [Scope(key=f"env:{env}", label=f"Environment · {env}") for env in environments]

    # variables only exist for Actions
    if kind == "secret":
        scopes += [
            Scope(key="dependabot", label="Dependabot"),
            Scope(key="codespaces", label="Codespaces"),
        ]

    return scopes


def page_url(target: Target) -> str:
    plural = "secrets" if target.kind == "secret" else "variables"

    if target.owner == "user":
        return "https://github.com/settings/codespaces"

    if target.owner == "org":
        return f"https://github.com/organizations/{target.name}/settings/{plural}/{target.app}"

    if target.environment:
        return f"https://github.com/{target.name}/settings/environments"

    return f"https://github.com/{target.name}/settings/{plural}/{target.app}"


def saved_owner(settings: AppSettings) -> Owner | None:
    if settings.github_owner is not None:
        return settings.github_owner

    # settings written before organizations were supported
    if settings.repo:
        return repo_owner(full_name=settings.repo)

    return None


class GitHubTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.directory = Directory()
        self.environments: list[str] = []
        self.entries: list[Entry] = []
        self.owner = saved_owner(settings=app.settings)
        self.kind: EntryKind = app.settings.github_kind
        self.scope = app.settings.github_scope
        self.directory_generation = 0
        self.secret_index_loading = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 20)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("QSplitter::handle { border: none; }")
        self.sidebar = Sidebar(
            on_select=self.open_owner,
            on_reload=self.load_directory,
            on_filter=self._filter_repositories,
            on_change=self.app.save_settings,
        )
        self.sidebar.restore_state(
            repo_filter=app.settings.github_repo_filter,
            search=app.settings.github_repo_search,
            collapsed=app.settings.github_collapsed_sections,
        )
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self._main())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1000])
        layout.addWidget(splitter)

        self._shortcut(keys=QKeySequence.StandardKey.New, action=self.new_entry)
        self._shortcut(keys=QKeySequence.StandardKey.Refresh, action=self.refresh)
        self._shortcut(keys=QKeySequence.StandardKey.Find, action=self.search.setFocus)
        self._shortcut(
            keys=QKeySequence.StandardKey.Delete,
            action=lambda: self.delete(names=self.selected_names()),
        )

        self.show_header()
        self.rebuild_chips()
        QTimer.singleShot(0, self.load_directory)

        if self.owner is not None:
            owner = self.owner
            QTimer.singleShot(0, lambda: self.open_owner(owner=owner, keep_scope=True))

    def _shortcut(self, keys: QKeySequence.StandardKey, action: Callable[[], None]) -> None:
        shortcut = QShortcut(keys, self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(action)

    # ---- layout

    def _main(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Browser")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header())
        layout.addLayout(self._chip_row())
        layout.addLayout(self._toolbar())
        layout.addWidget(separator())

        self.stack = QStackedWidget()
        self.placeholder = MessagePage(
            icon="repo",
            title="Choose a repository",
            text="Pick a repository, an organization or Codespaces on the left, "
            "or type owner/name in the filter box and press Enter.",
        )
        self.stack.addWidget(self.placeholder)
        self.loading = MessagePage(icon="refresh", title="Loading…")
        self.stack.addWidget(self.loading)

        self.list = QListWidget()
        self.list.setObjectName("Secrets")
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(lambda item: self.edit(name=item.data(NAME_ROLE)))
        self.stack.addWidget(self.list)

        self.empty = MessagePage(
            icon="key",
            title="",
            action_text="Create one",
            action=self.new_entry,
        )
        self.stack.addWidget(self.empty)
        layout.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 10)
        footer.setSpacing(8)
        footer.addWidget(icon_label(key="lock", size=16))
        self.footer = muted(text="")
        self.footer.setWordWrap(True)
        footer.addWidget(self.footer, 1)
        layout.addLayout(footer)

        return frame

    def _header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("PanelHeader")
        header.setFixedHeight(64)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 4, 8, 4)

        self.title_icon = QLabel()
        layout.addWidget(self.title_icon)
        self.title = QLabel()
        self.title.setObjectName("RepoTitle")
        layout.addWidget(self.title, 1)

        self.open_button = flat_button(icon="open", tip="Open this page on GitHub")
        self.open_button.clicked.connect(self.open_on_github)
        layout.addWidget(self.open_button)

        return header

    def _chip_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(16, 14, 16, 0)
        row.setSpacing(8)
        self.kind_chips = QHBoxLayout()
        self.kind_chips.setSpacing(8)
        row.addLayout(self.kind_chips)
        self.scope_label = muted(text="   Scope")
        row.addWidget(self.scope_label)
        self.scope_chips = QHBoxLayout()
        self.scope_chips.setSpacing(8)
        row.addLayout(self.scope_chips)
        row.addStretch(1)

        return row

    def _toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 14, 16, 10)
        toolbar.setSpacing(8)

        self.search = search_box(placeholder="Search")
        self.search.setMaximumWidth(380)
        self.search.textChanged.connect(lambda _: self.paint())
        toolbar.addWidget(self.search, 1)

        self.count = QLabel("0")
        self.count.setObjectName("Count")
        toolbar.addWidget(self.count)
        toolbar.addStretch(1)

        self.import_button = QPushButton("  Import .env")
        self.import_button.setIcon(theme.named_icon(key="upload", color=theme.TEXT))
        self.import_button.clicked.connect(self.import_env)
        toolbar.addWidget(self.import_button)

        self.new_button = primary_button(text="New secret", action=self.new_entry)
        toolbar.addWidget(self.new_button)

        return toolbar

    # ---- state

    def store_settings(self, settings: AppSettings) -> None:
        settings.github_owner = self.owner
        settings.github_kind = self.kind
        settings.github_scope = self.scope
        settings.github_repo_filter = self.sidebar.secret_filter.currentData()
        settings.github_repo_search = self.sidebar.search.text()
        settings.github_collapsed_sections = sorted(self.sidebar.collapsed)
        settings.repo = ""

    def target(self, quiet: bool = False) -> Target | None:
        if self.owner is None:
            if not quiet:
                QMessageBox.warning(self, "GitHub", "Choose a repository or organization first.")

            return None

        environment = self.scope[4:] if self.scope.startswith("env:") else ""
        app: AppName = "actions"

        if self.scope == "dependabot":
            app = "dependabot"
        elif self.scope == "codespaces":
            app = "codespaces"

        return Target(
            owner=self.owner.kind,
            name=self.owner.name,
            kind=self.kind,
            app=app,
            environment=environment,
        )

    def show_header(self) -> None:
        owner = self.owner
        icon = OWNER_ICONS[owner.kind] if owner else "repo"
        self.title_icon.setPixmap(theme.named_icon(key=icon).pixmap(24, 24))
        self.title.setText(owner.label if owner else "GitHub")
        self.title.setToolTip(owner.name if owner else "")
        self.open_button.setEnabled(owner is not None)

        noun = "secret" if self.kind == "secret" else "variable"
        note = SECRET_NOTE if self.kind == "secret" else VARIABLE_NOTE
        self.new_button.setText(f"  New {noun}")
        self.import_button.setToolTip(f"Set every variable of a .env file as a {noun}")
        self.search.setPlaceholderText(f"Search {noun}s")
        self.footer.setText(f"{note}  {SHORTCUTS}")

    def _clear_chips(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None

            if widget is not None:
                discard(widget=widget)

    def _add_chip(
        self,
        layout: QHBoxLayout,
        text: str,
        checked: bool,
        on_click: Callable[[], None],
    ) -> QToolButton:
        button = chip(text=text)
        button.setChecked(checked)
        button.clicked.connect(lambda _=False: on_click())
        layout.addWidget(button)

        return button

    def rebuild_chips(self) -> None:
        self._clear_chips(layout=self.kind_chips)
        self._clear_chips(layout=self.scope_chips)

        if self.owner is None:
            self.scope_label.hide()

            return

        if self.owner.kind != "user":
            for kind, text in KIND_LABELS.items():
                self._add_chip(
                    layout=self.kind_chips,
                    text=text,
                    checked=kind == self.kind,
                    on_click=partial(self.set_kind, kind=kind),
                )

        scopes = scopes_for(owner=self.owner, kind=self.kind, environments=self.environments)

        if self.scope not in [scope.key for scope in scopes]:
            self.scope = scopes[0].key

        self.scope_label.setVisible(len(scopes) > 1)

        if len(scopes) > 1:
            for scope in scopes:
                self._add_chip(
                    layout=self.scope_chips,
                    text=scope.label,
                    checked=scope.key == self.scope,
                    on_click=partial(self.set_scope, key=scope.key),
                )

    def set_kind(self, kind: EntryKind) -> None:
        if kind != self.kind:
            self.kind = kind
            self.entries = []
            self.show_header()

        self.rebuild_chips()
        self.app.save_settings()
        self.refresh()

    def set_scope(self, key: str) -> None:
        self.scope = key
        self.rebuild_chips()
        self.app.save_settings()
        self.refresh()

    # ---- repositories and organizations

    def load_directory(self) -> None:
        self.directory_generation += 1
        generation = self.directory_generation
        self.secret_index_loading = False
        self.sidebar.set_secret_statuses(statuses=[])
        self.sidebar.show_note(text="Loading repositories…")

        def done(directory: Directory) -> None:

            if generation != self.directory_generation:
                return

            self.directory = directory
            self.sidebar.set_directory(directory=directory)
            self._filter_repositories()

        def failed(exc: Exception) -> None:

            if generation != self.directory_generation:
                return

            self.sidebar.show_note(text=f"Could not list repositories: {exc}")

        self.app.run(work=load_directory, done=done, busy="Loading repositories…", failed=failed)

    def _filter_repositories(self) -> None:

        if self.sidebar.secret_filter.currentData() == "all" or self.secret_index_loading:
            return

        names = [name for name in self.sidebar.repository_names() if name not in self.sidebar.secret_statuses]

        if not names:
            return

        generation = self.directory_generation
        self.secret_index_loading = True
        self.sidebar.set_secret_statuses(statuses=list(self.sidebar.secret_statuses.values()), checking=True)

        def done(statuses: List[RepoSecretStatus]) -> None:

            if generation != self.directory_generation:
                return

            combined = dict(self.sidebar.secret_statuses)

            for status in statuses:
                combined.setdefault(status.name, status)

            self.secret_index_loading = False
            self.sidebar.set_secret_statuses(statuses=list(combined.values()))
            self._filter_repositories()

        def failed(exc: Exception) -> None:

            if generation != self.directory_generation:
                return

            self.secret_index_loading = False
            self.sidebar.set_secret_statuses(
                statuses=[
                    *self.sidebar.secret_statuses.values(),
                    *(RepoSecretStatus(name=name, error=str(exc)) for name in names),
                ]
            )

        self.app.run(
            work=lambda: inspect_repositories(names=names),
            done=done,
            failed=failed,
            busy="Checking repository Actions secrets…",
        )

    def open_owner(self, owner: Owner, keep_scope: bool = False) -> None:
        self.owner = owner

        if owner.kind == "user":
            self.kind = "secret"

        if not keep_scope:
            self.scope = "codespaces" if owner.kind == "user" else "actions"

        # keep a saved environment scope until the real list arrives
        self.environments = [self.scope[4:]] if self.scope.startswith("env:") else []
        self.entries = []
        self.show_header()
        self.sidebar.select(owner=owner)
        self._filter_repositories()
        self.rebuild_chips()
        self.app.save_settings()

        if owner.kind == "repo":
            self._load_environments(owner=owner)

        self.refresh()

    def _load_environments(self, owner: Owner) -> None:
        def done(environments: list[str]) -> None:
            if self.owner != owner:
                return

            scope = self.scope
            self.environments = environments
            self.rebuild_chips()

            if scope != self.scope:
                self.refresh()

        self.app.run(
            work=lambda: cli.list_environments(repo=owner.name),
            done=done,
            busy="Loading environments…",
        )

    # ---- entries

    def refresh(self) -> None:
        target = self.target(quiet=True)

        if target is None:
            self.stack.setCurrentIndex(PLACEHOLDER)

            return

        self.loading.show_text(title="Loading…", text=target.label())
        self.stack.setCurrentIndex(LOADING)

        def done(entries: list[Entry]) -> None:
            if (
                target.owner == "repo"
                and target.kind == "secret"
                and target.app == "actions"
                and not target.environment
            ):
                statuses = dict(self.sidebar.secret_statuses)
                statuses[target.name] = RepoSecretStatus(name=target.name, count=len(entries))
                self.sidebar.set_secret_statuses(statuses=list(statuses.values()), checking=self.secret_index_loading)

            if self.target(quiet=True) != target:
                return

            self.entries = entries
            self.paint()
            self.app.status(text=f"{len(entries)} in {target.label()}")

        def failed(exc: Exception) -> None:
            if self.target(quiet=True) == target:
                self.loading.show_text(title="Could not load", text=str(exc) or type(exc).__name__)

        self.app.run(
            work=lambda: cli.list_entries(target=target),
            done=done,
            busy="Loading from GitHub…",
            failed=failed,
        )

    def paint(self) -> None:
        target = self.target(quiet=True)

        if target is None:
            return

        text = self.search.text().strip().lower()
        shown = [entry for entry in self.entries if text in entry.name.lower()]
        total = len(self.entries)
        self.count.setText(f"{len(shown)} of {total}" if text else str(total))

        if not shown:
            self._show_empty(target=target, text=text)

            return

        selected = set(self.selected_names())
        self.list.clear()

        for entry in shown:
            item = QListWidgetItem(self.list)
            item.setData(NAME_ROLE, entry.name)
            row = EntryRow(
                entry=entry,
                kind=target.kind,
                shared=target.shared,
                on_edit=lambda name: self.edit(name=name),
                on_delete=lambda names: self.delete(names=names),
                on_copy=lambda value: self.copy_value(value=value),
            )
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            self.list.setItemWidget(item, row)
            item.setSelected(entry.name in selected)

        self.stack.setCurrentIndex(LIST)

    def _show_empty(self, target: Target, text: str) -> None:
        noun = "secret" if target.kind == "secret" else "variable"

        if text:
            self.empty.show_text(title=f"No {noun} matches", text=f"Nothing here contains “{text}”.")
        elif target.kind == "secret":
            self.empty.show_text(
                title="No secrets yet",
                text="Secrets are encrypted values that workflows read as ${{ secrets.NAME }}.",
            )
        else:
            self.empty.show_text(
                title="No variables yet",
                text="Variables are plain values that workflows read as ${{ vars.NAME }}.",
            )

        self.stack.setCurrentIndex(EMPTY)

    def selected_names(self) -> list[str]:
        return [item.data(NAME_ROLE) for item in self.list.selectedItems()]

    def entry(self, name: str) -> Entry | None:
        return next((entry for entry in self.entries if entry.name == name), None)

    def repo_choices(self, target: Target) -> list[str]:
        if target.owner == "org":
            return [repo.full_name for repo in self.directory.orgs.get(target.name, [])]

        return self.directory.all_repo_names()

    def copy_value(self, value: str) -> None:
        self.app.status(text=copy_secret(text=value))

    def save(self, target: Target, results: list[EntryResult]) -> None:
        def work() -> None:
            for result in results:
                cli.set_entry(
                    target=target,
                    name=result.name,
                    value=result.value,
                    access=result.access,
                )

        def done(_: None) -> None:
            self.app.status(text=f"Saved {len(results)} in {target.label()}")

            if self.target(quiet=True) == target:
                self.refresh()

        self.app.run(work=work, done=done, busy="Saving to GitHub…")

    def _dialog(
        self,
        parent: QWidget,
        title: str,
        target: Target,
        name: str = "",
        value: str = "",
        fixed_name: bool = False,
        access: Access | None = None,
    ) -> EntryResult | None:
        choices = self.repo_choices(target=target) if target.shared else None
        dialog = EntryDialog(
            parent=parent,
            title=title,
            kind=target.kind,
            check_name=cli.check_name,
            name=name,
            value=value,
            fixed_name=fixed_name,
            owner=target.owner,
            access=access,
            repo_choices=choices,
        )

        return dialog.ask()

    def new_entry(self) -> None:
        target = self.target()

        if target is None:
            return

        noun = "secret" if target.kind == "secret" else "variable"
        result = self._dialog(parent=self, title=f"New {noun} · {target.label()}", target=target)

        if result is None:
            return

        exists = self.entry(name=result.name) is not None

        if (
            exists
            and not ConfirmDialog(
                parent=self,
                title=f"Replace {noun}",
                text=f"{result.name} already exists in {target.label()}. Replace it?",
                ok_text="Replace",
            ).ask()
        ):
            return

        self.save(target=target, results=[result])

    def edit(self, name: str) -> None:
        target = self.target()
        entry = self.entry(name=name) if name else None

        if target is None or entry is None:
            return

        needs_repos = target.owner == "user" or entry.visibility == "selected"

        if not target.shared or not needs_repos:
            access = Access.model_validate(obj={"visibility": entry.visibility or "private"}) if target.shared else None
            self._edit_with(target=target, entry=entry, access=access)

            return

        # the list only has a count, so fetch which repositories can read it first
        def done(repos: list[str]) -> None:
            access = Access(visibility="selected", repos=repos)
            self._edit_with(target=target, entry=entry, access=access)

        self.app.run(
            work=lambda: cli.selected_repos(target=target, name=name),
            done=done,
            busy="Loading repository access…",
        )

    def _edit_with(self, target: Target, entry: Entry, access: Access | None) -> None:
        verb = "Edit" if target.kind == "variable" else "Replace value"
        result = self._dialog(
            parent=self,
            title=f"{verb} · {target.label()}",
            target=target,
            name=entry.name,
            value=entry.value or "",
            fixed_name=True,
            access=access,
        )

        if result is not None:
            self.save(target=target, results=[result])

    # Used by the Firestore and Secret Manager tabs to send a value to GitHub as a secret
    def push_secret(self, parent: QWidget, name: str, value: str) -> None:
        current = self.target()

        if current is None:
            return

        target = current.model_copy(update={"kind": "secret"})
        result = self._dialog(
            parent=parent,
            title=f"Set GitHub secret · {target.label()}",
            target=target,
            name=name,
            value=value,
        )

        if result is None:
            return

        if ConfirmDialog(
            parent=parent,
            title="Set GitHub secret",
            text=f"Set {result.name} in {target.label()}? A secret with the same name is overwritten.",
            ok_text="Set secret",
        ).ask():
            self.save(target=target, results=[result])

    def delete(self, names: list[str]) -> None:
        target = self.target()

        if target is None or not names:
            self.app.status(text="Select something to delete")

            return

        listed = "\n".join(f"  • {name}" for name in names)
        warning = "Workflows that use them will stop working. This cannot be undone."

        if not ConfirmDialog(
            parent=self,
            title="Delete" if len(names) > 1 else f"Delete {names[0]}",
            text=f"Delete from {target.label()}:\n\n{listed}\n\n{warning}",
        ).ask():
            return

        def work() -> None:
            for name in names:
                cli.delete_entry(target=target, name=name)

        def done(_: None) -> None:
            self.app.status(text=f"Deleted {len(names)} from {target.label()}")
            self.refresh()

        self.app.run(work=work, done=done, busy="Deleting on GitHub…")

    def import_env(self) -> None:
        target = self.target()

        if target is None:
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Import from a .env file", "", "Env files (.env *.env);;All files (*)"
        )

        if not path:
            return

        names = env_names(path=path)

        if not names:
            QMessageBox.warning(self, "Import .env", "No variables were found in that file.")

            return

        existing = {entry.name for entry in self.entries}
        lines = [f"  • {name}{'  (replaces the current value)' if name in existing else ''}" for name in names]
        file_name = os.path.basename(path)

        if not ConfirmDialog(
            parent=self,
            title="Import .env",
            text=f"Set {len(names)} in {target.label()} from {file_name}:\n\n" + "\n".join(lines),
            ok_text="Import",
        ).ask():
            return

        def done(_: None) -> None:
            self.app.status(text=f"Imported {len(names)} from {file_name}")
            self.refresh()

        self.app.run(
            work=lambda: cli.set_from_env_file(target=target, path=path),
            done=done,
            busy="Importing…",
        )

    def open_on_github(self) -> None:
        target = self.target()

        if target is not None:
            QDesktopServices.openUrl(QUrl(page_url(target=target)))
