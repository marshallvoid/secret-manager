from __future__ import annotations

from typing import Generic, Optional, TypeVar

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .widgets import muted

DialogResult = TypeVar("DialogResult")


# A dialog whose `build` turns the inputs into a result; a ValueError keeps it open
class Dialog(QDialog, Generic[DialogResult]):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        ok_text: str = "Save",
        danger: bool = False,
        width: int = 640,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.result_value: Optional[DialogResult] = None

        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(24, 24, 24, 24)
        self.layout_.setSpacing(16)
        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        self.layout_.addWidget(heading)

        self.content = QVBoxLayout()
        self.content.setSpacing(12)
        self.layout_.addLayout(self.content, 1)

        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(12)
        self.buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton(ok_text)
        self.ok.setObjectName("Danger" if danger else "Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._accept)
        self.buttons.addWidget(cancel)
        self.buttons.addWidget(self.ok)
        self.layout_.addLayout(self.buttons)

    def build(self) -> DialogResult:
        raise NotImplementedError

    def _accept(self) -> None:
        try:
            self.result_value = self.build()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

            return

        self.accept()

    def ask(self) -> Optional[DialogResult]:
        accepted = self.exec() == QDialog.DialogCode.Accepted

        return self.result_value if accepted else None


class ConfirmDialog(Dialog[bool]):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        text: str,
        confirm: str | None = None,
        ok_text: str = "Delete",
    ) -> None:
        super().__init__(parent=parent, title=title, ok_text=ok_text, danger=True, width=480)
        label = QLabel(text)
        label.setWordWrap(True)
        self.content.addWidget(label)

        # some deletes ask the user to type the name, like the Firebase console
        if confirm:
            self.content.addWidget(muted(text=f"Type {confirm} to confirm"))
            self.edit = QLineEdit()
            self.edit.textChanged.connect(lambda text: self.ok.setEnabled(text == confirm))
            self.content.addWidget(self.edit)
            self.ok.setEnabled(False)
            self.edit.setFocus()

    def build(self) -> bool:
        return True

    def ask(self) -> bool:
        return bool(super().ask())


def ask_yes_no(parent: QWidget, title: str, text: str) -> bool:
    answer = QMessageBox.question(parent, title, text)

    return answer == QMessageBox.StandardButton.Yes
