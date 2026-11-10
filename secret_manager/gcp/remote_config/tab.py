from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ... import theme
from ...dialogs import ConfirmDialog
from ...utils.dates import relative_time
from ...widgets import (
    MessagePage,
    PanelHeader,
    flat_button,
    muted,
    primary_button,
    search_box,
    separator,
)
from ..credentials import GoogleAccount
from .client import RemoteConfigClient
from .dialogs import ConditionDialog, ParameterDialog, VersionsDialog, color_icon
from .models import Parameter, Template, TemplateVersion

if TYPE_CHECKING:
    from ...app import App

KEY_ROLE = Qt.ItemDataRole.UserRole
PLACEHOLDER, LOADING, CONTENT = range(3)


def row_actions(on_edit: Callable[[], None], on_delete: Callable[[], None]) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 6, 0)
    layout.setSpacing(2)
    layout.addStretch(1)

    edit = flat_button(icon="edit", tip="Edit")
    edit.clicked.connect(lambda _=False: QTimer.singleShot(0, on_edit))
    layout.addWidget(edit)

    delete = flat_button(icon="delete", tip="Delete")
    delete.clicked.connect(lambda _=False: QTimer.singleShot(0, on_delete))
    layout.addWidget(delete)

    return box


def table(headers: list[str], stretch: int) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setObjectName("Table")
    tree.setHeaderLabels(headers)
    tree.setColumnCount(len(headers))
    tree.setFrameShape(QFrame.Shape.NoFrame)
    header = tree.header()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Fixed)
    header.resizeSection(len(headers) - 1, 96)

    return tree


class RemoteConfigTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.client: RemoteConfigClient | None = None
        self.template: Template | None = None
        self.changes = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("Browser")
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header())
        layout.addWidget(self._banner())

        self.stack = QStackedWidget()
        self.placeholder = MessagePage(
            icon="tune",
            title="Not connected",
            text="Choose a service account file above and press Connect.",
        )
        self.stack.addWidget(self.placeholder)
        self.loading = MessagePage(icon="refresh", title="Loading the template…")
        self.stack.addWidget(self.loading)

        self.pages = QTabWidget()
        self.pages.addTab(self._parameters_page(), "Parameters")
        self.pages.addTab(self._conditions_page(), "Conditions")
        self.stack.addWidget(self.pages)
        layout.addWidget(self.stack, 1)

    # ---- layout

    def _header(self) -> QWidget:
        title = QLabel("Remote Config")
        title.setObjectName("PanelTitle")
        header = PanelHeader(icon="tune", title=title)
        header.row.setStretch(1, 0)
        header.row.addSpacing(12)
        self.version_label = muted(text="")
        header.row.addWidget(self.version_label, 1)

        history = flat_button(icon="history", tip="Version history and rollback")
        history.clicked.connect(lambda _=False: self.show_versions())
        header.row.addWidget(history)

        refresh = flat_button(icon="refresh", tip="Reload the published template")
        refresh.clicked.connect(lambda _=False: self.reload())
        header.row.addWidget(refresh)

        return header

    def _banner(self) -> QWidget:
        self.banner = QWidget()
        self.banner.setObjectName("Draft")
        self.banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.banner.setStyleSheet("QWidget#Draft { background: #3b3424; }")
        layout = QHBoxLayout(self.banner)
        layout.setContentsMargins(16, 8, 16, 8)

        self.banner_text = QLabel()
        self.banner_text.setStyleSheet("color: #fdd663;")
        layout.addWidget(self.banner_text, 1)

        discard_button = QPushButton("Discard all")
        discard_button.clicked.connect(self.discard_changes)
        layout.addWidget(discard_button)
        layout.addWidget(primary_button(text="Publish changes", action=self.publish, icon="upload"))
        self.banner.hide()

        return self.banner

    def _parameters_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 12, 16, 10)
        self.search = search_box(placeholder="Search parameters")
        self.search.setMaximumWidth(380)
        self.search.textChanged.connect(lambda _: self.paint_parameters())
        toolbar.addWidget(self.search, 1)
        self.count = QLabel("0")
        self.count.setObjectName("Count")
        toolbar.addWidget(self.count)
        toolbar.addStretch(1)
        toolbar.addWidget(primary_button(text="Add parameter", action=lambda: self.edit_parameter(key=None)))
        layout.addLayout(toolbar)
        layout.addWidget(separator())

        headers = ["Parameter", "Default value", "Conditional values", "Type", ""]
        self.params = table(headers=headers, stretch=1)
        self.params.itemDoubleClicked.connect(self._param_clicked)
        layout.addWidget(self.params, 1)

        return page

    def _conditions_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 12, 16, 10)
        toolbar.addWidget(muted(text="Conditions are checked from top to bottom; the first match wins."))
        toolbar.addStretch(1)
        toolbar.addWidget(primary_button(text="Add condition", action=lambda: self.edit_condition(name=None)))
        layout.addLayout(toolbar)
        layout.addWidget(separator())

        self.conditions = table(headers=["Condition", "Expression", "Used by", ""], stretch=1)
        self.conditions.itemDoubleClicked.connect(
            lambda item, _column: self.edit_condition(name=item.data(0, KEY_ROLE))
        )
        layout.addWidget(self.conditions, 1)

        return page

    # ---- loading and publishing

    def connect_account(self, account: GoogleAccount) -> None:
        self.client = RemoteConfigClient(account=account)
        self.reload()

    def reload(self) -> None:
        client = self.client

        if client is None:
            self.stack.setCurrentIndex(PLACEHOLDER)

            return

        self.stack.setCurrentIndex(LOADING)

        def failed(exc: Exception) -> None:
            self.loading.show_text(title="Could not load Remote Config", text=str(exc))

        self.app.run(
            work=client.get,
            done=self._loaded,
            busy="Loading Remote Config…",
            failed=failed,
        )

    def _loaded(self, template: Template) -> None:
        self.template = template
        self.changes = 0
        self.paint()
        self.stack.setCurrentIndex(CONTENT)
        project = self.client.project if self.client is not None else ""
        self.app.status(text=f"Loaded Remote Config of {project}")

    def publish(self) -> None:
        client, template = self.client, self.template

        if client is None or template is None or not self.changes:
            return

        if not ConfirmDialog(
            parent=self,
            title="Publish changes",
            text=f"Publish {self.changes} change(s)? Apps that fetch Remote Config get them right away.",
            ok_text="Publish",
        ).ask():
            return

        self.app.run(
            work=lambda: client.publish(template=template),
            done=self._loaded,
            busy="Publishing…",
        )

    def discard_changes(self) -> None:
        if ConfirmDialog(
            parent=self,
            title="Discard changes",
            text="Throw away every unpublished change?",
            ok_text="Discard",
        ).ask():
            self.reload()

    def show_versions(self) -> None:
        client = self.client

        if client is not None:
            self.app.run(
                work=client.versions,
                done=self._choose_version,
                busy="Loading versions…",
            )

    def _choose_version(self, versions: list[TemplateVersion]) -> None:
        client = self.client
        number = VersionsDialog(parent=self, versions=versions).ask()

        if number is None or client is None:
            return

        warning = " Your unpublished changes are lost." if self.changes else ""

        if not ConfirmDialog(
            parent=self,
            title="Roll back",
            text=f"Publish version {number} again as the current template?{warning}",
            ok_text="Roll back",
        ).ask():
            return

        self.app.run(
            work=lambda: client.rollback(number=number),
            done=self._loaded,
            busy="Rolling back…",
        )

    # ---- painting

    def _changed(self) -> None:
        self.changes += 1
        self.paint()

    def paint(self) -> None:
        template = self.template

        if template is None:
            return

        version = template.version

        if version is not None:
            who = f" by {version.update_user.email}" if version.update_user.email else ""
            published = relative_time(value=version.update_time, prefix="published")
            self.version_label.setText(f"Version {version.version_number} · {published}{who}")
        else:
            self.version_label.setText("No published template yet")

        self.banner.setVisible(self.changes > 0)
        self.banner_text.setText(
            f"{self.changes} unpublished change(s). Apps keep the published template until you publish."
        )
        self.paint_parameters()
        self.paint_conditions()

    def paint_parameters(self) -> None:
        template = self.template

        if template is None:
            return

        text = self.search.text().strip().lower()
        shown = [
            param
            for param in template.parameters
            if text in param.key.lower() or text in param.description.lower() or text in param.group.lower()
        ]
        total = len(template.parameters)
        self.count.setText(f"{len(shown)} of {total}" if text else str(total))
        self.params.clear()
        groups: dict[str, QTreeWidgetItem] = {}

        for param in shown:
            parent: QTreeWidget | QTreeWidgetItem = self.params

            if param.group:
                if param.group not in groups:
                    description = template.groups.get(param.group, "")
                    groups[param.group] = self._group_item(name=param.group, description=description)

                parent = groups[param.group]

            self._param_item(parent=parent, param=param)

        self.params.expandAll()

        for column in (0, 2, 3):
            self.params.resizeColumnToContents(column)

    def _group_item(self, name: str, description: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self.params, [name, description])
        font = QFont(item.font(0))
        font.setBold(True)
        item.setFont(0, font)
        item.setIcon(0, theme.named_icon(key="collection"))
        item.setForeground(1, QColor(theme.MUTED))

        return item

    def _param_item(self, parent: QTreeWidget | QTreeWidgetItem, param: Parameter) -> None:
        default = param.default.describe() if param.default is not None else "(no default)"
        conditional = ", ".join(param.conditional)
        item = QTreeWidgetItem(parent, [param.key, default, conditional, param.value_type.title(), ""])
        item.setData(0, KEY_ROLE, param.key)
        item.setToolTip(0, param.description or param.key)
        item.setToolTip(1, default[:2000])
        item.setToolTip(
            2,
            "\n".join(f"{name}: {value.describe()[:200]}" for name, value in param.conditional.items()),
        )
        key = param.key
        actions = row_actions(
            on_edit=lambda: self.edit_parameter(key=key),
            on_delete=lambda: self.delete_parameter(key=key),
        )
        self.params.setItemWidget(item, 4, actions)

    def paint_conditions(self) -> None:
        template = self.template

        if template is None:
            return

        self.conditions.clear()

        for condition in template.conditions:
            name = condition.name
            users = sum(1 for param in template.parameters if name in param.conditional)
            item = QTreeWidgetItem(
                self.conditions,
                [name, condition.expression, f"{users} parameter(s)", ""],
            )
            item.setIcon(0, color_icon(color=condition.tag_color))
            item.setData(0, KEY_ROLE, name)
            item.setToolTip(1, condition.expression)
            actions = row_actions(
                on_edit=partial(self.edit_condition, name=name),
                on_delete=partial(self.delete_condition, name=name),
            )
            self.conditions.setItemWidget(item, 3, actions)

        for column in (0, 2):
            self.conditions.resizeColumnToContents(column)

    # ---- editing; changes stay local until published

    def _param_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        key = item.data(0, KEY_ROLE)

        if key:
            self.edit_parameter(key=key)

    def edit_parameter(self, key: str | None) -> None:
        template = self.template

        if template is None:
            return

        original = template.parameter(key=key) if key else None
        result = ParameterDialog(parent=self, template=template, param=original).ask()

        if result is None:
            return

        if result.group and result.group not in template.groups:
            template.groups[result.group] = ""

        if original is not None:
            template.parameters[template.parameters.index(original)] = result
        else:
            template.parameters.append(result)
            template.parameters.sort(key=lambda param: param.key.lower())

        self._changed()

    def delete_parameter(self, key: str) -> None:
        template = self.template

        if template is None:
            return

        if ConfirmDialog(parent=self, title="Delete parameter", text=f"Delete the parameter {key}?").ask():
            template.parameters = [param for param in template.parameters if param.key != key]
            self._changed()

    def edit_condition(self, name: str | None) -> None:
        template = self.template

        if template is None:
            return

        original = next((c for c in template.conditions if c.name == name), None)
        result = ConditionDialog(parent=self, template=template, condition=original).ask()

        if result is None:
            return

        if original is None:
            template.conditions.append(result)
        else:
            template.rename_condition(old=original.name, new=result.name)
            template.conditions[template.conditions.index(original)] = result

        self._changed()

    def delete_condition(self, name: str) -> None:
        template = self.template

        if template is None:
            return

        users = [param.key for param in template.parameters if name in param.conditional]
        detail = f" Its values are removed from: {', '.join(users)}." if users else ""

        if ConfirmDialog(
            parent=self,
            title="Delete condition",
            text=f"Delete the condition {name}?{detail}",
        ).ask():
            template.drop_condition(name=name)
            self._changed()
