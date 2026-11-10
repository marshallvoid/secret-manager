from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set

from pydantic import BaseModel, Field
from PySide6.QtCore import QSignalBlocker, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from .. import theme
from ..widgets import PanelHeader, flat_button, search_box
from ..widgets_links import LinkLabel
from .cli import REPO_RE
from .models import Owner, Repo, RepositoryFilter
from .secret_index import RepoSecretStatus

OWNER_ROLE = Qt.ItemDataRole.UserRole
USER_OWNER = Owner(kind="user", name="", label="Codespaces")
OWNER_ICONS: Dict[str, str] = {"repo": "repo", "org": "org", "user": "person"}


class Directory(BaseModel):
    repos: List[Repo] = Field(default_factory=list)
    # organization login → its repositories
    orgs: Dict[str, List[Repo]] = Field(default_factory=dict)

    def all_repo_names(self) -> List[str]:
        names = [repo.full_name for repo in self.repos]

        for repos in self.orgs.values():
            names += [repo.full_name for repo in repos]

        return sorted(names, key=str.lower)


class Section(BaseModel):
    key: str
    title: str
    owners: List[Owner]


def repo_owner(full_name: str) -> Owner:
    return Owner(kind="repo", name=full_name, label=full_name.split("/")[-1])


class Sidebar(QFrame):
    def __init__(
        self,
        on_select: Callable[[Owner], None],
        on_reload: Callable[[], None],
        on_filter: Optional[Callable[[], None]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self.setObjectName("Browser")
        self.setMinimumWidth(240)
        self.on_select = on_select
        self.directory = Directory()
        self.current: Optional[Owner] = None
        self.on_filter = on_filter
        self.on_change = on_change
        self.collapsed: Set[str] = set()
        self.secret_statuses: Dict[str, RepoSecretStatus] = {}
        self.checking = False
        self.focus_section: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("GitHub")
        title.setObjectName("PanelTitle")
        header = PanelHeader(icon="repo", title=title)
        reload_button = flat_button(icon="refresh", tip="Reload repositories and organizations")
        reload_button.clicked.connect(lambda _=False: on_reload())
        header.row.addWidget(reload_button)
        layout.addWidget(header)

        box = QVBoxLayout()
        box.setContentsMargins(10, 10, 10, 6)
        box.setSpacing(8)
        self.search = search_box(placeholder="Filter, or type owner/name ↵")
        self.search.textChanged.connect(self._search_changed)
        self.search.returnPressed.connect(self.open_typed)
        box.addWidget(self.search)
        filter_label = QLabel("Repository secrets")
        self.secret_filter = QComboBox()
        self.secret_filter.addItem("All repositories", "all")
        self.secret_filter.addItem("With secrets", "with")
        self.secret_filter.addItem("Without secrets", "without")
        self.secret_filter.addItem("Unable to check", "unknown")
        self.secret_filter.setAccessibleName("Filter repositories by Actions secrets")
        self.secret_filter.setToolTip(
            "Repository Actions secrets only. Excludes inherited, environment, "
            "Dependabot and Codespaces secrets. Failed checks are never treated as empty."
        )
        filter_label.setBuddy(self.secret_filter)
        self.secret_filter.currentIndexChanged.connect(self._filter_changed)
        box.addWidget(filter_label)
        box.addWidget(self.secret_filter)
        self.filter_note = LinkLabel()
        self.filter_note.setObjectName("Muted")
        self.filter_note.setWordWrap(True)
        self.filter_note.hide()
        box.addWidget(self.filter_note)
        layout.addLayout(box)

        self.list = QListWidget()
        self.list.setObjectName("Items")
        self.list.setProperty("repositoryList", True)
        self.list.setItemDelegate(theme.ChevronDelegate(parent=self.list))
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.itemClicked.connect(self._clicked)
        layout.addWidget(self.list, 1)

        self.note = LinkLabel(text="Loading repositories…")
        self.note.setObjectName("Note")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

    def restore_state(self, repo_filter: RepositoryFilter, search: str, collapsed: List[str]) -> None:
        self.collapsed = set(collapsed)

        with QSignalBlocker(self.search), QSignalBlocker(self.secret_filter):
            self.search.setText(search)
            self.secret_filter.setCurrentIndex(self.secret_filter.findData(repo_filter))

        self.fill()

    def _search_changed(self) -> None:
        self.fill()

        if self.on_change is not None:
            self.on_change()

    def _filter_changed(self) -> None:
        self.fill()

        if self.on_filter is not None:
            self.on_filter()

        if self.on_change is not None:
            self.on_change()

    def set_secret_statuses(self, statuses: List[RepoSecretStatus], checking: bool = False) -> None:
        self.secret_statuses = {status.name: status for status in statuses}
        self.checking = checking
        self.fill()

    def _matches_secrets(self, owner: Owner) -> bool:
        mode = self.secret_filter.currentData()

        if owner.kind != "repo" or mode == "all":
            return True

        status = self.secret_statuses.get(owner.name)

        if status is None:
            return False

        if mode == "unknown":
            return status.count is None

        if status.count is None:
            return False

        return status.count > 0 if mode == "with" else status.count == 0

    def set_directory(self, directory: Directory) -> None:
        self.directory = directory
        self.fill()

    def repository_names(self) -> List[str]:
        return sorted({owner.name for section in self._sections() for owner in section.owners if owner.kind == "repo"})

    def show_note(self, text: str) -> None:
        self.note.setText(text)
        self.note.show()

    def select(self, owner: Optional[Owner]) -> None:
        self.current = owner
        item = self._owner_item(owner=owner)

        if item is not None:
            if self.list.currentItem() is not item:
                self.list.setCurrentItem(item)
                self.list.scrollToItem(item)

            return

        self.fill()
        item = self._owner_item(owner=owner)

        if item is not None:
            self.list.scrollToItem(item)

    def _owner_item(self, owner: Optional[Owner]) -> Optional[QListWidgetItem]:

        if owner is None:
            return None

        for index in range(self.list.count()):
            item = self.list.item(index)

            if item.data(OWNER_ROLE) == owner:
                return item

        return None

    def _clicked(self, item: QListWidgetItem) -> None:
        owner = item.data(OWNER_ROLE)

        if isinstance(owner, Owner):
            self.on_select(owner)

    def open_typed(self) -> None:
        text = self.search.text().strip()

        if REPO_RE.fullmatch(text):
            self.search.clear()
            self.on_select(repo_owner(full_name=text))

            return

        items = [self.list.item(index) for index in range(self.list.count())]
        owners = [item.data(OWNER_ROLE) for item in items]
        owners = [owner for owner in owners if isinstance(owner, Owner)]

        if len(owners) == 1:
            self.on_select(owners[0])

    # From the widest scope to the narrowest: account, organizations, then repositories
    def _sections(self) -> List[Section]:
        sections = [Section(key="account", title="Account", owners=[USER_OWNER])]

        for org, repos in sorted(self.directory.orgs.items()):
            org_owner = Owner(kind="org", name=org, label=org)
            members = [repo_owner(full_name=repo.full_name) for repo in repos]
            sections.append(Section(key=f"org:{org}", title=org, owners=[org_owner, *members]))

        own = [repo_owner(full_name=repo.full_name) for repo in self.directory.repos]
        sections.append(Section(key="repos", title="Your repositories", owners=own))

        # a repository opened by typing its name stays visible
        known = {owner for section in sections for owner in section.owners}

        if self.current is not None and self.current not in known:
            sections.append(Section(key="opened", title="Opened", owners=[self.current]))

        return sections

    def fill(self) -> None:
        vertical = self.list.verticalScrollBar().value()
        horizontal = self.list.horizontalScrollBar().value()
        self.list.setUpdatesEnabled(False)

        try:
            with QSignalBlocker(self.list.selectionModel()):
                self._fill_items()
                self.list.doItemsLayout()
        finally:
            self.list.verticalScrollBar().setValue(vertical)
            self.list.horizontalScrollBar().setValue(horizontal)
            self.list.setUpdatesEnabled(True)

    def _fill_items(self) -> None:
        text = self.search.text().strip().lower()
        self.list.clear()
        shown = 0
        matching_repos = 0

        for section in self._sections():
            matches = [
                owner
                for owner in section.owners
                if (text in owner.label.lower() or text in owner.name.lower()) and self._matches_secrets(owner=owner)
            ]

            if not matches:
                continue

            matching_repos += sum(owner.kind == "repo" for owner in matches)
            self._add_header(title=section.title, key=section.key)

            if section.key in self.collapsed:
                shown += len(matches)

                continue

            for owner in matches:
                self._add_owner(owner=owner)

            shown += len(matches)

        if shown:
            self.note.hide()
        elif REPO_RE.fullmatch(self.search.text().strip()):
            self.show_note(text="Press Enter to open this repository.")
        else:
            self.show_note(text="Nothing matches.")

        failures = sum(status.count is None for status in self.secret_statuses.values())
        note = (
            "Checking repository Actions secrets…"
            if self.checking
            else (
                f"{failures} repositories could not be checked. Select Unable to check; reload to retry."
                if failures
                else "Repository Actions secrets only."
            )
        )
        self.filter_note.setText(note)

        if not matching_repos and not self.checking:
            self.filter_note.setText(f"No repositories match. {note}")

        self.filter_note.setVisible(self.secret_filter.currentData() != "all")

    def _toggle_section(self, key: str, expanded: bool) -> None:

        if expanded:
            self.collapsed.discard(key)
        else:
            self.collapsed.add(key)

        self.focus_section = key
        QTimer.singleShot(0, self.fill)

        if self.on_change is not None:
            self.on_change()

    def _add_header(self, title: str, key: str) -> None:
        item = QListWidgetItem(self.list)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        label = QToolButton()
        label.setObjectName("SectionToggle")
        label.setText(title)
        label.setCheckable(True)
        label.setChecked(key not in self.collapsed)
        label.setAccessibleName(f"Expand or collapse {title}")
        label.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        label.setArrowType(Qt.ArrowType.DownArrow if label.isChecked() else Qt.ArrowType.RightArrow)
        label.toggled.connect(lambda expanded: self._toggle_section(key=key, expanded=expanded))

        # the item padding (6px above and below) eats into the widget's height
        label.ensurePolished()
        item.setSizeHint(QSize(0, label.sizeHint().height() + 14))
        self.list.setItemWidget(item, label)

        if self.focus_section == key:
            label.setFocus()
            self.focus_section = None

    def _add_owner(self, owner: Owner) -> None:
        icon = theme.named_icon(key=OWNER_ICONS[owner.kind])
        item = QListWidgetItem(icon, owner.label, self.list)
        item.setData(OWNER_ROLE, owner)
        tips = {
            "repo": owner.name,
            "org": f"Organization secrets and variables of {owner.name}",
            "user": "Your Codespaces secrets",
        }
        item.setToolTip(tips[owner.kind])

        if owner == self.current:
            self.list.setCurrentItem(item)
