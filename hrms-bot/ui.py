"""
ui.py – PyQt5 system-tray application, 8 AM permission popup, and desktop notifications.

Gracefully degrades to headless mode if no display is available (Linux servers, CI).
"""
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# ── Detect headless environment ───────────────────────────────────────────────
import os as _os
import platform as _platform

_HAS_DISPLAY = (
    _platform.system() in ("Windows", "Darwin")
    or bool(_os.environ.get("DISPLAY") or _os.environ.get("WAYLAND_DISPLAY"))
)

if not _HAS_DISPLAY:
    logger.info("No display detected – running in headless/notification-only mode.")


# ── Qt imports (guarded) ─────────────────────────────────────────────────────
_Qt_available = False
if _HAS_DISPLAY:
    try:
        from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
        from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap
        from PyQt5.QtWidgets import (
            QAction,
            QApplication,
            QDialog,
            QDialogButtonBox,
            QHBoxLayout,
            QLabel,
            QMenu,
            QPushButton,
            QSizePolicy,
            QSystemTrayIcon,
            QVBoxLayout,
            QWidget,
        )
        _Qt_available = True
    except ImportError:
        logger.warning("PyQt5 not installed – tray UI disabled.")


# ── Plyer notifications (fallback) ───────────────────────────────────────────
def _plyer_notify(title: str, message: str) -> None:
    try:
        from plyer import notification  # type: ignore
        notification.notify(title=title, message=message, app_name="HRMS Bot", timeout=8)
    except Exception:
        logger.info("[NOTIFICATION] %s – %s", title, message)


# ══════════════════════════════════════════════════════════════════════════════
# HEADLESS MODE  –  no Qt needed
# ══════════════════════════════════════════════════════════════════════════════

class HeadlessTrayApp:
    """
    No-op tray replacement used when there is no display or Qt is unavailable.
    The scheduler is still fully functional; notifications go to the log.
    """
    def __init__(self, scheduler, storage) -> None:
        self._scheduler = scheduler
        self._storage   = storage
        self._scheduler.register_notify_callback(self._notify)
        # In headless mode, auto-approve is handled by config.AUTO_APPROVE
        logger.info("Running in headless mode (no tray UI).")

    def show(self) -> None:
        pass  # nothing to show

    def _notify(self, title: str, message: str) -> None:
        _plyer_notify(title, message)


# ══════════════════════════════════════════════════════════════════════════════
# FULL GUI MODE
# ══════════════════════════════════════════════════════════════════════════════

if _Qt_available:

    def _make_tray_icon(color_name: str = "#4f8ef7") -> "QIcon":
        """Create a 22×22 colored circle icon for the system tray."""
        size = 22
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        from PyQt5.QtGui import QPainter, QBrush
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(color_name)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)
        painter.end()
        return QIcon(pixmap)


    class _SignalBridge(QObject):
        """Lets background scheduler threads safely invoke Qt slots on the main thread."""
        show_permission_popup = pyqtSignal()
        show_notification     = pyqtSignal(str, str)


    class PermissionDialog(QDialog):
        """
        8 AM modal dialog:
          "Enable auto clock-in and clock-out for today?"
          [YES]  [NO]
        """
        def __init__(self, parent: Optional["QWidget"] = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("HRMS Auto Attendance")
            self.setWindowFlags(
                Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
            )
            self.setFixedWidth(360)
            self._build_ui()

        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(28, 28, 28, 24)
            root.setSpacing(16)

            # Header
            header = QLabel("⏰  HRMS Attendance")
            header.setAlignment(Qt.AlignCenter)
            font = header.font()
            font.setBold(True)
            font.setPointSize(13)
            header.setFont(font)
            root.addWidget(header)

            # Body
            body = QLabel(
                "Enable <b>auto clock-in</b> (10:00 AM) and "
                "<b>auto clock-out</b> (5:05 PM) for today?"
            )
            body.setWordWrap(True)
            body.setAlignment(Qt.AlignCenter)
            root.addWidget(body)

            # Buttons
            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)

            self._btn_yes = QPushButton("✅  YES")
            self._btn_no  = QPushButton("❌  NO")
            for btn, color in (
                (self._btn_yes, "#27ae60"),
                (self._btn_no,  "#e74c3c"),
            ):
                btn.setFixedHeight(40)
                btn.setStyleSheet(
                    f"QPushButton {{ background:{color}; color:white; border:none;"
                    f" border-radius:8px; font-size:14px; font-weight:bold; }}"
                    f"QPushButton:hover {{ opacity:0.85; }}"
                )
            btn_row.addWidget(self._btn_yes)
            btn_row.addWidget(self._btn_no)
            root.addLayout(btn_row)

            self._btn_yes.clicked.connect(self.accept)
            self._btn_no.clicked.connect(self.reject)

        @property
        def granted(self) -> bool:
            return self.result() == QDialog.Accepted


    class SystemTrayApp(QSystemTrayIcon):
        """
        Full system-tray application.

        • Shows a colour-coded icon (green = enabled, red = disabled, grey = pending).
        • Pops the permission dialog at 8 AM via signal from the scheduler thread.
        • Provides manual clock-in/out actions in the context menu.
        """

        def __init__(self, scheduler, storage, parent: Optional["QWidget"] = None) -> None:
            icon = _make_tray_icon("#7f8c8d")  # grey = not yet decided
            super().__init__(icon, parent)

            self._scheduler = scheduler
            self._storage   = storage
            self._bridge    = _SignalBridge()

            # Wire signals (cross-thread safe)
            self._bridge.show_permission_popup.connect(self._on_show_permission_popup)
            self._bridge.show_notification.connect(self._on_show_notification)

            # Register callbacks with the scheduler
            scheduler.register_permission_callback(
                lambda: self._bridge.show_permission_popup.emit()
            )
            scheduler.register_notify_callback(
                lambda t, m: self._bridge.show_notification.emit(t, m)
            )

            self._build_menu()
            self.setToolTip("HRMS Auto Attendance")

        def show(self) -> None:
            super().show()
            logger.info("System tray icon shown.")

        # ── Menu ────────────────────────────────────────────────────────────

        def _build_menu(self) -> None:
            menu = QMenu()

            # Status row
            self._status_action = QAction("Status: checking …", menu)
            self._status_action.setEnabled(False)
            menu.addAction(self._status_action)
            menu.addSeparator()

            # Manual actions
            clock_in_action  = QAction("▶  Clock In now", menu)
            clock_out_action = QAction("■  Clock Out now", menu)
            clock_in_action.triggered.connect(self._scheduler.manual_clock_in)
            clock_out_action.triggered.connect(self._scheduler.manual_clock_out)
            menu.addAction(clock_in_action)
            menu.addAction(clock_out_action)
            menu.addSeparator()

            # Today's log
            self._tasks_action = QAction("Today's log: (loading)", menu)
            self._tasks_action.setEnabled(False)
            menu.addAction(self._tasks_action)
            menu.addSeparator()

            # Quit
            quit_action = QAction("Quit", menu)
            quit_action.triggered.connect(QApplication.instance().quit)
            menu.addAction(quit_action)

            self.setContextMenu(menu)

            # Refresh status every 30 s
            self._timer = QTimer()
            self._timer.timeout.connect(self._refresh_status)
            self._timer.start(30_000)
            self._refresh_status()

        def _refresh_status(self) -> None:
            perm = self._storage.get_today_permission()
            if perm is True:
                label  = "Today: Automation ENABLED ✅"
                color  = "#27ae60"
            elif perm is False:
                label  = "Today: Automation DISABLED ❌"
                color  = "#e74c3c"
            else:
                label  = "Today: Waiting for 8 AM decision …"
                color  = "#f39c12"

            self._status_action.setText(label)
            self.setIcon(_make_tray_icon(color))
            self.setToolTip(f"HRMS Bot – {label}")

            tasks = self._storage.get_today_tasks()
            if tasks:
                lines = []
                for t in tasks:
                    lines.append(
                        f"  {t['action_type']} → {t['status']} "
                        f"({t.get('retry_count', 0)} retries)"
                    )
                self._tasks_action.setText("Today:\n" + "\n".join(lines))
            else:
                self._tasks_action.setText("Today: no tasks yet.")

        # ── Slots (called on main thread) ────────────────────────────────────

        @pyqtSlot()
        def _on_show_permission_popup(self) -> None:
            # Double-check; another job might have already set it
            if self._storage.get_today_permission() is not None:
                return
            dlg = PermissionDialog()
            dlg.exec_()
            granted = dlg.granted
            self._storage.set_today_permission(granted)
            self._refresh_status()
            msg = "Automation ENABLED for today ✅" if granted else "Automation DISABLED for today ❌"
            self._on_show_notification("HRMS Auto Attendance", msg)
            logger.info("Permission dialog closed: %s", "YES" if granted else "NO")

        @pyqtSlot(str, str)
        def _on_show_notification(self, title: str, message: str) -> None:
            # Qt tray notification
            try:
                self.showMessage(
                    title, message,
                    QSystemTrayIcon.Information, 6000,
                )
            except Exception:
                pass
            # plyer fallback
            _plyer_notify(title, message)


# ── Public factory ────────────────────────────────────────────────────────────

def create_tray_app(scheduler, storage):
    """
    Return the appropriate tray/headless app based on the environment.
    If Qt is available and a display exists → SystemTrayApp.
    Otherwise                                → HeadlessTrayApp.
    """
    if _Qt_available and _HAS_DISPLAY:
        return SystemTrayApp(scheduler, storage)
    return HeadlessTrayApp(scheduler, storage)
