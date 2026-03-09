"""
activity_tracker.py  —  Google Sheets backend
================================================
All credentials come from Streamlit secrets — nothing sensitive in code.

Secrets format (paste into Streamlit Cloud → Settings → Secrets):
──────────────────────────────────────────────────────────────────
ACTIVITY_SHEET_ID = "your_google_sheet_id_here"

[gcp_service_account]
type                        = "service_account"
project_id                  = "your-project-id"
private_key_id              = "abc123..."
private_key                 = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email                = "dribl-stats@your-project.iam.gserviceaccount.com"
client_id                   = "123456789"
auth_uri                    = "https://accounts.google.com/o/oauth2/auth"
token_uri                   = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url        = "https://www.googleapis.com/robot/v1/metadata/x509/..."
──────────────────────────────────────────────────────────────────

Local dev (.streamlit/secrets.toml — git-ignored):
Same format as above, stored in your local .streamlit/secrets.toml file.
"""

import threading
import queue
from datetime import datetime, timezone
from typing import Optional

# ── Optional imports (graceful fallback if libraries missing) ─────────────────
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False

_GSPREAD_ERROR = ""
try:
    import gspread
    from google.oauth2.service_account import Credentials
    _HAS_GSPREAD = True
except Exception as _e:
    _HAS_GSPREAD = False
    _GSPREAD_ERROR = str(_e)

# ── Sheet configuration ───────────────────────────────────────────────────────
_SHEET_NAME   = "activity_log"    # tab name inside your Google Sheet
_SCOPES       = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
_COLUMNS = [
    "timestamp", "username", "full_name", "ip_address",
    "action_type", "league", "competition", "club",
    "search_query", "session_id",
]

# ── Write queue — all writes happen in a background thread ────────────────────
# This means UI is never blocked waiting for the Sheets API.
_write_queue: queue.Queue = queue.Queue()
_worker_started = False
_worker_lock    = threading.Lock()

# ── Internal cache for reads (avoids hammering Sheets API) ───────────────────
_read_cache: dict = {}          # key → (data, expires_at_timestamp)
_CACHE_TTL = 30                 # seconds


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_get(key: str):
    entry = _read_cache.get(key)
    if entry and datetime.now(timezone.utc).timestamp() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, value):
    _read_cache[key] = (value, datetime.now(timezone.utc).timestamp() + _CACHE_TTL)


# ── Google Sheets client ──────────────────────────────────────────────────────
def _get_client() -> Optional["gspread.Client"]:
    """Build an authorised gspread client from Streamlit secrets."""
    if not _HAS_GSPREAD or not _HAS_ST:
        return None
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        # gspread wants the private_key newlines unescaped
        if "\\n" in creds_dict.get("private_key", ""):
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None


def _get_sheet() -> Optional["gspread.Worksheet"]:
    """Open the activity worksheet, creating the header row if needed."""
    client = _get_client()
    if not client:
        return None
    try:
        sheet_id = st.secrets.get("ACTIVITY_SHEET_ID", "")
        if not sheet_id:
            return None
        spreadsheet = client.open_by_key(sheet_id)
        try:
            ws = spreadsheet.worksheet(_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=_SHEET_NAME, rows=1, cols=len(_COLUMNS))
            ws.append_row(_COLUMNS, value_input_option="RAW")
        # Add header row if sheet is completely empty
        if ws.row_count == 0 or not ws.row_values(1):
            ws.append_row(_COLUMNS, value_input_option="RAW")
        return ws
    except Exception:
        return None


# ── Background writer thread ──────────────────────────────────────────────────
def _writer_loop():
    """Consume rows from _write_queue and append them to Google Sheets."""
    while True:
        try:
            row = _write_queue.get(timeout=5)
        except queue.Empty:
            continue
        # Drain up to 20 rows and batch-append
        batch = [row]
        try:
            while len(batch) < 20:
                batch.append(_write_queue.get_nowait())
        except queue.Empty:
            pass

        try:
            ws = _get_sheet()
            if ws:
                values = [[r.get(c, "") for c in _COLUMNS] for r in batch]
                ws.append_rows(values, value_input_option="RAW")
        except Exception:
            pass   # silently drop — never crash the app

        for _ in batch:
            _write_queue.task_done()


def _ensure_worker():
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            t = threading.Thread(target=_writer_loop, daemon=True)
            t.start()
            _worker_started = True


def _enqueue(action_type="", username="", full_name="", ip_address="",
             league="", competition="", club="", search_query="", session_id=""):
    _ensure_worker()
    _write_queue.put({
        "timestamp":    _now(),
        "username":     username,
        "full_name":    full_name,
        "ip_address":   ip_address,
        "action_type":  action_type,
        "league":       league,
        "competition":  competition,
        "club":         club,
        "search_query": search_query,
        "session_id":   session_id,
    })
    # Invalidate read cache on every write
    _read_cache.clear()


# ── Public write API (identical signatures to old activity_tracker.py) ────────

def log_login(username="", full_name="", ip_address="", session_id=""):
    _enqueue("login", username=username, full_name=full_name,
             ip_address=ip_address, session_id=session_id)


def log_logout(username="", full_name="", session_id=""):
    _enqueue("logout", username=username, full_name=full_name,
             session_id=session_id)


def log_search(username="", full_name="", query="", session_id=""):
    _enqueue("search_query", username=username, full_name=full_name,
             search_query=query, session_id=session_id)


def log_view(username="", full_name="", view_type="", league="",
             competition="", club="", session_id=""):
    _enqueue(f"view_{view_type}", username=username, full_name=full_name,
             league=league, competition=competition, club=club,
             session_id=session_id)



def check_connection() -> dict:
    """
    Test the Google Sheets connection.
    Returns {"ok": True/False, "message": "..."}.
    Called by the admin dashboard to show the status dot.
    """
    if not _HAS_GSPREAD:
        return {"ok": False, "message": f"gspread import failed — {_GSPREAD_ERROR or 'unknown error'}"}
    if not _HAS_ST:
        return {"ok": False, "message": "streamlit not available"}
    try:
        ws = _get_sheet()
        if ws is None:
            return {"ok": False, "message": "Could not open sheet — check ACTIVITY_SHEET_ID and gcp_service_account in Streamlit Secrets"}
        return {"ok": True, "message": f"Connected to sheet: {ws.spreadsheet.title} → {ws.title}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

# ── Public read API ───────────────────────────────────────────────────────────

def _all_rows() -> list[dict]:
    """Fetch all rows from the sheet, with caching."""
    cached = _cache_get("all_rows")
    if cached is not None:
        return cached
    try:
        ws = _get_sheet()
        if not ws:
            return []
        records = ws.get_all_records(expected_headers=_COLUMNS)
        _cache_set("all_rows", records)
        return records
    except Exception:
        return []


def get_recent_activity(limit: int = 50) -> list:
    rows = _all_rows()
    return list(reversed(rows[-limit:])) if rows else []


def get_user_stats() -> dict:
    cached = _cache_get("user_stats")
    if cached:
        return cached

    rows = _all_rows()
    if not rows:
        return {"total_activities": 0, "unique_users": 0,
                "activities_by_type": {}, "most_active_users": [],
                "top_clubs": {}, "top_searches": []}

    total = len(rows)
    user_counts: dict = {}
    type_counts: dict = {}
    club_counts:  dict = {}
    query_counts: dict = {}

    for r in rows:
        u = r.get("username", "")
        if u:
            user_counts[u] = user_counts.get(u, {"count": 0,
                                                  "full_name": r.get("full_name", "")})
            user_counts[u]["count"] += 1

        t = r.get("action_type", "")
        type_counts[t] = type_counts.get(t, 0) + 1

        c = r.get("club", "")
        if c:
            club_counts[c] = club_counts.get(c, 0) + 1

        q = r.get("search_query", "")
        if q:
            query_counts[q] = query_counts.get(q, 0) + 1

    top_users = sorted(
        [{"username": u, "full_name": v["full_name"], "activity_count": v["count"]}
         for u, v in user_counts.items()],
        key=lambda x: x["activity_count"], reverse=True
    )[:10]

    top_searches = sorted(
        [{"search_query": q, "cnt": n} for q, n in query_counts.items()],
        key=lambda x: x["cnt"], reverse=True
    )[:20]

    result = {
        "total_activities":   total,
        "unique_users":       len(user_counts),
        "activities_by_type": type_counts,
        "most_active_users":  top_users,
        "top_clubs":          dict(sorted(club_counts.items(),
                                          key=lambda x: x[1], reverse=True)[:10]),
        "top_searches":       top_searches,
    }
    _cache_set("user_stats", result)
    return result


def get_active_users_today() -> list:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows  = _all_rows()
    seen: dict = {}
    for r in rows:
        if not r.get("timestamp", "").startswith(today):
            continue
        u = r.get("username", "")
        if not u:
            continue
        if u not in seen:
            seen[u] = {"username": u, "full_name": r.get("full_name", ""),
                       "last_activity": r["timestamp"], "activity_count": 0}
        seen[u]["activity_count"] += 1
        if r["timestamp"] > seen[u]["last_activity"]:
            seen[u]["last_activity"] = r["timestamp"]
    return sorted(seen.values(), key=lambda x: x["last_activity"], reverse=True)
