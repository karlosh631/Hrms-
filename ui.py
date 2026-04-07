"""
ui.py – System-tray icon, permission popup, and manual action buttons.

Requires PyQt5.  Falls back gracefully when a display is not available.
"""

import logging
import sys
from datetime import date
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import – PyQt5 may be absent in headless environments
# ---------------------------------------------------------------------------
try:
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject  # type: ignore
    from PyQt5.QtGui import QIcon, QPixmap, QColor  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QApplication,
        QDialog,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QPushButton,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )
    _HAS_QT = True
except ImportError:
    _HAS_QT = False
    logger.warning("PyQt5 not available – UI features disabled.")


# ---------------------------------------------------------------------------
# QApplication singleton
# ---------------------------------------------------------------------------

_app: Optional[object] = None


def get_app():
    global _app
    if not _HAS_QT:
        return None
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


# ---------------------------------------------------------------------------
# Permission popup
# ---------------------------------------------------------------------------

def ask_permission(day: date, on_result: Callable[[bool], None]) -> None:
    """
    Show the 8 AM permission dialog.
    Calls *on_result(True)* if user clicks YES, *on_result(False)* otherwise.
    Falls back to a console prompt when Qt is unavailable.
    """
    if not _HAS_QT:
        _console_ask_permission(day, on_result)
        return

    app = get_app()

    dialog = _PermissionDialog(day)
    result = dialog.exec_()  # blocks until user responds
    granted = result == QDialog.Accepted
    logger.info("Permission dialog closed – granted=%s", granted)
    on_result(granted)


def _console_ask_permission(day: date, on_result: Callable[[bool], None]) -> None:
    try:
        answer = input(
            f"\n[HRMS AutoAttendance] Enable auto clock-in/out for {day}? [y/N]: "
        ).strip().lower()
        on_result(answer in ("y", "yes"))
    except EOFError:
        logger.warning("No TTY – defaulting permission to NO")
        on_result(False)


# ---------------------------------------------------------------------------
# Permission dialog widget
# ---------------------------------------------------------------------------

class _PermissionDialog(QDialog if _HAS_QT else object):  # type: ignore[misc]
    def __init__(self, day: date):
        super().__init__(None, Qt.WindowStaysOnTopHint)  # type: ignore[arg-type]
        self.setWindowTitle("HRMS Auto Attendance")
        self.setMinimumWidth(380)
        self._build_ui(day)

    def _build_ui(self, day: date) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("<b>HRMS Auto Attendance</b>")
        title.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(title)

        msg = QLabel(
            f"Enable auto clock-in and clock-out for today?\n({day.strftime('%A, %d %B %Y')})"
        )
        msg.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_layout = QHBoxLayout()
        yes_btn = QPushButton("✔ YES")
        no_btn = QPushButton("✘ NO")
        yes_btn.setFixedHeight(36)
        no_btn.setFixedHeight(36)

        yes_btn.clicked.connect(self.accept)
        no_btn.clicked.connect(self.reject)

        btn_layout.addWidget(yes_btn)
        btn_layout.addWidget(no_btn)
        layout.addLayout(btn_layout)


# ---------------------------------------------------------------------------
# System tray icon
# ---------------------------------------------------------------------------

class TrayApp:
    """Manages the system tray icon and optional status window."""

    def __init__(
        self,
        on_clock_in: Optional[Callable] = None,
        on_clock_out: Optional[Callable] = None,
    ):
        self._on_clock_in = on_clock_in
        self._on_clock_out = on_clock_out
        self._tray: Optional[object] = None
        self._window: Optional[object] = None

        if not _HAS_QT:
            logger.warning("TrayApp: PyQt5 unavailable – tray icon disabled.")
            return

        app = get_app()
        self._tray = self._create_tray()

    def _create_tray(self):
        icon = self._make_icon()
        tray = QSystemTrayIcon(icon)
        tray.setToolTip("HRMS AutoAttendance")
        tray.setContextMenu(self._build_menu())
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _make_icon(self):
        """Create a simple coloured square as the tray icon."""
        px = QPixmap(32, 32)
        px.fill(QColor("#1a73e8"))
        return QIcon(px)

    def _build_menu(self):
        menu = QMenu()

        status_action = menu.addAction("Today: checking …")
        status_action.setEnabled(False)
        self._status_action = status_action

        menu.addSeparator()

        ci = menu.addAction("Clock-in now")
        ci.triggered.connect(self._manual_clock_in)

        co = menu.addAction("Clock-out now")
        co.triggered.connect(self._manual_clock_out)

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)

        return menu

    def update_status(self, text: str) -> None:
        if self._status_action:
            self._status_action.setText(text)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:  # type: ignore[attr-defined]
            self._show_status_window()

    def _show_status_window(self) -> None:
        import storage
        today = date.today()
        tasks = storage.get_tasks_for_day(today)
        perm = storage.get_permission(today)

        lines = [f"<b>HRMS AutoAttendance – {today}</b>"]
        lines.append(f"Permission: {'✔ Enabled' if perm else ('✘ Disabled' if perm is False else '—')}")
        lines.append("")
        for t in tasks:
            lines.append(
                f"{t['action_type'].replace('_', ' ').title()}: "
                f"{t['status']}  (retries: {t['retries']})"
            )

        if self._window is None:
            self._window = _StatusWindow("\n".join(lines))
        else:
            self._window.update_text("<br>".join(lines))  # type: ignore[union-attr]
        self._window.show()  # type: ignore[union-attr]
        self._window.raise_()  # type: ignore[union-attr]

    def _manual_clock_in(self) -> None:
        if self._on_clock_in:
            self._on_clock_in()

    def _manual_clock_out(self) -> None:
        if self._on_clock_out:
            self._on_clock_out()

    def _quit(self) -> None:
        if _HAS_QT:
            QApplication.quit()

    def run_event_loop(self) -> None:
        """Start the Qt event loop (blocking)."""
        if _HAS_QT:
            get_app().exec_()  # type: ignore[union-attr]
        else:
            # No GUI – just block the main thread
            import time
            logger.info("Running in headless mode (no Qt). Press Ctrl+C to exit.")
            while True:
                time.sleep(60)


class _StatusWindow(QMainWindow if _HAS_QT else object):  # type: ignore[misc]
    def __init__(self, text: str):
        super().__init__()
        self.setWindowTitle("HRMS Status")
        self.setMinimumWidth(320)
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)
        self._label = QLabel(text.replace("\n", "<br>"))
        self._label.setTextFormat(Qt.RichText)  # type: ignore[attr-defined]
        self._label.setAlignment(Qt.AlignTop)  # type: ignore[attr-defined]
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

    def update_text(self, text: str) -> None:
        """Update the displayed status text (HTML supported)."""
        self._label.setText(text)
