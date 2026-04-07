"""
storage.py – SQLite persistence layer for HRMS attendance automation.

Tables:
  daily_permission  – stores per-day YES/NO permission
  tasks             – scheduled / pending / completed tasks
  logs              – execution audit log
"""

import sqlite3
import logging
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "hrms_data.db"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they do not already exist."""
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_permission (
                date        TEXT PRIMARY KEY,  -- YYYY-MM-DD
                permitted   INTEGER NOT NULL,  -- 1 = YES, 0 = NO
                asked_at    TEXT               -- ISO-8601 timestamp
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT NOT NULL,          -- YYYY-MM-DD
                action_type     TEXT NOT NULL,          -- 'clock_in' | 'clock_out'
                scheduled_time  TEXT NOT NULL,          -- ISO-8601
                executed_time   TEXT,                   -- ISO-8601, NULL until done
                status          TEXT NOT NULL DEFAULT 'pending',  -- pending/success/failed
                retries         INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     INTEGER,
                timestamp   TEXT NOT NULL,
                level       TEXT NOT NULL,
                message     TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );
            """
        )
    logger.info("Database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Context-manager helper
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Daily permission
# ---------------------------------------------------------------------------

def set_permission(day: date, permitted: bool) -> None:
    """Persist today's permission decision."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO daily_permission (date, permitted, asked_at)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET permitted=excluded.permitted,
                                            asked_at=excluded.asked_at
            """,
            (day.isoformat(), int(permitted), datetime.now().isoformat()),
        )


def get_permission(day: date) -> bool | None:
    """Return True/False if permission was recorded today, else None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT permitted FROM daily_permission WHERE date = ?",
            (day.isoformat(),),
        ).fetchone()
    return bool(row["permitted"]) if row is not None else None


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def upsert_task(
    day: date,
    action_type: str,
    scheduled_time: datetime,
) -> int:
    """
    Insert a task for *day* and *action_type* if one does not already exist.
    Returns the task id.
    """
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM tasks WHERE date=? AND action_type=?",
            (day.isoformat(), action_type),
        ).fetchone()
        if existing:
            return existing["id"]
        cur = conn.execute(
            """
            INSERT INTO tasks (date, action_type, scheduled_time, status, retries, created_at)
            VALUES (?, ?, ?, 'pending', 0, ?)
            """,
            (
                day.isoformat(),
                action_type,
                scheduled_time.isoformat(),
                datetime.now().isoformat(),
            ),
        )
        return cur.lastrowid


def get_task(day: date, action_type: str):
    """Return task row or None."""
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE date=? AND action_type=?",
            (day.isoformat(), action_type),
        ).fetchone()


def mark_task_success(task_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='success', executed_time=? WHERE id=?",
            (datetime.now().isoformat(), task_id),
        )


def mark_task_failed(task_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='failed', executed_time=? WHERE id=?",
            (datetime.now().isoformat(), task_id),
        )


def increment_retries(task_id: int) -> int:
    """Increment retry counter and return new value."""
    with _conn() as conn:
        conn.execute(
            "UPDATE tasks SET retries = retries + 1 WHERE id=?",
            (task_id,),
        )
        row = conn.execute(
            "SELECT retries FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        return row["retries"]


def get_pending_tasks(day: date | None = None):
    """Return all pending tasks, optionally filtered by date."""
    with _conn() as conn:
        if day:
            return conn.execute(
                "SELECT * FROM tasks WHERE status='pending' AND date=? ORDER BY scheduled_time",
                (day.isoformat(),),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM tasks WHERE status='pending' ORDER BY scheduled_time"
        ).fetchall()


def get_tasks_for_day(day: date):
    """Return all tasks for a given day."""
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE date=? ORDER BY scheduled_time",
            (day.isoformat(),),
        ).fetchall()


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

def add_log(task_id: int | None, level: str, message: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO logs (task_id, timestamp, level, message) VALUES (?,?,?,?)",
            (task_id, datetime.now().isoformat(), level, message),
        )


def get_recent_logs(limit: int = 100):
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
