# HRMS 

https://karls-hrms.netlify.app/

A **two-part project**:

| Part | What it is | Where it runs |
|------|-----------|---------------|
| **Web app** (`index.html` / `style.css` / `app.js`) | HRMS dashboard UI with login, attendance, leaves, payroll |
| **Desktop bot** (`hrms-bot/`) | Python automation that clock-in/out on hrms | 💻 Your PC / server |

---


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


> Tip (2026-08-11): Small dev note — check CONTRIBUTING.md for PR guidelines.

> Tip (2026-08-12): Small dev note — check CONTRIBUTING.md for PR guidelines.

<!-- auto-updated: 2026-08-13T11:31:41.423090+00:00 -->
[2026-08-13 11:31:41 GMT] Quick note: reviewed rate limiter and left a small TODO about edge-case handling. (see issue #59)
[2026-08-13 11:31:41 GMT] Quick note: reviewed health check endpoint and left a small TODO about edge-case handling.
[2026-08-13 11:31:41 GMT] Follow-up: reworded docs for jwt validation and clarified expected inputs.
[2026-08-13 11:31:41 GMT] Deprecation notice: flagged legacy interface in graphql resolver for future removal.
[2026-08-13 11:31:41 GMT] Dx improvement: simplified setup commands in api/users guide. — example: `fix_598`
[2026-08-13 11:31:41 GMT] API draft: sketched out REST response contract for metrics exporter.
[2026-08-13 11:31:41 GMT] State sync: investigated race conditions within search index sync.
[2026-08-13 11:31:41 GMT] Cache strategy: evaluated TTL values for session store.

<!-- auto-updated: 2026-08-14T11:36:18.917206+00:00 -->
[2026-08-14 11:36:18 GMT] Investigation: observed flaky behavior around audit trail recorder; note to reproduce later.
[2026-08-14 11:36:18 GMT] Type check: tightened strict mode types across docs/setup.
[2026-08-14 11:36:18 GMT] UI alignment: verified design token consistency in db.connection.
[2026-08-14 11:36:18 GMT] Reminder: check CI setup that references metrics exporter.
[2026-08-14 11:36:18 GMT] Housekeeping: removed an outdated comment in task runner.
[2026-08-14 11:36:18 GMT] State sync: investigated race conditions within metrics exporter.
[2026-08-14 11:36:18 GMT] UI alignment: verified design token consistency in scheduler.
[2026-08-14 11:36:18 GMT] Dependency check: reviewed compatibility of packages used in s3 file uploader. (see issue #25)

> Tip (2026-08-18 GMT): Small dev note — check CONTRIBUTING.md for PR guidelines.

> Tip (2026-08-31 GMT): Small dev note — check CONTRIBUTING.md for PR guidelines.

> Tip (2026-09-03 GMT): Small dev note — check CONTRIBUTING.md for PR guidelines.

<!-- auto-updated: 2026-09-06T13:39:40.582904+00:00 -->
[2026-09-06 13:39:40 GMT] Telemetry: added event tracking markers to graphql resolver.
[2026-09-06 13:39:40 GMT] Type check: tightened strict mode types across cors middleware.
[2026-09-06 13:39:40 GMT] Security check: audited permission flags in websocket handler.
[2026-09-06 13:39:40 GMT] Performance review: benchmarked api/users under heavy payload.
[2026-09-06 13:39:40 GMT] Error handling: added graceful fallback logic inside env variable validator. (see issue #45)

> Tip (2026-09-10 GMT): Small dev note — check CONTRIBUTING.md for PR guidelines.

> Tip (2026-09-15 GMT): Small dev note — check CONTRIBUTING.md for PR guidelines.

<!-- auto-updated: 2026-09-21T16:07:59.384699+00:00 -->
[2026-09-21 16:07:59 GMT] Deprecation notice: flagged legacy interface in input sanitizer for future removal.
[2026-09-21 16:07:59 GMT] Coverage update: added unit test stubs for session store.
[2026-09-21 16:07:59 GMT] API draft: sketched out REST response contract for error handling.
[2026-09-21 16:07:59 GMT] Performance review: benchmarked auth.login under heavy payload.
[2026-09-21 16:07:59 GMT] Security check: audited permission flags in rate limiter.
[2026-09-21 16:07:59 GMT] Small tweak: adjusted formatting and examples in logger service. (see issue #299)
[2026-09-21 16:07:59 GMT] Coverage update: added unit test stubs for s3 file uploader.
[2026-09-21 16:07:59 GMT] State sync: investigated race conditions within feature flag manager.
[2026-09-21 16:07:59 GMT] State sync: investigated race conditions within feature flag manager. (see issue #263)
[2026-09-21 16:07:59 GMT] Reminder: check CI setup that references search index sync. — example: `fix_618`

<!-- auto-updated: 2026-09-22T14:24:01.817309+00:00 -->
[2026-09-22 14:24:01 GMT] Telemetry: added event tracking markers to search index sync.
[2026-09-22 14:24:01 GMT] Reminder: check CI setup that references auth.login.
[2026-09-22 14:24:01 GMT] Progress: sketched optimization idea for rate limiter; prototype next.
[2026-09-22 14:24:01 GMT] Dependency check: reviewed compatibility of packages used in CI configuration.
[2026-09-22 14:24:01 GMT] Performance review: benchmarked error handling under heavy payload. (see issue #307)
[2026-09-22 14:24:01 GMT] Small tweak: adjusted formatting and examples in auth.login.
[2026-09-22 14:24:01 GMT] Refactor thought: consider splitting notification dispatcher into smaller helpers for tests.
[2026-09-22 14:24:01 GMT] Quick note: reviewed auth.login and left a small TODO about edge-case handling.
[2026-09-22 14:24:01 GMT] Refactor thought: consider splitting api/users into smaller helpers for tests.
[2026-09-22 14:24:01 GMT] Progress: sketched optimization idea for jwt validation; prototype next.
