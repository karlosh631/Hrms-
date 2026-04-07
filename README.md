# HRMS 

https://karls-hrms.netlify.app/

A **two-part project**:

| Part | What it is | Where it runs |
|------|-----------|---------------|
| **Web app** (`index.html` / `style.css` / `app.js`) | HRMS dashboard UI with login, attendance, leaves, payroll | ☁️ Netlify (static hosting) |
| **Desktop bot** (`hrms-bot/`) | Python automation that auto clock-in/out on hrms.technimus.com | 💻 Your PC / server |

---

## ☁️ Deploy the Web App to Netlify

### Option A — One-click (recommended)

[![Deploy to Netlify](https://www.netlify.com/img/deploy/button.svg)](https://app.netlify.com/start/deploy?repository=https://github.com/karlosh631/Hrms-)

1. Click the button above.
2. Connect your GitHub account if prompted.
3. Click **"Save & Deploy"** — no build settings needed.

### Option B — Manual via Netlify dashboard

1. Go to [app.netlify.com](https://app.netlify.com) → **Add new site → Import an existing project**.
2. Choose **GitHub** → select `karlosh631/Hrms-`.
3. Set the following:

   | Setting | Value |
   |---------|-------|
   | **Branch to deploy** | `copilot/fix-deployment-issue-hrms` (or `main` after merge) |
   | **Base directory** | *(leave empty)* |
   | **Build command** | *(leave empty)* |
   | **Publish directory** | `.` |

4. Click **Deploy site**.

### Option C — Netlify CLI

```bash
npm install -g netlify-cli
netlify login
netlify deploy --dir . --prod
```

---

## 🔑 Demo Login Credentials (web app only)

| Role | HRMS ID | Password |
|------|---------|----------|
| Admin | `ADMIN` | `admin123` |
| Employee | `EMP001` – `EMP005` | `hrms1234` |

---

## 💻 Desktop Bot (hrms-bot/)

The Python bot auto clock-in/out in the real Horilla HRMS.
See **[hrms-bot/README.md](hrms-bot/README.md)** for full setup instructions.

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

