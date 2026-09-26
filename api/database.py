"""
api/database.py — SQLite-backed detection history.

Replaces the CSV-based history (src/history.py) with a proper database
that handles concurrent access safely. This is the backend version;
src/history.py remains for the Streamlit demo.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from api.schemas import HistoryEntry, HistoryStats

# ── Database path ──────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "vaniguard.db"

# Thread-local storage for connections
_local = threading.local()


def _ensure_dir() -> None:
    """Create the data directory if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Get a thread-local SQLite connection.

    Uses WAL journal mode for better concurrent read performance.
    """
    _ensure_dir()
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.row_factory = sqlite3.Row
    try:
        yield _local.conn
    except Exception:
        _local.conn.rollback()
        raise


def init_db() -> None:
    """Create the history table if it does not exist."""
    _ensure_dir()
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                filename      TEXT    NOT NULL,
                verdict       TEXT    NOT NULL,
                confidence_pct REAL   NOT NULL,
                risk_band     TEXT    NOT NULL,
                probability   REAL   NOT NULL
            )
        """)
        conn.commit()


def save_detection(
    filename: str,
    verdict: str,
    confidence_pct: float,
    risk_band: str,
    probability: float,
) -> int:
    """
    Insert a detection result and return the new row ID.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO history (timestamp, filename, verdict, confidence_pct, risk_band, probability)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                filename,
                verdict,
                round(confidence_pct, 1),
                risk_band,
                round(probability, 4),
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def get_history(limit: int = 100, offset: int = 0) -> list[HistoryEntry]:
    """
    Retrieve detection history, newest first.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            HistoryEntry(
                id=row["id"],
                timestamp=row["timestamp"],
                filename=row["filename"],
                verdict=row["verdict"],
                confidence_pct=row["confidence_pct"],
                risk_band=row["risk_band"],
                probability=row["probability"],
            )
            for row in rows
        ]


def get_stats() -> HistoryStats:
    """
    Compute aggregate statistics from the history table.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                                        AS total,
                SUM(CASE WHEN verdict LIKE '%AI%' THEN 1 ELSE 0 END) AS ai_detected,
                SUM(CASE WHEN verdict = 'Human' THEN 1 ELSE 0 END)  AS human_detected,
                SUM(CASE WHEN verdict = 'UNCERTAIN' THEN 1 ELSE 0 END) AS uncertain,
                COALESCE(AVG(confidence_pct), 0.0)                AS avg_confidence
            FROM history
            """
        ).fetchone()

        total = row["total"] or 0
        ai_detected = row["ai_detected"] or 0
        return HistoryStats(
            total=total,
            ai_detected=ai_detected,
            human_detected=row["human_detected"] or 0,
            uncertain=row["uncertain"] or 0,
            ai_detection_rate=round((ai_detected / total * 100) if total else 0.0, 1),
            avg_confidence=round(row["avg_confidence"] or 0.0, 1),
        )


def get_total_count() -> int:
    """Return the total number of history records."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM history").fetchone()
        return row["cnt"] or 0


def clear_all_history() -> int:
    """Delete all history records. Returns the number of deleted rows."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM history")
        conn.commit()
        return cursor.rowcount
