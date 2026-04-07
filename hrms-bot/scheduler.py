"""
scheduler.py – APScheduler-based job manager.

Jobs
----
• 08:00  Sun–Fri  → ask permission (or auto-approve in cloud/auto mode)
• 10:00  daily    → clock-in  (only if today's permission = YES)
• 17:05  daily    → clock-out (only if today's permission = YES)
• every 5 min     → retry any pending tasks when back online

All jobs are idempotent – duplicate execution is prevented by checking
task_already_succeeded() before acting.
"""
import logging
import threading
import time
from datetime import datetime, date
from typing import Callable, Optional

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    AUTO_APPROVE,
    CLOCKIN_HOUR,
    CLOCKIN_MINUTE,
    CLOCKOUT_HOUR,
    CLOCKOUT_MINUTE,
    MAX_RETRIES,
    PERMISSION_HOUR,
    PERMISSION_MINUTE,
    RETRY_INTERVAL,
)
from utils import is_online

logger = logging.getLogger(__name__)


class HRMSScheduler:
    """
    Wraps APScheduler's BackgroundScheduler.  Communicates with the UI
    via a callback that the UI layer (ui.py) registers for the
    8-AM permission request.
    """

    def __init__(self, storage) -> None:
        self._storage  = storage
        self._sched    = BackgroundScheduler(timezone="local", job_defaults={
            "misfire_grace_time": 3600,   # allow up to 1-hour late start
            "coalesce":           True,   # run once even if multiple misfires
            "max_instances":      1,
        })
        # Callback injected by ui.py to show the permission popup
        self._ask_permission_cb: Optional[Callable[[], None]] = None
        # Callback injected by ui.py to send a desktop notification
        self._notify_cb: Optional[Callable[[str, str], None]] = None

    # ── Public API ───────────────────────────────────────────────────────────

    def register_permission_callback(self, cb: Callable[[], None]) -> None:
        """Register a callable that will show the 8 AM permission popup."""
        self._ask_permission_cb = cb

    def register_notify_callback(self, cb: Callable[[str, str], None]) -> None:
        """Register a callable(title, message) for desktop notifications."""
        self._notify_cb = cb

    def start(self) -> None:
        self._register_jobs()
        self._sched.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self._sched.start()
        logger.info("Scheduler started.")

    def stop(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    # ── Manual triggers (called from UI manual buttons) ──────────────────────

    def manual_clock_in(self) -> None:
        threading.Thread(target=self._do_clock_in, daemon=True).start()

    def manual_clock_out(self) -> None:
        threading.Thread(target=self._do_clock_out, daemon=True).start()

    # ── Job registration ─────────────────────────────────────────────────────

    def _register_jobs(self) -> None:
        # 8 AM permission check – Sunday through Friday
        self._sched.add_job(
            self._job_ask_permission,
            CronTrigger(
                day_of_week="sun,mon,tue,wed,thu,fri",
                hour=PERMISSION_HOUR,
                minute=PERMISSION_MINUTE,
            ),
            id="ask_permission",
            replace_existing=True,
        )

        # Clock-in at configured time every day
        self._sched.add_job(
            self._job_clock_in,
            CronTrigger(hour=CLOCKIN_HOUR, minute=CLOCKIN_MINUTE),
            id="clock_in",
            replace_existing=True,
        )

        # Clock-out at configured time every day
        self._sched.add_job(
            self._job_clock_out,
            CronTrigger(hour=CLOCKOUT_HOUR, minute=CLOCKOUT_MINUTE),
            id="clock_out",
            replace_existing=True,
        )

        # Retry loop every RETRY_INTERVAL seconds
        self._sched.add_job(
            self._job_retry_pending,
            IntervalTrigger(seconds=RETRY_INTERVAL),
            id="retry_pending",
            replace_existing=True,
        )

        logger.info(
            "Jobs registered: permission@%02d:%02d, clock-in@%02d:%02d, "
            "clock-out@%02d:%02d, retry every %ds",
            PERMISSION_HOUR, PERMISSION_MINUTE,
            CLOCKIN_HOUR, CLOCKIN_MINUTE,
            CLOCKOUT_HOUR, CLOCKOUT_MINUTE,
            RETRY_INTERVAL,
        )

    # ── Job implementations ──────────────────────────────────────────────────

    def _job_ask_permission(self) -> None:
        """Called at 8 AM.  Skip if permission was already set today."""
        today_perm = self._storage.get_today_permission()
        if today_perm is not None:
            logger.info("Permission already decided today (%s) – skipping popup.", today_perm)
            return

        if AUTO_APPROVE:
            logger.info("AUTO_APPROVE enabled – granting permission automatically.")
            self._storage.set_today_permission(True)
            self._notify("HRMS Auto Attendance", "Auto-approved for today ✅")
            return

        # Delegate to UI layer
        if self._ask_permission_cb:
            logger.info("Triggering permission popup …")
            self._ask_permission_cb()
        else:
            # Headless / no UI – default to auto-approve if no callback registered
            logger.warning("No permission callback registered; auto-approving.")
            self._storage.set_today_permission(True)

    def _job_clock_in(self) -> None:
        perm = self._storage.get_today_permission()
        if perm is not True:
            logger.info("Clock-in skipped – permission not granted (perm=%s).", perm)
            return

        if self._storage.task_already_succeeded("clock_in"):
            logger.info("Clock-in already succeeded today – no duplicate action.")
            return

        task_id = self._storage.create_task(
            "clock_in", datetime(
                *date.today().timetuple()[:3], CLOCKIN_HOUR, CLOCKIN_MINUTE
            )
        )
        self._execute_task(task_id, "clock_in")

    def _job_clock_out(self) -> None:
        perm = self._storage.get_today_permission()
        if perm is not True:
            logger.info("Clock-out skipped – permission not granted.")
            return

        if self._storage.task_already_succeeded("clock_out"):
            logger.info("Clock-out already succeeded today – no duplicate action.")
            return

        task_id = self._storage.create_task(
            "clock_out", datetime(
                *date.today().timetuple()[:3], CLOCKOUT_HOUR, CLOCKOUT_MINUTE
            )
        )
        self._execute_task(task_id, "clock_out")

    def _job_retry_pending(self) -> None:
        """Retry any pending tasks for today if we are online."""
        pending = self._storage.get_pending_tasks()
        if not pending:
            return

        if not is_online():
            logger.debug("Still offline – %d task(s) remain pending.", len(pending))
            return

        for task in pending:
            if task["retry_count"] >= MAX_RETRIES:
                self._storage.update_task(task["id"], "failed", "MAX_RETRIES exceeded")
                self._notify(
                    "HRMS – Task Failed",
                    f"{task['action_type'].replace('_', ' ').title()} failed after"
                    f" {MAX_RETRIES} retries.",
                )
                continue
            logger.info(
                "Retrying task %d (%s), attempt %d …",
                task["id"], task["action_type"], task["retry_count"] + 1,
            )
            self._execute_task(task["id"], task["action_type"])

    # ── Core execution ───────────────────────────────────────────────────────

    def _execute_task(self, task_id: int, action_type: str) -> None:
        """Run a clock-in or clock-out, update the task log, and notify."""
        from hrms_bot import HRMSBot  # deferred to avoid circular import

        if not is_online():
            logger.warning("Offline – task %d deferred.", task_id)
            # Attempt to re-enable WiFi
            from utils import try_enable_wifi
            try_enable_wifi()
            return  # will be retried by _job_retry_pending

        try:
            with HRMSBot() as bot:
                success = (
                    bot.clock_in()  if action_type == "clock_in"  else
                    bot.clock_out() if action_type == "clock_out" else False
                )
            status = "success" if success else "failed"
            self._storage.update_task(task_id, status)

            label = action_type.replace("_", " ").title()
            if success:
                self._notify("HRMS ✅", f"{label} completed successfully.")
                logger.info("Task %d (%s) → success.", task_id, action_type)
            else:
                self._notify("HRMS ⚠️", f"{label} failed – will retry.")
                logger.warning("Task %d (%s) → failed.", task_id, action_type)

        except Exception as exc:
            self._storage.update_task(task_id, "failed", str(exc))
            self._notify("HRMS ❌", f"Error during {action_type}: {exc}")
            logger.exception("Task %d raised exception: %s", task_id, exc)

    def _do_clock_in(self) -> None:
        """Thread target for manual clock-in."""
        if self._storage.task_already_succeeded("clock_in"):
            self._notify("HRMS", "Already clocked in today.")
            return
        task_id = self._storage.create_task("clock_in", datetime.now())
        self._execute_task(task_id, "clock_in")

    def _do_clock_out(self) -> None:
        """Thread target for manual clock-out."""
        if self._storage.task_already_succeeded("clock_out"):
            self._notify("HRMS", "Already clocked out today.")
            return
        task_id = self._storage.create_task("clock_out", datetime.now())
        self._execute_task(task_id, "clock_out")

    # ── APScheduler listener ─────────────────────────────────────────────────

    def _job_listener(self, event) -> None:
        if event.exception:
            logger.error("Scheduler job %s raised: %s", event.job_id, event.exception)
        else:
            logger.debug("Scheduler job %s completed.", event.job_id)

    # ── Helper ───────────────────────────────────────────────────────────────

    def _notify(self, title: str, message: str) -> None:
        if self._notify_cb:
            try:
                self._notify_cb(title, message)
            except Exception as exc:
                logger.debug("Notification failed: %s", exc)
