import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DB


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with connection() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY, path TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY, body TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, ticket_id TEXT, status TEXT NOT NULL,
            error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            idempotency_key TEXT UNIQUE, FOREIGN KEY(ticket_id) REFERENCES tickets(id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS presets (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, design TEXT NOT NULL
        );
        """)


def fail_interrupted_jobs():
    # The worker alone owns job recovery; an API restart must not affect an active transfer.
    with connection() as db:
        db.execute("UPDATE jobs SET status='failed', error='Interrupted by worker restart', updated_at=? WHERE status IN ('rendering','printing')", (now(),))


def setting(key, default=None):
    with connection() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key, value):
    with connection() as db:
        db.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
