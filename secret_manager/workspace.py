from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from . import theme


class WorkspaceHeader(QFrame):
    """Keep the app identity separate from provider and service navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AppHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(16)

        mark = QLabel()
        mark.setPixmap(theme.named_icon(key="shield", color=theme.ACCENT).pixmap(36, 36))
        layout.addWidget(mark)

        titles = QVBoxLayout()
        titles.setSpacing(4)
        title = QLabel("Secret Manager")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Cloud resources, secrets & configuration")
        subtitle.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        layout.addLayout(titles, 1)
