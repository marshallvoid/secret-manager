from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ... import theme
from ...dialogs import Dialog
from ...utils.dates import exact_time
from ...widgets import AutoText, flat_button, link_button, muted
from .models import (
    COLOR_HEX,
    TAG_COLORS,
    VALUE_TYPES,
    Condition,
    Parameter,
    ParamValue,
    Template,
    TemplateVersion,
    check_key,
    check_value,
)

EXPRESSION_HINT = (
    "Examples: device.os == 'ios'  ·  app.version.>=(['2.0.0'])  ·  percent <= 10  ·  "
    "app.userProperty['plan'].exactlyMatches(['pro'])"
)


def color_icon(color: str) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(QColor(COLOR_HEX.get(color, theme.MUTED)))

    return QIcon(pixmap)


# An input that fits the parameter's data type
class ValueEditor(QWidget):
    def __init__(self, value_type: str, value: str = "") -> None:
        super().__init__()
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.editor: QWidget | None = None
        self.value_type = value_type
        self.set_type(value_type=value_type, value=value)

    def set_type(self, value_type: str, value: str | None = None) -> None:
        text = self.text() if value is None else value

        if self.editor is not None:
            self.editor.setParent(None)
            self.editor.deleteLater()

        self.value_type = value_type

        if value_type == "BOOLEAN":
            box = QComboBox()
            box.addItems(["true", "false"])
            box.setCurrentIndex(1 if text == "false" else 0)
            self.editor = box
        elif value_type == "NUMBER":
            self.editor = QLineEdit(text)
        else:
            self.editor = AutoText(text=text)

        self.layout_.addWidget(self.editor)

    def text(self) -> str:
        if isinstance(self.editor, QComboBox):
            return self.editor.currentText()

        if isinstance(self.editor, QLineEdit):
            return self.editor.text().strip()

        if isinstance(self.editor, QPlainTextEdit):
            return self.editor.toPlainText()

        return ""


# The default value, or the value for one condition
class ValueRow(QWidget):
    def __init__(
        self,
        value_type: str,
        value: ParamValue,
        conditions: list[str] | None = None,
        condition: str = "",
    ) -> None:
        super().__init__()
        self.original = value
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.condition_box: QComboBox | None = None
        self.editor: ValueEditor | None = None
        self.in_app: QCheckBox | None = None

        if conditions is not None:
            self.condition_box = QComboBox()
            self.condition_box.addItems(conditions)
            self.condition_box.setCurrentText(condition)
            self.condition_box.setFixedWidth(200)
            layout.addWidget(self.condition_box)

        if value.is_raw():
            layout.addWidget(muted(text=f"{value.describe()}  kept as it is"), 1)
        else:
            editor = ValueEditor(value_type=value_type, value=value.value or "")
            in_app = QCheckBox("In-app default")
            in_app.setChecked(bool(value.use_in_app_default))
            in_app.toggled.connect(lambda on: editor.setEnabled(not on))
            editor.setEnabled(not value.use_in_app_default)
            layout.addWidget(editor, 1)
            layout.addWidget(in_app)
            self.editor, self.in_app = editor, in_app

        self.remove = flat_button(icon="delete", tip="Remove")
        layout.addWidget(self.remove)

    def condition(self) -> str:
        return (
            self.condition_box.currentText() if self.condition_box is not None else ""
        )

    def set_type(self, value_type: str) -> None:
        if self.editor is not None:
            self.editor.set_type(value_type=value_type)

    def value(self, value_type: str) -> ParamValue:
        if self.editor is None:
            return self.original

        if self.in_app is not None and self.in_app.isChecked():
            return ParamValue(use_in_app_default=True)

        text = self.editor.text()
        problem = check_value(value_type=value_type, value=text)

        if problem:
            where = (
                f"Value for {self.condition()}" if self.condition() else "Default value"
            )

            raise ValueError(f"{where}: {problem}")

        return ParamValue(value=text)


class ParameterDialog(Dialog):
    def __init__(
        self, parent: QWidget, template: Template, param: Parameter | None
    ) -> None:
        title = f"Edit {param.key}" if param else "Add a parameter"
        super().__init__(parent=parent, title=title, ok_text="Save", width=820)
        self.resize(820, 620)
        self.template = template
        self.original = param
        param = param or Parameter(key="", default=ParamValue(value=""))

        form = QFormLayout()
        self.key_edit = QLineEdit(param.key)
        self.key_edit.setPlaceholderText("parameter_key")
        form.addRow("Key", self.key_edit)

        self.type_box = QComboBox()
        self.type_box.addItems(VALUE_TYPES)
        self.type_box.setCurrentText(param.value_type)
        self.type_box.currentTextChanged.connect(self._type_changed)
        form.addRow("Data type", self.type_box)

        self.description = QLineEdit(param.description)
        self.description.setPlaceholderText("Optional")
        form.addRow("Description", self.description)

        self.group_box = QComboBox()
        self.group_box.setEditable(True)
        self.group_box.addItems(["", *sorted(template.groups)])
        self.group_box.setCurrentText(param.group)
        self.group_box.lineEdit().setPlaceholderText("No group")
        form.addRow("Group", self.group_box)
        self.content.addLayout(form)

        self.content.addWidget(QLabel("Default value"))
        default = param.default or ParamValue(value="")
        self.default_row = ValueRow(value_type=param.value_type, value=default)
        self.default_row.remove.hide()
        self.content.addWidget(self.default_row)

        self.content.addWidget(QLabel("Conditional values"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 8, 0)
        self.rows_layout = QVBoxLayout()
        holder_layout.addLayout(self.rows_layout)
        self.add_button = link_button(
            text="Add value for condition", action=self._add_empty_row
        )
        self.add_button.setEnabled(bool(template.conditions))
        holder_layout.addWidget(self.add_button)

        if not template.conditions:
            holder_layout.addWidget(
                muted(text="Add a condition on the Conditions tab first.")
            )

        holder_layout.addStretch(1)
        scroll.setWidget(holder)
        self.content.addWidget(scroll, 1)

        self.rows: list[ValueRow] = []

        for condition, value in param.conditional.items():
            self._add_row(condition=condition, value=value)

        self.key_edit.setFocus()

    def _add_empty_row(self) -> None:
        used = {row.condition() for row in self.rows}
        free = [name for name in self.template.condition_names() if name not in used]
        self._add_row(condition=free[0] if free else "", value=ParamValue(value=""))

    def _add_row(self, condition: str, value: ParamValue) -> None:
        row = ValueRow(
            value_type=self.type_box.currentText(),
            value=value,
            conditions=self.template.condition_names(),
            condition=condition,
        )
        row.remove.clicked.connect(lambda _=False: self._remove_row(row=row))
        self.rows_layout.addWidget(row)
        self.rows.append(row)

    def _remove_row(self, row: ValueRow) -> None:
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _type_changed(self, value_type: str) -> None:
        self.default_row.set_type(value_type=value_type)

        for row in self.rows:
            row.set_type(value_type=value_type)

    def build(self) -> Parameter:
        key = self.key_edit.text().strip()
        problem = check_key(key=key)

        if problem:
            raise ValueError(problem)

        existing = self.template.parameter(key=key)

        if existing is not None and existing is not self.original:
            raise ValueError(f"A parameter named {key} already exists.")

        value_type = self.type_box.currentText()
        conditional: dict[str, ParamValue] = {}

        for row in self.rows:
            if row.condition() in conditional:
                raise ValueError(f"The condition {row.condition()} is used twice.")

            conditional[row.condition()] = row.value(value_type=value_type)

        return Parameter(
            key=key,
            value_type=value_type,
            description=self.description.text().strip(),
            group=self.group_box.currentText().strip(),
            default=self.default_row.value(value_type=value_type),
            conditional=conditional,
        )

    def ask(self) -> Parameter | None:
        return super().ask()


class ConditionDialog(Dialog):
    def __init__(
        self, parent: QWidget, template: Template, condition: Condition | None
    ) -> None:
        title = f"Edit {condition.name}" if condition else "Add a condition"
        super().__init__(parent=parent, title=title, ok_text="Save", width=720)
        self.template = template
        self.original = condition
        condition = condition or Condition(name="", expression="", tag_color="BLUE")

        form = QFormLayout()
        self.name_edit = QLineEdit(condition.name)
        form.addRow("Name", self.name_edit)

        self.color_box = QComboBox()

        for color in TAG_COLORS:
            self.color_box.addItem(
                color_icon(color=color), color.replace("_", " ").title(), color
            )

        if condition.tag_color in TAG_COLORS:
            self.color_box.setCurrentIndex(TAG_COLORS.index(condition.tag_color))

        form.addRow("Color", self.color_box)
        self.content.addLayout(form)

        self.content.addWidget(QLabel("Expression"))
        self.expression = QPlainTextEdit(condition.expression)
        self.expression.setStyleSheet(f"font-family: {theme.MONO};")
        self.expression.setMinimumHeight(120)
        self.content.addWidget(self.expression, 1)

        hint = muted(text=EXPRESSION_HINT)
        hint.setWordWrap(True)
        self.content.addWidget(hint)
        self.name_edit.setFocus()

    def build(self) -> Condition:
        name = self.name_edit.text().strip()
        expression = self.expression.toPlainText().strip()

        if not name:
            raise ValueError("A condition needs a name.")

        taken = [
            condition
            for condition in self.template.conditions
            if condition.name == name and condition is not self.original
        ]

        if taken:
            raise ValueError(f"A condition named {name} already exists.")

        if not expression:
            raise ValueError("A condition needs an expression.")

        return Condition(
            name=name, expression=expression, tag_color=self.color_box.currentData()
        )

    def ask(self) -> Condition | None:
        return super().ask()


class VersionsDialog(Dialog):
    def __init__(self, parent: QWidget, versions: list[TemplateVersion]) -> None:
        super().__init__(
            parent=parent, title="Template versions", ok_text="Roll back", width=900
        )
        self.resize(900, 520)
        self.versions = versions

        self.table = QTreeWidget()
        self.table.setObjectName("Table")
        self.table.setRootIsDecorated(False)
        self.table.setHeaderLabels(
            ["Version", "Published", "By", "Origin", "Description"]
        )
        self.table.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for version in versions:
            description = (
                version.description or version.update_type.replace("_", " ").title()
            )
            QTreeWidgetItem(
                self.table,
                [
                    version.version_number,
                    exact_time(value=version.update_time),
                    version.update_user.email,
                    version.update_origin.replace("_", " ").title(),
                    description,
                ],
            )

        for column in range(4):
            self.table.resizeColumnToContents(column)

        self.content.addWidget(self.table, 1)
        self.content.addWidget(
            muted(
                text="Rolling back publishes the chosen version again as a new version."
            )
        )

    def build(self) -> str:
        item = self.table.currentItem()

        if item is None:
            raise ValueError("Choose the version to roll back to.")

        if self.versions and item.text(0) == self.versions[0].version_number:
            raise ValueError("That is the current version.")

        return item.text(0)

    def ask(self) -> str | None:
        return super().ask()
