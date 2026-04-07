"""
storage.py – Thread-safe SQLite persistence layer.

Tables
------
daily_permission  – one row per calendar day; whether the user approved automation
task_log          – every scheduled/executed clock-in or clock-out attempt
"""
import sqlite3
import threading
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from config import DB_PATH, MAX_RETRIES

logger = logging.getLogger(__name__)


class Storage:
    """Thread-safe SQLite handler using per-call connections with WAL mode."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ── Internal helpers ────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Schema ──────────────────────────────────────────────────────────────

    def init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS daily_permission (
                    date        TEXT PRIMARY KEY,
                    enabled     INTEGER NOT NULL DEFAULT 0,
                    decided_at  TEXT
                );

                CREATE TABLE IF NOT EXISTS task_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    date            TEXT    NOT NULL,
                    action_type     TEXT    NOT NULL,
                    scheduled_time  TEXT    NOT NULL,
                    executed_time   TEXT,
                    status          TEXT    NOT NULL DEFAULT 'pending',
                    retry_count     INTEGER NOT NULL DEFAULT 0,
                    error_message   TEXT,
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_task_date_status
                    ON task_log (date, action_type, status);
            """)
        logger.info("Database ready at %s", DB_PATH)

    # ── Daily permission ────────────────────────────────────────────────────

    def get_today_permission(self) -> Optional[bool]:
        """Return True/False if decided today, None if not yet decided."""
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT enabled FROM daily_permission WHERE date = ?", (today,)
            ).fetchone()
        return None if row is None else bool(row["enabled"])

    def set_today_permission(self, enabled: bool) -> None:
        today = date.today().isoformat()
        now   = datetime.now().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO daily_permission (date, enabled, decided_at)"
                " VALUES (?, ?, ?)",
                (today, int(enabled), now),
            )
        logger.info("Daily permission for %s → %s", today, "YES" if enabled else "NO")

    # ── Task log ────────────────────────────────────────────────────────────

    def create_task(self, action_type: str, scheduled_time: datetime) -> int:
        """Insert a new pending task and return its row ID."""
        today = date.today().isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO task_log (date, action_type, scheduled_time, status)"
                " VALUES (?, ?, ?, 'pending')",
                (today, action_type, scheduled_time.isoformat()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def update_task(
        self, task_id: int, status: str, error: Optional[str] = None
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE task_log"
                " SET status = ?, executed_time = ?, error_message = ?,"
                "     retry_count = retry_count + 1"
                " WHERE id = ?",
                (status, now, error, task_id),
            )

    def task_already_succeeded(
        self, action_type: str, for_date: Optional[str] = None
    ) -> bool:
        """Return True if a successful execution already exists for today."""
        today = for_date or date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM task_log"
                " WHERE date = ? AND action_type = ? AND status = 'success'",
                (today, action_type),
            ).fetchone()
        return row is not None

    def get_pending_tasks(
        self, for_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return all pending tasks for a date that still have retries left."""
        today = for_date or date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_log"
                " WHERE date = ? AND status = 'pending' AND retry_count < ?"
                " ORDER BY scheduled_time ASC",
                (today, MAX_RETRIES),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_today_tasks(self) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_log WHERE date = ? ORDER BY scheduled_time ASC",
                (today,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_log WHERE id = ?", (task_id,)
            ).fetchone()
        return dict(row) if row else None
