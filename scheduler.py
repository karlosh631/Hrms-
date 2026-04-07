"""
scheduler.py – APScheduler-based job orchestration.

Jobs:
  • 08:00 Mon-Sat  – ask daily permission via UI popup
  • 10:00 daily    – clock-in  (only if today's permission is YES)
  • 17:05 daily    – clock-out (only if today's permission is YES)
  • every 5 min    – retry pending / offline tasks
  • on startup     – recover missed same-day tasks
"""

import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore

import storage
import utils
import hrms_bot

logger = logging.getLogger(__name__)

MAX_RETRIES: int = 20       # configurable
RETRY_INTERVAL_MIN: int = 5  # minutes between retry sweeps

# Injected by main.py so scheduler can open the permission dialog
_ask_permission_callback = None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def set_permission_callback(cb) -> None:
    """Register the function that shows the 8 AM permission popup."""
    global _ask_permission_callback
    _ask_permission_callback = cb


def build_scheduler() -> BackgroundScheduler:
    """Create and return a configured (not yet started) BackgroundScheduler."""
    scheduler = BackgroundScheduler(timezone="Asia/Karachi")

    # 08:00 Sunday–Friday – ask permission
    # APScheduler cron accepts day-of-week names directly (mon, tue, … sun).
    # Sunday–Friday means every day except Saturday.
    scheduler.add_job(
        _job_ask_permission,
        CronTrigger(day_of_week="mon,tue,wed,thu,fri,sun", hour=8, minute=0),
        id="ask_permission",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 10:00 every day – clock-in
    scheduler.add_job(
        lambda: _job_action("clock_in"),
        CronTrigger(hour=10, minute=0),
        id="clock_in",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 17:05 every day – clock-out
    scheduler.add_job(
        lambda: _job_action("clock_out"),
        CronTrigger(hour=17, minute=5),
        id="clock_out",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Retry sweep every RETRY_INTERVAL_MIN minutes
    scheduler.add_job(
        _job_retry_pending,
        "interval",
        minutes=RETRY_INTERVAL_MIN,
        id="retry_pending",
        replace_existing=True,
    )

    return scheduler


def recover_missed_tasks() -> None:
    """
    Called once at startup.
    For any pending task scheduled for TODAY that is past its scheduled time,
    attempt execution immediately.
    """
    today = date.today()
    now = datetime.now()
    pending = storage.get_pending_tasks(day=today)
    for task in pending:
        scheduled = datetime.fromisoformat(task["scheduled_time"])
        if scheduled <= now:
            logger.info(
                "Recovering missed same-day task: %s scheduled at %s",
                task["action_type"],
                task["scheduled_time"],
            )
            _execute_task(task["id"], task["action_type"])


# ---------------------------------------------------------------------------
# Scheduled job implementations
# ---------------------------------------------------------------------------

def _job_ask_permission() -> None:
    today = date.today()
    # Only ask once per day
    existing = storage.get_permission(today)
    if existing is not None:
        logger.info("Permission already recorded for %s – skipping popup.", today)
        return

    if _ask_permission_callback:
        _ask_permission_callback(today)
    else:
        logger.warning("No permission callback registered – defaulting to NO.")
        storage.set_permission(today, False)


def _job_action(action_type: str) -> None:
    today = date.today()

    # Only proceed on Sun-Fri (0=Mon … 6=Sun in Python)
    # Sunday = 6 in Python's weekday(), Fri = 4
    weekday = today.weekday()  # Mon=0 … Sun=6
    if weekday == 5:  # Saturday
        logger.info("Skipping %s – today is Saturday.", action_type)
        return

    permitted = storage.get_permission(today)
    if not permitted:
        logger.info("Automation not permitted for %s – skipping %s.", today, action_type)
        return

    # Determine scheduled time for idempotency
    scheduled_hour, scheduled_minute = (10, 0) if action_type == "clock_in" else (17, 5)
    scheduled_dt = datetime.now().replace(
        hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0
    )

    task_id = storage.upsert_task(today, action_type, scheduled_dt)
    task = storage.get_task(today, action_type)
    if task and task["status"] == "success":
        logger.info("%s already executed successfully today – skipping.", action_type)
        return

    _execute_task(task_id, action_type)


def _job_retry_pending() -> None:
    """Retry all pending tasks (across any date, up to MAX_RETRIES)."""
    today = date.today()
    pending = storage.get_pending_tasks()
    if not pending:
        return

    logger.info("Retry sweep: %d pending task(s) found.", len(pending))

    # Only retry tasks from today (past-day tasks are skipped)
    for task in pending:
        task_date = date.fromisoformat(task["date"])
        if task_date != today:
            logger.debug("Skipping old pending task %s from %s", task["action_type"], task["date"])
            continue

        retries = task["retries"]
        if retries >= MAX_RETRIES:
            logger.warning(
                "Task %d (%s) exceeded max retries (%d) – marking failed.",
                task["id"],
                task["action_type"],
                MAX_RETRIES,
            )
            storage.mark_task_failed(task["id"])
            storage.add_log(task["id"], "ERROR", f"Max retries ({MAX_RETRIES}) exceeded")
            utils.notify(
                "HRMS Automation – Failed",
                f"{task['action_type'].replace('_', ' ').title()} failed after {MAX_RETRIES} retries.",
            )
            continue

        if not utils.is_online():
            logger.info("Still offline – skipping retry for task %d.", task["id"])
            utils.attempt_connectivity_recovery()
            continue

        _execute_task(task["id"], task["action_type"])


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

def execute_task(task_id: int, action_type: str) -> bool:
    """
    Public API: attempt to perform *action_type* via hrms_bot.
    Updates task status and sends notifications.
    Returns True on success.
    """
    if not utils.is_online():
        storage.add_log(task_id, "WARN", "Offline at execution time – will retry later")
        logger.info("Device offline – deferring task %d (%s) to retry queue.", task_id, action_type)
        return False

    retries = storage.increment_retries(task_id)
    label = action_type.replace("_", " ").title()
    storage.add_log(task_id, "INFO", f"Attempting {label} (try #{retries})")

    try:
        hrms_bot.perform_action(action_type)  # type: ignore[arg-type]
        storage.mark_task_success(task_id)
        storage.add_log(task_id, "INFO", f"{label} succeeded")
        utils.notify("HRMS AutoAttendance ✔", f"{label} recorded successfully.")
        logger.info("Task %d (%s) succeeded.", task_id, action_type)
        return True

    except Exception as exc:
        storage.add_log(task_id, "ERROR", f"{label} failed: {exc}")
        logger.error("Task %d (%s) failed: %s", task_id, action_type, exc)
        # Task remains 'pending' so retry sweep will pick it up
        return False


# Keep the private alias for internal callers
_execute_task = execute_task
