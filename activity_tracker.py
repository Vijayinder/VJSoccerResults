"""
activity_tracker.py — Persistent activity logging using SQLite.

Stores the database in the same 'data/' directory as all JSON files,
so it survives app reboots on Streamlit Cloud and similar platforms.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone
from contextlib import contextmanager

# ── Database location ─────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "activity_log.db")

_lock = threading.Lock()

# ── Schema ────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    username      TEXT,
    full_name     TEXT,
    ip_address    TEXT,
    action_type   TEXT,
    league        TEXT,
    competition   TEXT,
    club          TEXT,
    search_query  TEXT,
    session_id    TEXT
);
"""

@contextmanager
def _get_conn():
    with _lock:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(_SCHEMA)
            conn.commit()
            yield conn
        finally:
            conn.close()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert(action_type: str, username: str = "", full_name: str = "",
            ip_address: str = "", league: str = "", competition: str = "",
            club: str = "", search_query: str = "", session_id: str = ""):
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO activity_log
               (timestamp, username, full_name, ip_address, action_type,
                league, competition, club, search_query, session_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (_now_utc(), username, full_name, ip_address, action_type,
             league, competition, club, search_query, session_id)
        )
        conn.commit()


# ── Public API ────────────────────────────────────────────

def log_login(username: str = "", full_name: str = "",
              ip_address: str = "", session_id: str = ""):
    _insert("login", username=username, full_name=full_name,
            ip_address=ip_address, session_id=session_id)


def log_logout(username: str = "", full_name: str = "",
               session_id: str = ""):
    _insert("logout", username=username, full_name=full_name,
            session_id=session_id)


def log_search(username: str = "", full_name: str = "",
               query: str = "", session_id: str = ""):
    _insert("search_query", username=username, full_name=full_name,
            search_query=query, session_id=session_id)


def log_view(username: str = "", full_name: str = "",
             view_type: str = "", league: str = "", competition: str = "",
             club: str = "", session_id: str = ""):
    _insert(f"view_{view_type}", username=username, full_name=full_name,
            league=league, competition=competition, club=club,
            session_id=session_id)


def get_recent_activity(limit: int = 50) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_user_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        unique_users = conn.execute(
            "SELECT COUNT(DISTINCT username) FROM activity_log WHERE username != ''"
        ).fetchone()[0]
        by_type = conn.execute(
            "SELECT action_type, COUNT(*) as cnt FROM activity_log GROUP BY action_type"
        ).fetchall()
        top_users = conn.execute(
            """SELECT username, full_name, COUNT(*) as activity_count
               FROM activity_log WHERE username != ''
               GROUP BY username ORDER BY activity_count DESC LIMIT 10"""
        ).fetchall()
        top_clubs = conn.execute(
            """SELECT club, COUNT(*) as cnt FROM activity_log
               WHERE club != '' GROUP BY club ORDER BY cnt DESC LIMIT 10"""
        ).fetchall()

    return {
        "total_activities":  total,
        "unique_users":      unique_users,
        "activities_by_type": {r["action_type"]: r["cnt"] for r in by_type},
        "most_active_users": [dict(r) for r in top_users],
        "top_clubs":         {r["club"]: r["cnt"] for r in top_clubs},
    }


def get_active_users_today() -> list:
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT username, full_name, MAX(timestamp) as last_activity,
                      COUNT(*) as activity_count
               FROM activity_log
               WHERE timestamp LIKE ? AND username != ''
               GROUP BY username
               ORDER BY last_activity DESC""",
            (f"{today_prefix}%",)
        ).fetchall()
    return [dict(r) for r in rows]
