# HRMS 

https://karls-hrms.netlify.app/

A **two-part project**:

| Part | What it is | Where it runs |
|------|-----------|---------------|
| **Web app** (`index.html` / `style.css` / `app.js`) | HRMS dashboard UI with login, attendance, leaves, payroll |
| **Desktop bot** (`hrms-bot/`) | Python automation that clock-in/out on hrms | 💻 Your PC / server |

---


   | Setting | Value |
   |---------|-------|
   | **Branch to deploy** | `copilot/fix-deployment-issue-hrms` (or `main` after merge) |
   | **Base directory** | *(leave empty)* |
   | **Build command** | *(leave empty)* |
   | **Publish directory** | `.` |



## 🔑 Demo Login Credentials (web app only)

| Role | HRMS ID | Password |
|------|---------|----------|
| Admin | `ADMIN` | `admin123` |
| Employee | `EMP001` – `EMP005` | `hrms1234` |

---


Quick start:
```bash
cd hrms-bot
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in HRMS_USERNAME + HRMS_PASSWORD
python main.py
```

---

## 📁 Project Structure

```
├── index.html        Web app – login + HRMS dashboard
├── style.css         Styles (mobile-first, responsive)
├── app.js            Frontend logic (auth, attendance, payroll …)
├── netlify.toml      Netlify deployment config (headers, redirects)
├── _redirects        SPA fallback redirect
└── hrms-bot/         Python desktop automation bot
    ├── main.py
    ├── hrms_bot.py   Playwright automation
    ├── scheduler.py  APScheduler jobs
    ├── storage.py    SQLite persistence
    ├── ui.py         System tray + popup
    ├── cloud_api.py  Flask web dashboard (cloud mode)
    ├── .env.example
    └── requirements.txt
```

