"""
utils.py – Shared helpers: network checks, notifications, WiFi recovery.
"""

import logging
import socket
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

_CHECK_HOST = "hrms.technimus.com"
_CHECK_PORT = 443
_CHECK_TIMEOUT = 5  # seconds


def is_online(host: str = _CHECK_HOST, port: int = _CHECK_PORT, timeout: int = _CHECK_TIMEOUT) -> bool:
    """Return True if we can reach *host*:*port* within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Connectivity recovery (best-effort, Windows only)
# ---------------------------------------------------------------------------

def try_enable_wifi() -> bool:
    """
    Attempt to enable a disabled WiFi adapter on Windows.
    Returns True if a netsh command ran without error.
    """
    if sys.platform != "win32":
        logger.debug("try_enable_wifi: not on Windows, skipping")
        return False
    try:
        result = subprocess.run(
            ["netsh", "interface", "set", "interface", "Wi-Fi", "admin=enable"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        success = result.returncode == 0
        logger.info("try_enable_wifi: %s", "ok" if success else result.stderr.strip())
        return success
    except Exception as exc:
        logger.warning("try_enable_wifi failed: %s", exc)
        return False


def attempt_connectivity_recovery() -> bool:
    """
    Try to restore internet connectivity.
    Returns True if online after recovery attempt.
    """
    if is_online():
        return True
    logger.info("Offline – attempting WiFi recovery …")
    try_enable_wifi()
    # Allow adapter time to associate
    import time
    time.sleep(10)
    result = is_online()
    logger.info("After recovery attempt: %s", "online" if result else "still offline")
    return result


# ---------------------------------------------------------------------------
# System notifications
# ---------------------------------------------------------------------------

def notify(title: str, message: str) -> None:
    """
    Send a desktop notification.
    Uses plyer when available; falls back gracefully.
    """
    try:
        from plyer import notification  # type: ignore
        notification.notify(
            title=title,
            message=message,
            app_name="HRMS AutoAttendance",
            timeout=8,
        )
    except Exception as exc:
        logger.warning("Desktop notification failed (%s): %s – %s", exc, title, message)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_file: Optional[str] = "hrms_automation.log", level: int = logging.INFO) -> None:
    """Configure root logger to write to file + stdout."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        handlers=handlers,
    )
