"""
utils.py – Cross-platform helpers: logging, network check, auto-start setup,
           missed-task recovery, and optional WiFi recovery.
"""
import logging
import logging.handlers
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from config import APP_NAME, LOG_PATH, MAX_RETRIES

if TYPE_CHECKING:
    from storage import Storage

logger = logging.getLogger(__name__)

# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger: rotating file + stderr."""
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        str(LOG_PATH), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "asyncio", "playwright"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.info("Logging started → %s", LOG_PATH)


# ── Network helpers ───────────────────────────────────────────────────────────

def is_online(host: str = "8.8.8.8", port: int = 53, timeout: int = 5) -> bool:
    """Quick TCP probe to check internet connectivity."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.create_connection((host, port)):
            return True
    except OSError:
        return False


def try_enable_wifi() -> bool:
    """
    Attempt to enable WiFi / bring up the network interface.
    Best-effort; returns True if the attempt was made without error.
    """
    system = platform.system()
    try:
        if system == "Windows":
            # Enable first available Wi-Fi adapter
            subprocess.run(
                ["netsh", "interface", "set", "interface", "Wi-Fi", "admin=enable"],
                check=True, capture_output=True, timeout=10,
            )
            logger.info("WiFi enable command sent (Windows)")
            return True

        elif system == "Darwin":
            subprocess.run(
                ["networksetup", "-setairportpower", "en0", "on"],
                check=True, capture_output=True, timeout=10,
            )
            logger.info("WiFi enable command sent (macOS)")
            return True

        elif system == "Linux":
            # Try nmcli first, fall back to rfkill
            for cmd in (
                ["nmcli", "radio", "wifi", "on"],
                ["rfkill", "unblock", "wifi"],
            ):
                try:
                    subprocess.run(cmd, check=True, capture_output=True, timeout=10)
                    logger.info("WiFi enable command sent (Linux): %s", cmd)
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
    except Exception as exc:
        logger.warning("try_enable_wifi failed: %s", exc)
    return False


# ── Missed-task recovery on startup ──────────────────────────────────────────

def check_missed_tasks(storage: "Storage") -> None:
    """
    On startup, look for tasks that were scheduled for today but not yet
    executed.  Execute them immediately if the user's permission was granted
    and we are online.  Only considers tasks for the current calendar day.
    """
    logger.info("Checking for missed tasks from today …")

    today = date.today().isoformat()
    permission = storage.get_today_permission()

    if permission is False:
        logger.info("Permission was denied today – skipping missed-task check.")
        return

    pending = storage.get_pending_tasks(for_date=today)
    if not pending:
        logger.info("No pending tasks found for today.")
        return

    for task in pending:
        scheduled = datetime.fromisoformat(task["scheduled_time"])
        if datetime.now() < scheduled:
            # Task is still in the future – the scheduler will handle it
            continue

        logger.warning(
            "Missed task detected: %s (scheduled %s, retries so far: %d)",
            task["action_type"],
            task["scheduled_time"],
            task["retry_count"],
        )

        if task["retry_count"] >= MAX_RETRIES:
            logger.error("Task %d exceeded MAX_RETRIES – skipping.", task["id"])
            storage.update_task(task["id"], "failed", "Exceeded MAX_RETRIES on startup")
            continue

        if not is_online():
            logger.warning("Offline at startup – task %d left as pending.", task["id"])
            continue

        # Deferred import to avoid circular dependency
        from hrms_bot import HRMSBot

        action = task["action_type"]
        logger.info("Executing missed task %d (%s) …", task["id"], action)
        try:
            with HRMSBot() as bot:
                success = bot.clock_in() if action == "clock_in" else bot.clock_out()
            status = "success" if success else "failed"
            storage.update_task(task["id"], status)
            logger.info("Missed task %d → %s", task["id"], status)
        except Exception as exc:
            storage.update_task(task["id"], "failed", str(exc))
            logger.exception("Missed task %d raised exception: %s", task["id"], exc)


# ── Auto-start on system boot ─────────────────────────────────────────────────

def setup_autostart(enable: bool = True) -> bool:
    """
    Register (or deregister) the bot to start automatically when the user logs in.
    Returns True on success, False on failure or unsupported platform.
    """
    system = platform.system()
    script  = Path(sys.argv[0]).resolve()
    python  = Path(sys.executable).resolve()

    if system == "Windows":
        return _autostart_windows(enable, python, script)
    elif system == "Darwin":
        return _autostart_macos(enable, python, script)
    elif system == "Linux":
        return _autostart_linux(enable, python, script)
    else:
        logger.warning("Auto-start not supported on %s", system)
        return False


def _autostart_windows(enable: bool, python: Path, script: Path) -> bool:
    try:
        import winreg  # type: ignore
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                cmd = f'"{python}" "{script}"'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                logger.info("Auto-start registered (Windows registry): %s", cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    logger.info("Auto-start removed (Windows registry)")
                except FileNotFoundError:
                    pass
        return True
    except Exception as exc:
        logger.error("Auto-start (Windows) failed: %s", exc)
        return False


def _autostart_macos(enable: bool, python: Path, script: Path) -> bool:
    plist_dir  = Path.home() / "Library" / "LaunchAgents"
    plist_file = plist_dir / "com.hrmsbot.autoattendance.plist"
    plist_dir.mkdir(parents=True, exist_ok=True)

    if enable:
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>com.hrmsbot.autoattendance</string>
  <key>ProgramArguments</key>  <array>
    <string>{python}</string>
    <string>{script}</string>
  </array>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <false/>
  <key>StandardOutPath</key>   <string>{LOG_PATH}</string>
  <key>StandardErrorPath</key> <string>{LOG_PATH}</string>
</dict>
</plist>
"""
        plist_file.write_text(plist)
        subprocess.run(["launchctl", "load", str(plist_file)], check=False)
        logger.info("Auto-start registered (macOS LaunchAgent): %s", plist_file)
    else:
        if plist_file.exists():
            subprocess.run(["launchctl", "unload", str(plist_file)], check=False)
            plist_file.unlink()
            logger.info("Auto-start removed (macOS LaunchAgent)")
    return True


def _autostart_linux(enable: bool, python: Path, script: Path) -> bool:
    autostart_dir  = Path.home() / ".config" / "autostart"
    desktop_file   = autostart_dir / "hrms-bot.desktop"
    autostart_dir.mkdir(parents=True, exist_ok=True)

    if enable:
        desktop = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            f"Exec={python} {script}\n"
            "Hidden=false\n"
            "NoDisplay=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        desktop_file.write_text(desktop)
        logger.info("Auto-start registered (Linux XDG autostart): %s", desktop_file)
    else:
        if desktop_file.exists():
            desktop_file.unlink()
            logger.info("Auto-start removed (Linux XDG autostart)")
    return True
