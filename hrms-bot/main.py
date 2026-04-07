"""
main.py – Entry point for the HRMS Auto Attendance Bot.

Desktop mode  (default, Windows / Mac / Linux with display):
    python main.py

Cloud/headless mode (Linux server, Docker, Raspberry Pi):
    HRMS_CLOUD_MODE=true python main.py
    HRMS_AUTO_APPROVE=true python main.py    # skip the 8 AM popup entirely

Run once (no tray, just execute now and exit):
    python main.py --clock-in
    python main.py --clock-out
"""
import argparse
import logging
import signal
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from config import APP_NAME, APP_VERSION, CLOUD_MODE, CLOUD_API_PORT, AUTO_APPROVE
from storage import Storage
from scheduler import HRMSScheduler
from utils import check_missed_tasks, setup_autostart, setup_logging

logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    p.add_argument("--clock-in",      action="store_true", help="Perform clock-in now and exit")
    p.add_argument("--clock-out",     action="store_true", help="Perform clock-out now and exit")
    p.add_argument("--enable-autostart",  action="store_true", help="Register auto-start on boot")
    p.add_argument("--disable-autostart", action="store_true", help="Remove auto-start on boot")
    p.add_argument("--debug",         action="store_true", help="Enable DEBUG logging")
    return p.parse_args()


def one_shot_action(action: str) -> int:
    """Execute a single clock action immediately and return exit code."""
    from hrms_bot import HRMSBot
    from utils import is_online

    if not is_online():
        print(f"[ERROR] No internet connection – cannot {action}.")
        return 1

    with HRMSBot() as bot:
        success = bot.clock_in() if action == "clock_in" else bot.clock_out()
    label = action.replace("_", " ").title()
    if success:
        print(f"[OK] {label} completed successfully.")
        return 0
    else:
        print(f"[FAIL] {label} failed.  Check data/screenshots/ for details.")
        return 1


def run_desktop_mode(scheduler: "HRMSScheduler", storage: "Storage") -> None:
    """Run with a PyQt5 event loop + system tray."""
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication

    from ui import create_tray_app

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)
    qt_app.setApplicationName(APP_NAME)

    tray = create_tray_app(scheduler, storage)
    tray.show()

    # Allow Ctrl-C to work inside the Qt event loop
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    def _quit(*_):
        logger.info("Shutdown requested …")
        scheduler.stop()
        qt_app.quit()

    signal.signal(signal.SIGINT,  _quit)
    signal.signal(signal.SIGTERM, _quit)

    logger.info("%s v%s started (desktop mode). Press Ctrl-C to exit.", APP_NAME, APP_VERSION)
    sys.exit(qt_app.exec_())


def run_headless_mode(scheduler: "HRMSScheduler", storage: "Storage") -> None:
    """Run without a display: scheduler + cloud API + signal loop."""
    from ui import HeadlessTrayApp
    from cloud_api import run_cloud_api

    tray = HeadlessTrayApp(scheduler, storage)
    tray.show()

    run_cloud_api(scheduler, storage, port=CLOUD_API_PORT)

    logger.info(
        "%s v%s started (headless/cloud mode, port %d). SIGINT/SIGTERM to exit.",
        APP_NAME, APP_VERSION, CLOUD_API_PORT,
    )

    stop_event = threading.Event()

    def _quit(*_):
        logger.info("Shutdown requested …")
        scheduler.stop()
        stop_event.set()

    import threading
    signal.signal(signal.SIGINT,  _quit)
    signal.signal(signal.SIGTERM, _quit)

    while not stop_event.is_set():
        time.sleep(1)


def main() -> None:
    import threading  # noqa: F401 – ensure available in nested scopes

    args = parse_args()
    setup_logging(level=logging.DEBUG if args.debug else logging.INFO)

    logger.info("=" * 60)
    logger.info("  %s  v%s", APP_NAME, APP_VERSION)
    logger.info("=" * 60)

    # ── Auto-start management (and exit) ──────────────────────────────────────
    if args.enable_autostart:
        ok = setup_autostart(True)
        print("Auto-start enabled." if ok else "Auto-start setup failed.")
        sys.exit(0 if ok else 1)

    if args.disable_autostart:
        ok = setup_autostart(False)
        print("Auto-start disabled." if ok else "Auto-start removal failed.")
        sys.exit(0 if ok else 1)

    # ── One-shot actions (no tray, no scheduler) ──────────────────────────────
    if args.clock_in:
        sys.exit(one_shot_action("clock_in"))
    if args.clock_out:
        sys.exit(one_shot_action("clock_out"))

    # ── Normal / daemon mode ──────────────────────────────────────────────────
    storage   = Storage()
    storage.init_db()

    # Recover any tasks that were missed (e.g. PC was off)
    check_missed_tasks(storage)

    # If AUTO_APPROVE is set and permission not yet decided, grant it now
    if AUTO_APPROVE and storage.get_today_permission() is None:
        logger.info("AUTO_APPROVE: granting permission automatically.")
        storage.set_today_permission(True)

    scheduler = HRMSScheduler(storage)
    scheduler.start()

    # Choose display mode
    headless = CLOUD_MODE or not _has_display()

    if headless:
        import threading as _t  # type: ignore
        run_headless_mode(scheduler, storage)
    else:
        run_desktop_mode(scheduler, storage)


def _has_display() -> bool:
    import os, platform
    return (
        platform.system() in ("Windows", "Darwin")
        or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    )


if __name__ == "__main__":
    main()
