from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

from google.cloud.firestore import GeoPoint
from google.cloud.firestore_v1.document import DocumentReference
from pydantic import BaseModel, ConfigDict
from PySide6.QtCore import QDateTime, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...widgets import AutoText, flat_button, link_button, muted
from . import values
from .store import check_field_name


# An input for one non-container value, and how to read the value back
class ScalarEditor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    widget: QWidget
    read: Callable[[], Any]


def _number_editor(value: Any) -> ScalarEditor:
    start = values.format_number(value=value) if values.type_of(value=value) == "number" else "0"
    edit = QLineEdit(start)

    def read() -> int | float:
        try:
            return values.parse_number(text=edit.text())
        except ValueError as exc:
            raise ValueError(f"'{edit.text()}' is not a number") from exc

    return ScalarEditor(widget=edit, read=read)


def _boolean_editor(value: Any) -> ScalarEditor:
    box = QComboBox()
    box.addItems(["true", "false"])
    box.setCurrentIndex(0 if value is not False else 1)

    return ScalarEditor(widget=box, read=lambda: box.currentIndex() == 0)


def _timestamp_editor(value: Any) -> ScalarEditor:
    edit = QDateTimeEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    original = value if isinstance(value, datetime.datetime) else None
    start = original or values.default_for(kind="timestamp")
    edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(start.timestamp())))

    def read() -> datetime.datetime:
        seconds = edit.dateTime().toSecsSinceEpoch()

        # an untouched value keeps its sub-second part
        if original is not None and seconds == int(original.timestamp()):
            return original

        return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)

    return ScalarEditor(widget=edit, read=read)


def _geopoint_editor(value: Any) -> ScalarEditor:
    point = value if isinstance(value, GeoPoint) else GeoPoint(latitude=0.0, longitude=0.0)
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    lat = QLineEdit(str(point.latitude))
    lng = QLineEdit(str(point.longitude))
    lat.setPlaceholderText("Latitude")
    lng.setPlaceholderText("Longitude")
    layout.addWidget(lat)
    layout.addWidget(lng)

    def read() -> GeoPoint:
        try:
            latitude, longitude = float(lat.text()), float(lng.text())
        except ValueError as exc:
            raise ValueError("Latitude and longitude must be numbers") from exc

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Latitude must be in [-90, 90] and longitude in [-180, 180]")

        return GeoPoint(latitude=latitude, longitude=longitude)

    return ScalarEditor(widget=box, read=read)


def _reference_editor(value: Any) -> ScalarEditor:
    original = value if isinstance(value, DocumentReference) else None
    is_reference = values.type_of(value=value) == "reference"
    edit = QLineEdit(values.ref_path(value=value) if is_reference else "")
    edit.setPlaceholderText("/collection/document")

    def read() -> DocumentReference | values.RefPath:
        text = edit.text().strip()

        if original is not None and text == values.ref_path(value=original):
            return original

        if not text.strip("/") or text.strip("/").count("/") % 2 == 0:
            raise ValueError(f"'{text}' is not a document path")

        return values.RefPath(text)

    return ScalarEditor(widget=edit, read=read)


def scalar_editor(kind: str, value: Any) -> ScalarEditor:
    if kind == "string":
        text = AutoText(text=value if isinstance(value, str) else "")

        return ScalarEditor(widget=text, read=text.toPlainText)

    if kind == "number":
        return _number_editor(value=value)

    if kind == "boolean":
        return _boolean_editor(value=value)

    if kind == "null":
        return ScalarEditor(widget=muted(text="null"), read=lambda: None)

    if kind == "timestamp":
        return _timestamp_editor(value=value)

    if kind == "geopoint":
        return _geopoint_editor(value=value)

    if kind == "reference":
        return _reference_editor(value=value)

    # bytes and anything else the console cannot edit stay as they are
    label = muted(text=f"{values.preview(value=value)}  (read-only)")

    return ScalarEditor(widget=label, read=lambda: value)


def collect_map(rows: list[FieldRow]) -> dict[str, Any]:
    data: dict[str, Any] = {}

    for row in rows:
        name = row.name() or ""
        problem = check_field_name(name=name)

        if problem:
            raise ValueError(problem)

        if name in data:
            raise ValueError(f"The field name '{name}' is used twice")

        data[name] = row.value()

    return data


# One field: name, type and value; maps and arrays hold rows of their own
class FieldRow(QWidget):
    remove_requested = Signal(object)

    def __init__(
        self,
        name: str = "",
        value: Any = "",
        named: bool = True,
        removable: bool = True,
        name_editable: bool = True,
    ) -> None:
        super().__init__()
        self.named = named
        self.original = value
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        line = QHBoxLayout()
        outer.addLayout(line)

        self.name_edit: QLineEdit | None = None
        self.index_label = muted(text="")

        if named:
            self.name_edit = QLineEdit(name)
            self.name_edit.setPlaceholderText("Field")
            self.name_edit.setEnabled(name_editable)
            self.name_edit.setFixedWidth(210)
            line.addWidget(self.name_edit)
        else:
            self.index_label.setFixedWidth(50)
            line.addWidget(self.index_label)

        line.addWidget(muted(text="="))

        self.kind_box = QComboBox()
        kind = values.type_of(value=value)
        kinds = list(values.TYPES)

        if kind not in kinds:
            kinds.append(kind)

        self.kind_box.addItems(kinds)
        self.kind_box.setCurrentText(kind)
        self.kind_box.setFixedWidth(140)
        line.addWidget(self.kind_box)

        self.value_slot = QHBoxLayout()
        line.addLayout(self.value_slot, 1)

        if removable:
            remove = flat_button(icon="delete", tip="Remove")
            remove.clicked.connect(lambda _=False: self.remove_requested.emit(self))
            line.addWidget(remove)

        self.children_box = QWidget()
        children = QVBoxLayout(self.children_box)
        children.setContentsMargins(28, 0, 0, 0)
        children.setSpacing(6)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(6)
        children.addLayout(self.rows_layout)
        self.add_child_button = link_button(text="Add field", action=lambda: self.add_child())
        children.addWidget(self.add_child_button)
        outer.addWidget(self.children_box)

        self.child_rows: list[FieldRow] = []
        self.editor: QWidget | None = None
        self.read: Callable[[], Any] | None = None
        self.kind_box.currentTextChanged.connect(self._kind_changed)
        self._show(kind=kind, value=value)

    def kind(self) -> str:
        return self.kind_box.currentText()

    def name(self) -> str | None:
        return self.name_edit.text().strip() if self.name_edit is not None else None

    def _clear(self) -> None:
        if self.editor is not None:
            self.editor.setParent(None)
            self.editor.deleteLater()
            self.editor = None

        for row in self.child_rows:
            row.setParent(None)
            row.deleteLater()

        self.child_rows = []

    def _show(self, kind: str, value: Any) -> None:
        self._clear()

        if kind in values.CONTAINERS:
            self.editor = QWidget()
            self.value_slot.addWidget(self.editor)
            self.children_box.show()
            self.add_child_button.setText("+   Add field" if kind == "map" else "+   Add item")
            items = sorted(value.items()) if kind == "map" else list(enumerate(value))

            for key, item in items:
                self.add_child(key=key, value=item)
        else:
            self.children_box.hide()
            editor = scalar_editor(kind=kind, value=value)
            self.editor, self.read = editor.widget, editor.read
            self.value_slot.addWidget(self.editor)

    def _kind_changed(self, kind: str) -> None:
        same = kind == values.type_of(value=self.original)
        self._show(kind=kind, value=self.original if same else values.default_for(kind=kind))

    def add_child(self, key: str | int = "", value: Any = "") -> FieldRow:
        is_map = self.kind() == "map"
        row = FieldRow(name=str(key) if is_map else "", value=value, named=is_map)
        row.remove_requested.connect(self._remove_child)
        self.rows_layout.addWidget(row)
        self.child_rows.append(row)
        self._relabel()

        if row.name_edit is not None and not key:
            row.name_edit.setFocus()

        return row

    def _remove_child(self, row: FieldRow) -> None:
        self.child_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._relabel()

    def _relabel(self) -> None:
        if self.kind() != "array":
            return

        for index, row in enumerate(self.child_rows):
            row.index_label.setText(str(index))

    def value(self) -> Any:
        kind = self.kind()
        label = self.name() if self.named else "item"

        try:
            if kind == "map":
                return collect_map(rows=self.child_rows)

            if kind == "array":
                items = [row.value() for row in self.child_rows]

                if any(values.type_of(value=item) == "array" for item in items):
                    raise ValueError("an array cannot directly contain another array")

                return items

            return self.read() if self.read is not None else None
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc


# The field list of the add document and start collection dialogs
class FieldsEditor(QScrollArea):
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setMinimumHeight(220)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        layout.addLayout(self.rows_layout)
        layout.addWidget(link_button(text="Add field", action=lambda: self.add_row()))
        layout.addStretch(1)
        self.setWidget(inner)
        self.rows: list[FieldRow] = []

        for name, value in sorted((data or {}).items()):
            self.add_row(name=name, value=value)

        if not self.rows:
            self.add_row()

    def add_row(self, name: str = "", value: Any = "") -> FieldRow:
        row = FieldRow(name=name, value=value)
        row.remove_requested.connect(self._remove)
        self.rows_layout.addWidget(row)
        self.rows.append(row)

        return row

    def _remove(self, row: FieldRow) -> None:
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    # Untouched blank rows are ignored, so a document can be created without fields
    def values(self) -> dict[str, Any]:
        used = [row for row in self.rows if row.name() or row.kind() != "string" or row.value() != ""]

        return collect_map(rows=used)
