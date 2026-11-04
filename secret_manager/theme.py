from __future__ import annotations

from PySide6.QtCore import QByteArray, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

BG = "#202124"
SURFACE = "#292a2d"
HOVER = "#2d2e31"
SELECT = "#37393d"
BORDER = "#4a4e63"
TEXT = "#e8eaed"
MUTED = "#9aa0a6"
ACCENT = "#8ab4f8"
DANGER = "#f28b82"
FONT_PT = 12
MONO = "'Roboto Mono', 'JetBrains Mono', 'DejaVu Sans Mono', monospace"

STYLE = f"""
QFrame#Browser {{ border: 1px solid {BORDER}; border-radius: 8px; }}
QFrame#Breadcrumb {{ border: none; border-bottom: 1px solid {BORDER}; }}
QFrame#Panel {{ border: none; }}
QSplitter::handle:horizontal {{ background: transparent; border-left: 1px solid {BORDER}; }}
QSplitter::handle:horizontal:hover {{ border-left: 2px solid {ACCENT}; }}
QWidget#PanelHeader {{ border-bottom: 1px solid {BORDER}; }}
QFrame#Separator {{ border: none; border-top: 1px solid {BORDER}; }}
QLabel#PanelTitle {{ font-family: {MONO}; font-size: {FONT_PT + 1}pt; }}
QLabel#DialogTitle {{ font-size: {FONT_PT + 4}pt; padding-bottom: 6px; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Note {{ color: {MUTED}; font-style: italic; padding: 10px 16px; }}
QLabel#FilterBar {{ color: {ACCENT}; padding: 6px 16px; background: {SURFACE}; }}
QPushButton#Link {{
    color: {ACCENT}; background: transparent; border: none; text-align: left;
    padding: 8px 16px;
}}
QPushButton#Link:hover {{ background: {HOVER}; }}
QPushButton#Primary {{
    color: {BG}; background: {ACCENT}; border: none; border-radius: 4px; padding: 6px 18px;
}}
QPushButton#Danger {{
    color: {BG}; background: {DANGER}; border: none; border-radius: 4px; padding: 6px 18px;
}}
QPushButton#Primary:disabled, QPushButton#Danger:disabled {{ background: {SELECT}; color: {MUTED}; }}
QToolButton#Flat, QToolButton#Crumb {{
    border: none; background: transparent; border-radius: 4px; padding: 3px 5px;
}}
QToolButton#Flat:hover, QToolButton#Crumb:hover {{ background: {HOVER}; }}
QToolButton#Flat[active="true"] {{ color: {ACCENT}; }}
QToolButton#Crumb {{ font-family: {MONO}; color: {MUTED}; }}
QToolButton#Crumb[current="true"] {{ color: {TEXT}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QListWidget#Items, QTreeWidget#Fields {{
    border: none; background: transparent; font-family: {MONO}; outline: 0;
}}
QListWidget#Items::item {{ padding: 6px 28px 6px 44px; color: {TEXT}; border: none; }}
QListWidget#Items::item:hover {{ background: {HOVER}; }}
QListWidget#Items::item:selected {{ background: {SELECT}; color: {TEXT}; }}
QTreeWidget#Fields::item {{ padding: 5px 0; border: none; color: {TEXT}; }}
QTreeWidget#Fields::item:hover, QTreeWidget#Fields::item:selected {{ background: {SELECT}; }}
QWidget#HoverActions {{ background: {SELECT}; }}
QToolButton#Chip {{
    border: 1px solid {BORDER}; border-radius: 15px; padding: 4px 14px; background: transparent;
    color: {MUTED};
}}
QToolButton#Chip:hover {{ background: {HOVER}; }}
QToolButton#Chip:checked {{ background: #394457; border-color: {ACCENT}; color: {ACCENT}; }}
QLabel#RepoTitle {{ font-family: {MONO}; font-size: {FONT_PT + 3}pt; }}
QLabel#SecretName {{ font-family: {MONO}; color: {TEXT}; }}
QLabel#EmptyTitle {{ font-size: {FONT_PT + 2}pt; color: {TEXT}; }}
QLabel#Count {{ color: {MUTED}; background: {SURFACE}; border-radius: 9px; padding: 1px 8px; }}
QListWidget#Secrets {{ border: none; background: transparent; outline: 0; }}
QListWidget#Secrets::item {{ border: none; border-bottom: 1px solid {SURFACE}; }}
QListWidget#Secrets::item:hover {{ background: {HOVER}; }}
QListWidget#Secrets::item:selected {{ background: {SELECT}; }}
QLineEdit#Search {{ padding: 6px 8px; border-radius: 6px; }}
QWidget#Separator {{ background: {BORDER}; }}
QLabel#Badge {{ border: 1px solid; border-radius: 9px; padding: 1px 8px; }}
QLabel#SectionHeader {{
    color: {MUTED}; font-size: {FONT_PT - 2}pt; font-weight: bold; padding: 10px 0 2px 0;
}}
QLabel#Value {{ font-family: {MONO}; color: {MUTED}; }}
QLabel#Banner {{ color: {BG}; background: #fdd663; padding: 8px 16px; }}
QTreeWidget#Table {{ border: none; background: transparent; outline: 0; }}
QTreeWidget#Table::item {{ padding: 6px 4px; border: none; border-bottom: 1px solid {SURFACE}; }}
QTreeWidget#Table::item:hover {{ background: {HOVER}; }}
QTreeWidget#Table::item:selected {{ background: {SELECT}; color: {TEXT}; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 4px;
}}
QTreeWidget#Plain {{ border: 1px solid {BORDER}; border-radius: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ padding: 8px 18px; background: transparent; color: {MUTED}; border: none; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 6px; margin-top: 14px; padding: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(FONT_PT)
    app.setFont(font)

    palette = QPalette()
    roles: dict[QPalette.ColorRole, str] = {
        QPalette.ColorRole.Window: BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: HOVER,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: SELECT,
        QPalette.ColorRole.HighlightedText: TEXT,
        QPalette.ColorRole.ToolTipBase: SURFACE,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: ACCENT,
        QPalette.ColorRole.Mid: BORDER,
    }

    for role, color in roles.items():
        palette.setColor(role, QColor(color))

    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(MUTED))

    app.setPalette(palette)
    app.setStyleSheet(STYLE)


# Material icon paths (24×24), the set the Firebase console uses
PATHS = {
    "database": "M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z",
    "collection": "M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z",
    "document": "M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z",
    "home": "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
    "add": "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    "edit": "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
    "delete": "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
    "filter": "M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z",
    "more": "M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z",
    "refresh": "M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z",
    "key": "M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z",
    "repo": "M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z",
    "open": "M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z",
    "upload": "M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z",
    "search": "M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
    "lock": "M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z",
    "variable": "M4 7v2c0 .55-.45 1-1 1H2v4h1c.55 0 1 .45 1 1v2c0 1.65 1.35 3 3 3h3v-2H7c-.55 0-1-.45-1-1v-2c0-1.3-.84-2.42-2-2.83v-.34C5.16 11.42 6 10.3 6 9V7c0-.55.45-1 1-1h3V4H7C5.35 4 4 5.35 4 7zm17 3c-.55 0-1-.45-1-1V7c0-1.65-1.35-3-3-3h-3v2h3c.55 0 1 .45 1 1v2c0 1.3.84 2.42 2 2.83v.34c-1.16.41-2 1.52-2 2.83v2c0 .55-.45 1-1 1h-3v2h3c1.65 0 3-1.35 3-3v-2c0-.55.45-1 1-1h1v-4h-1z",
    "org": "M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z",
    "person": "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z",
    "eye": "M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z",
    "copy": "M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z",
    "history": "M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z",
    "tune": "M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z",
    "shield": "M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z",
    "flag": "M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z",
    "info": "M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z",
}
_icons: dict[tuple[str, str], QIcon] = {}


def named_icon(key: str, color: str = MUTED) -> QIcon:
    if (key, color) not in _icons:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path fill="{color}" d="{PATHS[key]}"/></svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode("ascii")))
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        _icons[(key, color)] = QIcon(pixmap)

    return _icons[(key, color)]


# Draws the console's chevron on the selected row
class ChevronDelegate(QStyledItemDelegate):
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, index)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.save()
            painter.setPen(QColor(TEXT))
            font = painter.font()
            font.setPointSizeF(font.pointSizeF() * 1.4)
            painter.setFont(font)
            painter.drawText(
                option.rect.adjusted(0, 0, -14, -2),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "›",
            )
            painter.restore()
