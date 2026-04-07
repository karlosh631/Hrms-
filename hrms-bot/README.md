# HRMS Auto Attendance Bot

An automated desktop/server bot that **auto clock-in and clock-out** in your [Horilla HRMS](https://hrms.technimus.com/) instance every working day — with an 8 AM permission popup, offline retry, system tray, and optional cloud mode for mobile access.

---

## Features

| Feature | Details |
|---|---|
| 🕗 Daily permission | Popup at **8:00 AM** (Sun–Fri) — enable or disable automation for that day |
| ⏰ Auto clock-in | **10:00 AM** (configurable) |
| ⏰ Auto clock-out | **5:05 PM** (configurable) |
| 🔄 Offline retry | Stores tasks in SQLite; retries every 5 min; up to 20 attempts |
| 💻 System tray | Runs silently; colour-coded icon (green/red/yellow) |
| 🔔 Notifications | Desktop notification on every success/failure |
| ☁️ Cloud mode | Headless server + web dashboard — works from mobile browser |
| 🚀 Auto-start | Registers itself to launch on system boot |
| 🔒 No hardcoded creds | Credentials live only in `.env` |

---

## Supported Platforms

| Platform | Mode |
|---|---|
| Windows 10/11 | ✅ Full tray UI |
| macOS 12+ | ✅ Full tray UI |
| Linux (desktop) | ✅ Full tray UI |
| Linux (server/headless) | ✅ Cloud mode |
| Android / iOS | ✅ via Cloud mode web dashboard |

---

## Quick Start

### 1. Prerequisites

- **Python 3.9+** — [python.org](https://www.python.org/downloads/)
- **pip** (comes with Python)

### 2. Clone / download the bot

```bash
# If you cloned the full repo:
cd hrms-bot

# Or download just this folder as a zip and unzip it
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Then install the Playwright browser (Chromium):

```bash
playwright install chromium
```

### 4. Configure credentials

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in:

```
HRMS_USERNAME=your_username
HRMS_PASSWORD=your_password
```

All other settings are optional (defaults work for hrms.technimus.com).

### 5. Run the bot

```bash
python main.py
```

A small icon will appear in your system tray.  At **8:00 AM** you will see:

> *"Enable auto clock-in and clock-out for today?"*  **[YES]**  **[NO]**

---

## Running in the Background

### Windows — auto-start on boot (recommended)

```bash
python main.py --enable-autostart
```

To remove:
```bash
python main.py --disable-autostart
```

To run it right now in the background (hidden console):

```bat
pythonw main.py
```

Or create a `.bat` launcher:
```bat
@echo off
start "" /B pythonw "C:\path\to\hrms-bot\main.py"
```

### macOS

```bash
python main.py --enable-autostart
```

This creates a LaunchAgent plist in `~/Library/LaunchAgents/`.

### Linux (systemd service)

```bash
# Create a service file
sudo nano /etc/systemd/system/hrms-bot.service
```

Paste (replace paths):
```ini
[Unit]
Description=HRMS Auto Attendance Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/hrms-bot
ExecStart=/usr/bin/python3 /path/to/hrms-bot/main.py
Restart=on-failure
RestartSec=30
Environment=HRMS_CLOUD_MODE=true
Environment=HRMS_AUTO_APPROVE=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable hrms-bot
sudo systemctl start hrms-bot
```

---

## Cloud / Server Mode (for Mobile Access)

When running on a headless server (no screen), set `HRMS_CLOUD_MODE=true` in `.env`.

This starts a web dashboard on port 8080:

```
http://YOUR_SERVER_IP:8080
```

Open this URL from **any mobile browser** to:
- ✅ Enable automation for today
- ❌ Disable automation for today
- ▶ Clock in manually
- ■ Clock out manually
- View today's task log

### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/api/status` | Today's permission + task log |
| POST | `/api/permission` | Body: `{"enabled": true}` |
| POST | `/api/clock-in` | Trigger clock-in immediately |
| POST | `/api/clock-out` | Trigger clock-out immediately |

Example (from phone or curl):
```bash
# Grant permission
curl -X POST http://SERVER_IP:8080/api/permission -H "Content-Type: application/json" -d '{"enabled":true}'

# Manual clock-in
curl -X POST http://SERVER_IP:8080/api/clock-in
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `HRMS_USERNAME` | *required* | Your HRMS login ID |
| `HRMS_PASSWORD` | *required* | Your HRMS password |
| `HRMS_URL` | `https://hrms.technimus.com/` | HRMS base URL |
| `PERMISSION_HOUR` | `8` | Hour of the daily permission popup |
| `CLOCKIN_HOUR` | `10` | Clock-in hour |
| `CLOCKIN_MINUTE` | `0` | Clock-in minute |
| `CLOCKOUT_HOUR` | `17` | Clock-out hour (17 = 5 PM) |
| `CLOCKOUT_MINUTE` | `5` | Clock-out minute |
| `MAX_RETRIES` | `20` | Max retry attempts per task |
| `RETRY_INTERVAL` | `300` | Seconds between retries |
| `HRMS_CLOUD_MODE` | `false` | `true` = headless server mode |
| `HRMS_AUTO_APPROVE` | `false` | `true` = skip the 8 AM popup |
| `HRMS_HEADLESS` | `true` | `false` = show the browser window (debug) |
| `CLOUD_API_PORT` | `8080` | Web dashboard port |

---

## One-Shot Commands

```bash
# Clock in right now (no tray, no scheduler)
python main.py --clock-in

# Clock out right now
python main.py --clock-out

# Debug mode (verbose logging)
python main.py --debug
```

---

## File Structure

```
hrms-bot/
├── main.py          Entry point – boots tray or headless mode
├── scheduler.py     APScheduler jobs (permission, clock-in/out, retry)
├── hrms_bot.py      Playwright browser automation for Horilla HRMS
├── storage.py       SQLite persistence (daily permission + task log)
├── ui.py            PyQt5 system tray, 8 AM popup, notifications
├── cloud_api.py     Flask web dashboard for cloud/mobile mode
├── utils.py         Network check, auto-start, WiFi recovery, logging
├── config.py        Central configuration from .env
├── .env.example     Credential template
├── requirements.txt Python dependencies
└── data/            Created automatically at runtime
    ├── hrms_bot.db  SQLite database
    ├── hrms_bot.log Rotating log file
    └── screenshots/ Failure screenshots (for debugging)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `HRMS_USERNAME not set` | Create `.env` from `.env.example` and fill in credentials |
| Clock-in/out button not found | Set `HRMS_HEADLESS=false` to watch the browser; check `data/screenshots/` |
| PyQt5 import error | `pip install PyQt5` or use `HRMS_CLOUD_MODE=true` |
| App not starting on boot | Run `python main.py --enable-autostart` |
| Still offline after WiFi enable | Check network adapter name; edit `utils.py` `try_enable_wifi()` |
| Tasks stuck as `pending` | Check `data/hrms_bot.log`; run `python main.py --debug` |

---

## Security Notes

- **Never commit your real `.env` file** — it contains your HRMS password.
- `.env` is listed in `.gitignore` (add it if not present).
- Credentials are only read at startup from environment variables.
- The bot does **not** store your password in the SQLite database.
