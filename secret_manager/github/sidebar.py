from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

from .. import theme
from ..widgets import PanelHeader, flat_button, search_box
from .cli import REPO_RE
from .models import Owner, Repo

OWNER_ROLE = Qt.ItemDataRole.UserRole
USER_OWNER = Owner(kind="user", name="", label="Codespaces")
OWNER_ICONS: dict[str, str] = {"repo": "repo", "org": "org", "user": "person"}


class Directory(BaseModel):
    repos: list[Repo] = Field(default_factory=list)
    # organization login → its repositories
    orgs: dict[str, list[Repo]] = Field(default_factory=dict)

    def all_repo_names(self) -> list[str]:
        names = [repo.full_name for repo in self.repos]

        for repos in self.orgs.values():
            names += [repo.full_name for repo in repos]

        return sorted(names, key=str.lower)


class Section(BaseModel):
    title: str
    owners: list[Owner]


def repo_owner(full_name: str) -> Owner:
    return Owner(kind="repo", name=full_name, label=full_name.split("/")[-1])


class Sidebar(QFrame):
    def __init__(
        self,
        on_select: Callable[[Owner], None],
        on_reload: Callable[[], None],
    ) -> None:
        super().__init__()
        self.setObjectName("Browser")
        self.setMinimumWidth(240)
        self.on_select = on_select
        self.directory = Directory()
        self.current: Owner | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("GitHub")
        title.setObjectName("PanelTitle")
        header = PanelHeader(icon="repo", title=title)
        reload_button = flat_button(
            icon="refresh", tip="Reload repositories and organizations"
        )
        reload_button.clicked.connect(lambda _=False: on_reload())
        header.row.addWidget(reload_button)
        layout.addWidget(header)

        box = QVBoxLayout()
        box.setContentsMargins(10, 10, 10, 6)
        self.search = search_box(placeholder="Filter, or type owner/name ↵")
        self.search.textChanged.connect(lambda _: self.fill())
        self.search.returnPressed.connect(self.open_typed)
        box.addWidget(self.search)
        layout.addLayout(box)

        self.list = QListWidget()
        self.list.setObjectName("Items")
        self.list.setItemDelegate(theme.ChevronDelegate(parent=self.list))
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.itemClicked.connect(self._clicked)
        layout.addWidget(self.list, 1)

        self.note = QLabel("Loading repositories…")
        self.note.setObjectName("Note")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

    def set_directory(self, directory: Directory) -> None:
        self.directory = directory
        self.fill()

    def show_note(self, text: str) -> None:
        self.note.setText(text)
        self.note.show()

    def select(self, owner: Owner | None) -> None:
        self.current = owner
        self.fill()

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
    def _sections(self) -> list[Section]:
        sections = [Section(title="ACCOUNT", owners=[USER_OWNER])]

        for org, repos in sorted(self.directory.orgs.items()):
            org_owner = Owner(kind="org", name=org, label=org)
            members = [repo_owner(full_name=repo.full_name) for repo in repos]
            sections.append(Section(title=org.upper(), owners=[org_owner, *members]))

        own = [repo_owner(full_name=repo.full_name) for repo in self.directory.repos]
        sections.append(Section(title="YOUR REPOSITORIES", owners=own))

        # a repository opened by typing its name stays visible
        known = {owner for section in sections for owner in section.owners}

        if self.current is not None and self.current not in known:
            sections.append(Section(title="OPENED", owners=[self.current]))

        return sections

    def fill(self) -> None:
        text = self.search.text().strip().lower()
        self.list.clear()
        shown = 0

        for section in self._sections():
            matches = [
                owner
                for owner in section.owners
                if text in owner.label.lower() or text in owner.name.lower()
            ]

            if not matches:
                continue

            self._add_header(title=section.title)

            for owner in matches:
                self._add_owner(owner=owner)

            shown += len(matches)

        if shown:
            self.note.hide()
        elif REPO_RE.fullmatch(self.search.text().strip()):
            self.show_note(text="Press Enter to open this repository.")
        else:
            self.show_note(text="Nothing matches.")

    def _add_header(self, title: str) -> None:
        item = QListWidgetItem(self.list)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        label = QLabel(title)
        label.setObjectName("SectionHeader")

        # the item padding (6px above and below) eats into the widget's height
        label.ensurePolished()
        item.setSizeHint(QSize(0, label.sizeHint().height() + 14))
        self.list.setItemWidget(item, label)

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

        # the current item may sit far down the list, so bring it into view
        if owner == self.current:
            self.list.setCurrentItem(item)
            self.list.scrollToItem(item)
