"""
config.py – Central configuration loaded from .env and environment variables.
All other modules import from here; nothing touches os.getenv() directly.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ─── Directory setup ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── HRMS credentials (REQUIRED) ─────────────────────────────────────────────
# SECURITY: These MUST come from the .env file – never hard-code.
HRMS_URL      = os.getenv("HRMS_URL",      "https://hrms.technimus.com/").rstrip("/") + "/"
HRMS_USERNAME = os.getenv("HRMS_USERNAME", "")
HRMS_PASSWORD = os.getenv("HRMS_PASSWORD", "")

if not HRMS_USERNAME or not HRMS_PASSWORD:
    print("[FATAL] HRMS_USERNAME and HRMS_PASSWORD must be set in the .env file.")
    sys.exit(1)

# ─── Schedule times (configurable via .env) ───────────────────────────────────
PERMISSION_HOUR   = int(os.getenv("PERMISSION_HOUR",   "8"))
PERMISSION_MINUTE = int(os.getenv("PERMISSION_MINUTE", "0"))

CLOCKIN_HOUR      = int(os.getenv("CLOCKIN_HOUR",      "10"))
CLOCKIN_MINUTE    = int(os.getenv("CLOCKIN_MINUTE",    "0"))

CLOCKOUT_HOUR     = int(os.getenv("CLOCKOUT_HOUR",     "17"))
CLOCKOUT_MINUTE   = int(os.getenv("CLOCKOUT_MINUTE",   "5"))

# ─── Retry / offline settings ─────────────────────────────────────────────────
MAX_RETRIES       = int(os.getenv("MAX_RETRIES",    "20"))   # max attempts per task
RETRY_INTERVAL    = int(os.getenv("RETRY_INTERVAL", "300"))  # seconds between retries

# ─── Operating modes ──────────────────────────────────────────────────────────
# CLOUD_MODE: headless server – skips Qt UI, uses AUTO_APPROVE
CLOUD_MODE   = os.getenv("HRMS_CLOUD_MODE",   "false").lower() in ("1", "true", "yes")
# AUTO_APPROVE: grant daily permission automatically without showing a popup
AUTO_APPROVE = os.getenv("HRMS_AUTO_APPROVE", "false").lower() in ("1", "true", "yes")
# HEADLESS: run Chromium without a visible window
HEADLESS     = os.getenv("HRMS_HEADLESS",     "true" ).lower() in ("1", "true", "yes")

# Cloud API port (used when CLOUD_MODE=true)
CLOUD_API_PORT = int(os.getenv("CLOUD_API_PORT", "8080"))
# Optional Telegram bot token + chat ID for cloud permission requests
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")

# ─── File paths ───────────────────────────────────────────────────────────────
DB_PATH       = DATA_DIR / "hrms_bot.db"
LOG_PATH      = DATA_DIR / "hrms_bot.log"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# ─── App metadata ─────────────────────────────────────────────────────────────
APP_NAME    = "HRMS Auto Attendance"
APP_VERSION = "1.0.0"
