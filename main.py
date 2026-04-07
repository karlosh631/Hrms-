"""
main.py – Entry point for HRMS AutoAttendance.

Wires together: storage, scheduler, UI (tray + popup).

Usage:
    python main.py
"""

import logging
import sys
from datetime import date

import storage
import utils
import scheduler as sched_module
import ui


def _on_permission_response(day: date, granted: bool) -> None:
    """Callback invoked when the user answers the 8 AM popup."""
    storage.set_permission(day, granted)
    storage.add_log(None, "INFO", f"Permission for {day}: {'YES' if granted else 'NO'}")

    label = "enabled" if granted else "disabled"
    utils.notify(
        "HRMS AutoAttendance",
        f"Auto attendance {label} for today ({day}).",
    )

    if granted:
        from datetime import datetime
        # Pre-create task records so they show in tray status immediately
        today = date.today()
        ci_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        co_time = datetime.now().replace(hour=17, minute=5, second=0, microsecond=0)
        storage.upsert_task(today, "clock_in", ci_time)
        storage.upsert_task(today, "clock_out", co_time)


def _permission_popup_callback(day: date) -> None:
    """Called by the scheduler at 8 AM; opens the UI dialog."""
    ui.ask_permission(day, lambda granted: _on_permission_response(day, granted))


def _manual_clock_in() -> None:
    from scheduler import execute_task
    today = date.today()
    from datetime import datetime
    task_id = storage.upsert_task(
        today, "clock_in", datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    )
    execute_task(task_id, "clock_in")


def _manual_clock_out() -> None:
    from scheduler import execute_task
    today = date.today()
    from datetime import datetime
    task_id = storage.upsert_task(
        today, "clock_out", datetime.now().replace(hour=17, minute=5, second=0, microsecond=0)
    )
    execute_task(task_id, "clock_out")


def main() -> None:
    utils.setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("HRMS AutoAttendance starting …")

    # Initialise database
    storage.init_db()

    # Register permission callback so scheduler can open the popup
    sched_module.set_permission_callback(_permission_popup_callback)

    # Build and start the APScheduler background scheduler
    scheduler = sched_module.build_scheduler()
    scheduler.start()
    logger.info("Scheduler started.")

    # Recover any missed same-day tasks from a previous run
    sched_module.recover_missed_tasks()

    # Build tray app (may be headless if PyQt5 is unavailable)
    tray = ui.TrayApp(
        on_clock_in=_manual_clock_in,
        on_clock_out=_manual_clock_out,
    )

    logger.info("HRMS AutoAttendance running. Minimise to system tray.")

    try:
        tray.run_event_loop()
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped. Goodbye.")


if __name__ == "__main__":
    main()
