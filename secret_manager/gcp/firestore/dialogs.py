from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...dialogs import Dialog
from ...widgets import muted
from . import values
from .field_editor import FieldRow, FieldsEditor
from .models import DocumentResult, FieldResult, Query
from .store import LIST_OPERATORS, OPERATORS, auto_id, check_field_name, check_id


class FieldDialog(Dialog):
    def __init__(
        self,
        parent: QWidget,
        title: str,
        name: str = "",
        value: Any = "",
        named: bool = True,
        name_editable: bool = True,
        ok_text: str = "Update",
    ) -> None:
        super().__init__(parent=parent, title=title, ok_text=ok_text)
        self.named = named
        self.row = FieldRow(
            name=name,
            value=value,
            named=named,
            removable=False,
            name_editable=name_editable,
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.addWidget(self.row)
        holder_layout.addStretch(1)
        scroll.setWidget(holder)
        scroll.setMinimumHeight(140)
        self.content.addWidget(scroll)

        if self.row.name_edit is not None and not name:
            self.row.name_edit.setFocus()

    def build(self) -> FieldResult:
        name = self.row.name()

        if self.named:
            problem = check_field_name(name=name)

            if problem:
                raise ValueError(problem)

        return FieldResult(name=name, value=self.row.value())

    def ask(self) -> FieldResult | None:
        return super().ask()


class DocumentDialog(Dialog):
    def __init__(
        self,
        parent: QWidget,
        title: str,
        parent_path: str,
        ask_collection: bool = False,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent=parent, title=title, ok_text="Save", width=760)
        self.resize(760, 560)
        self.ask_collection = ask_collection

        form = QFormLayout()
        form.addRow("Parent path", muted(text=parent_path or "/"))
        self.collection_edit = QLineEdit()

        if ask_collection:
            self.collection_edit.setPlaceholderText("Collection ID")
            form.addRow("Collection ID", self.collection_edit)

        id_row = QHBoxLayout()
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("Leave empty for an auto-ID")
        auto = QPushButton("Auto-ID")
        auto.clicked.connect(lambda _=False: self.id_edit.setText(auto_id()))
        id_row.addWidget(self.id_edit, 1)
        id_row.addWidget(auto)
        form.addRow("Document ID", id_row)
        self.content.addLayout(form)

        self.fields = FieldsEditor(data=data)
        self.content.addWidget(self.fields, 1)
        (self.collection_edit if ask_collection else self.id_edit).setFocus()

    def build(self) -> DocumentResult:
        collection = self.collection_edit.text().strip()

        if self.ask_collection:
            problem = check_id(name=collection)

            if problem:
                raise ValueError(f"Collection ID: {problem}")

        doc_id = self.id_edit.text().strip() or auto_id()
        problem = check_id(name=doc_id)

        if problem:
            raise ValueError(f"Document ID: {problem}")

        return DocumentResult(
            collection=collection, doc_id=doc_id, data=self.fields.values()
        )

    def ask(self) -> DocumentResult | None:
        return super().ask()


# Returns the new query; an inactive query clears the filter
class FilterDialog(Dialog):
    def __init__(
        self, parent: QWidget, collection: str, query: Query | None = None
    ) -> None:
        super().__init__(parent=parent, title=f"Filter {collection}", ok_text="Apply")
        query = query or Query()

        self.filter_box = QGroupBox("Filter by field")
        self.filter_box.setCheckable(True)
        self.filter_box.setChecked(bool(query.field))
        form = QFormLayout(self.filter_box)
        self.field_edit = QLineEdit(query.field)
        self.field_edit.setPlaceholderText("field or map.field")
        self.op_box = QComboBox()
        self.op_box.addItems(list(OPERATORS))
        self.op_box.setCurrentText(query.op)
        start = query.value if query.field else ""
        self.value_row = FieldRow(value=start, named=False, removable=False)
        form.addRow("Field", self.field_edit)
        form.addRow("Condition", self.op_box)
        form.addRow("Value", self.value_row)
        self.content.addWidget(self.filter_box)

        self.sort_box = QGroupBox("Sort results")
        self.sort_box.setCheckable(True)
        self.sort_box.setChecked(bool(query.order))
        sort_form = QFormLayout(self.sort_box)
        self.order_edit = QLineEdit(query.order)
        self.direction_box = QComboBox()
        self.direction_box.addItems(["Ascending", "Descending"])
        self.direction_box.setCurrentIndex(1 if query.descending else 0)
        sort_form.addRow("Field", self.order_edit)
        sort_form.addRow("Direction", self.direction_box)
        self.content.addWidget(self.sort_box)
        self.content.addWidget(
            muted(
                text="Filters and sorting may need an index. "
                "Documents without the sorted field are left out."
            )
        )

        clear = QPushButton("Clear filter")
        clear.clicked.connect(self._clear)
        self.buttons.insertWidget(0, clear)

    def _clear(self) -> None:
        self.result_value = Query()
        self.accept()

    def build(self) -> Query:
        query = Query()

        if self.filter_box.isChecked():
            field = self.field_edit.text().strip()

            if not field:
                raise ValueError("Enter the field to filter by.")

            op = self.op_box.currentText()
            value = self.value_row.value()
            is_list = values.type_of(value=value) == "array"

            if op in LIST_OPERATORS and (not is_list or not 0 < len(value) <= 30):
                raise ValueError(f"'{op}' needs an array of 1 to 30 values.")

            query = query.model_copy(update={"field": field, "op": op, "value": value})

        if self.sort_box.isChecked():
            order = self.order_edit.text().strip()

            if not order:
                raise ValueError("Enter the field to sort by.")

            descending = self.direction_box.currentIndex() == 1
            query = query.model_copy(update={"order": order, "descending": descending})

        return query

    def ask(self) -> Query | None:
        return super().ask()
