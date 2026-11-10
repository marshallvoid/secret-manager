from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import theme
from ..utils.dates import exact_time, relative_time
from ..widgets import badge, flat_button, icon_label, muted
from .models import Entry, EntryKind

VALUE_PREVIEW = 70


# Runs after the click, since the list is rebuilt when the change lands
def later(action: Callable[[], None]) -> Callable[[bool], None]:
    def delayed(_checked: bool = False) -> None:
        QTimer.singleShot(0, action)

    return delayed


class EntryRow(QWidget):
    def __init__(
        self,
        entry: Entry,
        kind: EntryKind,
        shared: bool,
        on_edit: Callable[[str], None],
        on_delete: Callable[[list[str]], None],
        on_copy: Callable[[str], None],
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 10, 10)
        layout.setSpacing(12)
        layout.addWidget(icon_label(key="key" if kind == "secret" else "variable", size=20))

        title = QLabel(entry.name)
        title.setObjectName("SecretName")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)

        if entry.value is not None:
            layout.addSpacing(8)
            layout.addWidget(self._value_label(value=entry.value), 1)
        else:
            layout.addStretch(1)

        if shared and entry.access_text():
            layout.addWidget(badge(text=entry.access_text(), color=theme.ACCENT))

        updated = muted(text=relative_time(value=entry.updated))
        updated.setToolTip(exact_time(value=entry.updated))
        layout.addWidget(updated)
        layout.addSpacing(8)

        if entry.value is not None:
            value = entry.value
            copy = flat_button(icon="copy", tip="Copy value")
            copy.clicked.connect(lambda _=False: on_copy(value))
            layout.addWidget(copy)

        edit_tip = "Edit" if kind == "variable" else "Replace value"
        edit = flat_button(icon="edit", tip=edit_tip)
        edit.clicked.connect(later(action=lambda: on_edit(entry.name)))
        layout.addWidget(edit)

        delete = flat_button(icon="delete", tip="Delete")
        delete.clicked.connect(later(action=lambda: on_delete([entry.name])))
        layout.addWidget(delete)

    @staticmethod
    def _value_label(value: str) -> QLabel:
        flat = value.replace("\n", " ⏎ ")
        short = flat if len(flat) <= VALUE_PREVIEW else flat[: VALUE_PREVIEW - 1] + "…"
        label = QLabel(short or '""')
        label.setObjectName("Value")
        label.setToolTip(value[:2000])

        return label
