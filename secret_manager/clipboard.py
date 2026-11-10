from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

CLEAR_SECONDS = 30


# Copies a value and clears it again after a while, unless something else was copied since
class ClipboardGuard:
    def __init__(self) -> None:
        self.generation = 0

    def copy(self, text: str, seconds: int = CLEAR_SECONDS) -> None:
        QGuiApplication.clipboard().setText(text)
        self.generation += 1
        generation = self.generation
        QTimer.singleShot(seconds * 1000, lambda: self._clear(generation=generation, text=text))

    def _clear(self, generation: int, text: str) -> None:
        clipboard = QGuiApplication.clipboard()

        if generation == self.generation and clipboard.text() == text:
            clipboard.clear()


GUARD = ClipboardGuard()


def copy_secret(text: str) -> str:
    GUARD.copy(text=text)

    return f"Copied; the clipboard clears in {CLEAR_SECONDS} seconds"
