from __future__ import annotations

import html
import re
from typing import List

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel

from . import theme

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


class LinkLabel(QLabel):
    """Render plain messages safely, making only HTTP(S) URLs actionable."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        self.linkActivated.connect(self._open_link)
        self.setText(text)

    def setText(self, text: str) -> None:
        parts: List[str] = []
        offset = 0

        for match in URL_PATTERN.finditer(string=text):
            url = match.group().rstrip(".,;:!?) ]}")
            parts.append(html.escape(s=text[offset : match.start()]))
            escaped = html.escape(s=url, quote=True)
            parts.append(f'<a href="{escaped}" style="color: {theme.ACCENT};">{escaped}</a>')
            offset = match.start() + len(url)

        parts.append(html.escape(s=text[offset:]))
        super().setText("".join(parts).replace("\n", "<br>"))

    def _open_link(self, url: str) -> None:
        target = QUrl(url)

        if target.scheme() in ("http", "https"):
            QDesktopServices.openUrl(target)
