"""
activity_tracker.py
====================
Persistent activity logging for the Dribl Stats app.

Storage: SQLite at <app_dir>/data/activity_log.db  (same folder as your JSON data files).
Fallback: JSON flat-file at <app_dir>/data/activity_log.json if SQLite unavailable.

Place this file next to app.py. The data/ folder must persist on your host
for logs to survive reboots (same requirement as your match JSON files).
"""

import os, json, sqlite3, threading
from datetime import datetime, timezone
from contextlib import contextmanager

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
os.makedirs(_DATA_DIR, exist_ok=True)

DB_PATH   = os.path.join(_DATA_DIR, "activity_log.db")
JSON_PATH = os.path.join(_DATA_DIR, "activity_log.json")   # fallback

_lock = threading.Lock()

_DDL = """
CREATE TABLE IF NOT EXISTS activity_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    username      TEXT DEFAULT '',
    full_name     TEXT DEFAULT '',
    ip_address    TEXT DEFAULT '',
    action_type   TEXT DEFAULT '',
    league        TEXT DEFAULT '',
    competition   TEXT DEFAULT '',
    club          TEXT DEFAULT '',
    search_query  TEXT DEFAULT '',
    session_id    TEXT DEFAULT ''
);
"""

@contextmanager
def _conn():
    with _lock:
        c = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        try:
            c.execute(_DDL)
            c.commit()
            yield c
        finally:
            c.close()

def _now():
    return datetime.now(timezone.utc).isoformat()

def _json_load():
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _json_append(row):
    rows = _json_load()
    rows.append(row)
    rows = rows[-10_000:]
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

def _insert(action_type="", username="", full_name="", ip_address="",
            league="", competition="", club="", search_query="", session_id=""):
    row = dict(timestamp=_now(), username=username, full_name=full_name,
               ip_address=ip_address, action_type=action_type, league=league,
               competition=competition, club=club, search_query=search_query,
               session_id=session_id)
    try:
        with _conn() as c:
            c.execute(
                """INSERT INTO activity_log
                   (timestamp,username,full_name,ip_address,action_type,
                    league,competition,club,search_query,session_id)
                   VALUES (:timestamp,:username,:full_name,:ip_address,:action_type,
                           :league,:competition,:club,:search_query,:session_id)""", row)
            c.commit()
    except Exception:
        try:
            _json_append(row)
        except Exception:
            pass

# ── Public API ─────────────────────────────────────────────────────────────────

def log_login(username="", full_name="", ip_address="", session_id=""):
    _insert("login", username=username, full_name=full_name,
            ip_address=ip_address, session_id=session_id)

def log_logout(username="", full_name="", session_id=""):
    _insert("logout", username=username, full_name=full_name, session_id=session_id)

def log_search(username="", full_name="", query="", session_id=""):
    _insert("search_query", username=username, full_name=full_name,
            search_query=query, session_id=session_id)

def log_view(username="", full_name="", view_type="", league="",
             competition="", club="", session_id=""):
    _insert(f"view_{view_type}", username=username, full_name=full_name,
            league=league, competition=competition, club=club, session_id=session_id)

def get_recent_activity(limit=50):
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        rows = _json_load()
        return list(reversed(rows[-limit:]))

def get_user_stats():
    try:
        with _conn() as c:
            total        = c.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
            unique_users = c.execute(
                "SELECT COUNT(DISTINCT username) FROM activity_log WHERE username!=''").fetchone()[0]
            by_type      = c.execute(
                "SELECT action_type, COUNT(*) cnt FROM activity_log GROUP BY action_type").fetchall()
            top_users    = c.execute(
                """SELECT username, full_name, COUNT(*) activity_count
                   FROM activity_log WHERE username!=''
                   GROUP BY username ORDER BY activity_count DESC LIMIT 10""").fetchall()
            top_clubs    = c.execute(
                """SELECT club, COUNT(*) cnt FROM activity_log
                   WHERE club!='' GROUP BY club ORDER BY cnt DESC LIMIT 10""").fetchall()
            top_searches = c.execute(
                """SELECT search_query, COUNT(*) cnt FROM activity_log
                   WHERE search_query!='' GROUP BY search_query
                   ORDER BY cnt DESC LIMIT 20""").fetchall()
        return {
            "total_activities":   total,
            "unique_users":       unique_users,
            "activities_by_type": {r["action_type"]: r["cnt"] for r in by_type},
            "most_active_users":  [dict(r) for r in top_users],
            "top_clubs":          {r["club"]: r["cnt"] for r in top_clubs},
            "top_searches":       [dict(r) for r in top_searches],
        }
    except Exception:
        rows = _json_load()
        by_type: dict = {}
        for r in rows:
            k = r.get("action_type", "")
            by_type[k] = by_type.get(k, 0) + 1
        users = {r.get("username") for r in rows if r.get("username")}
        return {"total_activities": len(rows), "unique_users": len(users),
                "activities_by_type": by_type, "most_active_users": [],
                "top_clubs": {}, "top_searches": []}

def get_active_users_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with _conn() as c:
            rows = c.execute(
                """SELECT username, full_name, MAX(timestamp) last_activity,
                          COUNT(*) activity_count
                   FROM activity_log
                   WHERE timestamp LIKE ? AND username!=''
                   GROUP BY username ORDER BY last_activity DESC""",
                (f"{today}%",)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        rows = _json_load()
        seen: dict = {}
        for r in rows:
            if not r.get("timestamp","").startswith(today) or not r.get("username"):
                continue
            u = r["username"]
            if u not in seen:
                seen[u] = {"username": u, "full_name": r.get("full_name",""),
                           "last_activity": r["timestamp"], "activity_count": 0}
            seen[u]["activity_count"] += 1
            if r["timestamp"] > seen[u]["last_activity"]:
                seen[u]["last_activity"] = r["timestamp"]
        return sorted(seen.values(), key=lambda x: x["last_activity"], reverse=True)
