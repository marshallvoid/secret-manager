from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ... import theme
from ...utils.dates import exact_time, relative_time
from ...widgets import badge, flat_button, muted
from .models import VersionAction, VersionInfo

STATE_COLORS: dict[str, str] = {
    "ENABLED": "#81c995",
    "DISABLED": "#fdd663",
    "DESTROYED": theme.DANGER,
}


# Runs after the click, since the list is rebuilt when the change lands
def later(action: Callable[[], None]) -> Callable[[bool], None]:
    return lambda _=False: QTimer.singleShot(0, action)


class VersionRow(QWidget):
    def __init__(
        self,
        version: VersionInfo,
        latest: bool,
        on_view: Callable[[], None],
        on_change: Callable[[VersionAction], None],
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 10, 10)
        layout.setSpacing(12)

        title = QLabel(f"Version {version.number}")
        title.setObjectName("SecretName")
        layout.addWidget(title)

        if latest:
            layout.addWidget(badge(text="latest", color=theme.ACCENT))

        state = version.state
        layout.addWidget(
            badge(text=state.title(), color=STATE_COLORS.get(state, theme.MUTED))
        )
        layout.addStretch(1)

        created = muted(text=relative_time(value=version.created, prefix="Created"))
        created.setToolTip(exact_time(value=version.created))
        layout.addWidget(created)
        layout.addSpacing(8)

        if state == "ENABLED":
            view = flat_button(icon="eye", tip="View the value")
            view.clicked.connect(later(action=on_view))
            layout.addWidget(view)

        if state in ("ENABLED", "DISABLED"):
            action: VersionAction = "disable" if state == "ENABLED" else "enable"
            toggle = QPushButton(action.title())
            toggle.clicked.connect(later(action=lambda: on_change(action)))
            layout.addWidget(toggle)

            destroy = flat_button(icon="delete", tip="Destroy this version")
            destroy.clicked.connect(later(action=lambda: on_change("destroy")))
            layout.addWidget(destroy)
