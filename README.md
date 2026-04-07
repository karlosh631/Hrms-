# HRMS AutoAttendance

A production-grade desktop automation system for daily clock-in and clock-out on
**[hrms.technimus.com](https://hrms.technimus.com/)**.

The app runs silently in the Windows system tray, asks for your permission every
morning, and then handles clock-in at 10:00 AM and clock-out at 5:05 PM
automatically – even if the device was offline or restarted during those times.

---

## Features

| Feature | Details |
|---|---|
| **Daily permission** | 8:00 AM popup on Sunday–Friday; automation skipped on Saturday |
| **Reliable scheduling** | APScheduler with missed-fire recovery |
| **Offline resilience** | Stores pending tasks in SQLite, retries every 5 min (max 20 retries) |
| **Startup recovery** | Resumes same-day missed tasks when the app starts |
| **System tray** | Runs invisibly; left-click for status, right-click for menu |
| **Manual actions** | "Clock-in now" / "Clock-out now" from the tray menu |
| **Notifications** | Desktop alerts on success or permanent failure |
| **Credentials** | Loaded from `.env`; never hard-coded |

---

## Project Structure

```
hrms-autoattendance/
│
├── main.py          # Entry point
├── scheduler.py     # APScheduler job definitions
├── hrms_bot.py      # Playwright browser automation
├── storage.py       # SQLite persistence layer
├── ui.py            # PyQt5 tray icon + permission popup
├── utils.py         # Network checks, notifications, WiFi recovery
│
├── .env             # Your credentials (never commit this)
├── .env.example     # Template
├── requirements.txt
└── README.md
```

---

## Prerequisites

- **Python 3.11+** (recommended)
- **Windows 10/11** (primary target; macOS/Linux work with minor caveats)
- Internet access to `hrms.technimus.com`

---

## Installation

### 1. Clone / download

```bash
git clone https://github.com/karlosh631/Hrms-.git
cd Hrms-
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

```bash
playwright install chromium
```

### 5. Configure credentials

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Edit `.env`:

```
HRMS_USERNAME=your_username
HRMS_PASSWORD=your_password
```

---

## Running the App

```bash
python main.py
```

The app will:
1. Initialise the SQLite database (`hrms_data.db`) if it does not exist.
2. Start the background scheduler.
3. Recover any same-day missed tasks (if the system was off earlier).
4. Show a system-tray icon.

### Tray icon

| Interaction | Action |
|---|---|
| Left-click | Opens today's status window |
| Right-click | Opens the context menu |
| Context menu → Clock-in now | Triggers clock-in immediately |
| Context menu → Clock-out now | Triggers clock-out immediately |
| Context menu → Quit | Exits the app |

---

## Auto-start on Windows Boot

### Option A – Task Scheduler (recommended)

1. Open **Task Scheduler** → *Create Basic Task*.
2. Trigger: **When the computer starts**.
3. Action: **Start a program**
   - Program: `C:\path\to\.venv\Scripts\pythonw.exe`
   - Arguments: `C:\path\to\Hrms-\main.py`
4. Check **Run whether user is logged on or not** (optional).
5. Finish.

### Option B – Startup folder shortcut

Create a `.bat` file:

```bat
@echo off
cd /d C:\path\to\Hrms-
.venv\Scripts\pythonw.exe main.py
```

Place a shortcut to this file in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

---

## SQLite Schema

The file `hrms_data.db` is created automatically.

| Table | Purpose |
|---|---|
| `daily_permission` | Stores YES/NO for each date |
| `tasks` | Scheduled tasks with status and retry count |
| `logs` | Execution audit trail |

### `tasks` columns

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key |
| `date` | TEXT | YYYY-MM-DD |
| `action_type` | TEXT | `clock_in` / `clock_out` |
| `scheduled_time` | TEXT | ISO-8601 scheduled time |
| `executed_time` | TEXT | ISO-8601 actual execution time |
| `status` | TEXT | `pending` / `success` / `failed` |
| `retries` | INTEGER | Number of attempts made |

---

## Configuration

| Setting | Where | Default |
|---|---|---|
| Timezone | `scheduler.py` → `build_scheduler()` | `Asia/Karachi` |
| Clock-in time | `scheduler.py` CronTrigger | 10:00 |
| Clock-out time | `scheduler.py` CronTrigger | 17:05 |
| Max retries | `scheduler.py` `MAX_RETRIES` | 20 |
| Retry interval | `scheduler.py` `RETRY_INTERVAL_MIN` | 5 min |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| No tray icon | Ensure PyQt5 is installed: `pip install PyQt5` |
| Login fails | Verify `.env` credentials; check site for CAPTCHA |
| Clock-in button not found | Site may have changed layout – update selectors in `hrms_bot.py` |
| Tasks stuck as pending | Check `hrms_automation.log` for errors |
| App crashes on start | Run `python main.py` from a terminal to see the traceback |

---

## Security Notes

- Credentials are read from `.env` at runtime; they are **never** stored in the database or committed to source control.
- Add `.env` to `.gitignore` (already done in this repo).
- The SQLite database (`hrms_data.db`) contains only metadata – no passwords.

---

## Optional: Cloud Mode

For an always-online setup, deploy the app on a VPS or cloud instance:

1. Copy the project to the server (Linux).
2. Install a headless browser: `playwright install --with-deps chromium`.
3. Expose a small HTTP endpoint (e.g. with Flask) to accept the daily YES/NO decision via a Telegram bot or web form.
4. Run `python main.py` as a systemd service.

---

## License

MIT
