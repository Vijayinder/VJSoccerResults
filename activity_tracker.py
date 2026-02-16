# activity_tracker.py - User Activity Tracking

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz
from config import ACTIVITY_DB_PATH, ENABLE_ACTIVITY_TRACKING, LOG_RETENTION_DAYS

# ---------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------

def init_database():
    """Initialize the activity tracking database"""
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    cursor = conn.cursor()
    
    # Create activity logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            username TEXT NOT NULL,
            full_name TEXT,
            action_type TEXT NOT NULL,
            action_details TEXT,
            league TEXT,
            competition TEXT,
            club TEXT,
            player TEXT,
            search_query TEXT,
            session_id TEXT,
            ip_address TEXT
        )
    ''')
    
    # Create index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON activity_logs(timestamp DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_username 
        ON activity_logs(username)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_action_type 
        ON activity_logs(action_type)
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on import
if ENABLE_ACTIVITY_TRACKING:
    init_database()

# ---------------------------------------------------------
# Activity Logging Functions
# ---------------------------------------------------------

def log_activity(username, full_name, action_type, ip_address="Unknown", **kwargs):
    """Log any activity to CSV"""
    log_file = os.path.join(LOGS_DIR, "activity_log.csv")
    
    # Prepare log entry
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": username,
        "full_name": full_name,
        "action_type": action_type,
        "ip_address": ip_address,  # ✅ Add this
        "session_id": kwargs.get("session_id", ""),
        "league": kwargs.get("league", ""),
        "competition": kwargs.get("competition", ""),
        "club": kwargs.get("club", ""),
        "player": kwargs.get("player", ""),
        "search_query": kwargs.get("search_query", "")
    }
    
def log_activity(
    username: str,
    action_type: str,
    full_name: str = "",
    action_details: str = "",
    league: str = None,
    competition: str = None,
    club: str = None,
    player: str = None,
    search_query: str = None,
    session_id: str = None,
    ip_address: str = None
):
    """
    Log a user activity
    
    Action types:
    - login
    - logout
    - view_league
    - view_competition
    - view_ladder
    - view_club
    - view_player
    - search_query
    - view_fixtures
    - view_stats
    """
    if not ENABLE_ACTIVITY_TRACKING:
        return
    
    try:
        conn = sqlite3.connect(ACTIVITY_DB_PATH)
        cursor = conn.cursor()
        
        # Get current timestamp in AEST
        aest = pytz.timezone('Australia/Melbourne')
        timestamp = datetime.now(aest)
        
        cursor.execute('''
            INSERT INTO activity_logs 
            (timestamp, username, full_name, action_type, action_details, 
             league, competition, club, player, search_query, session_id, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp.isoformat(),
            username,
            full_name,
            action_type,
            action_details,
            league,
            competition,
            club,
            player,
            search_query,
            session_id,
            ip_address
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging activity: {e}")

# ---------------------------------------------------------
# Activity Retrieval Functions
# ---------------------------------------------------------

def get_recent_activity(limit: int = 100, username: str = None) -> List[Dict[str, Any]]:
    """Get recent activity logs"""
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if username:
        cursor.execute('''
            SELECT * FROM activity_logs 
            WHERE username = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (username, limit))
    else:
        cursor.execute('''
            SELECT * FROM activity_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_activity_by_date_range(
    start_date: datetime,
    end_date: datetime,
    username: str = None
) -> List[Dict[str, Any]]:
    """Get activity logs within a date range"""
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if username:
        cursor.execute('''
            SELECT * FROM activity_logs 
            WHERE timestamp BETWEEN ? AND ?
            AND username = ?
            ORDER BY timestamp DESC
        ''', (start_date.isoformat(), end_date.isoformat(), username))
    else:
        cursor.execute('''
            SELECT * FROM activity_logs 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        ''', (start_date.isoformat(), end_date.isoformat()))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_user_stats(username: str = None) -> Dict[str, Any]:
    """Get statistics about user activity"""
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    # Total activities
    if username:
        cursor.execute('SELECT COUNT(*) FROM activity_logs WHERE username = ?', (username,))
    else:
        cursor.execute('SELECT COUNT(*) FROM activity_logs')
    stats['total_activities'] = cursor.fetchone()[0]
    
    # Unique users
    if not username:
        cursor.execute('SELECT COUNT(DISTINCT username) FROM activity_logs')
        stats['unique_users'] = cursor.fetchone()[0]
    
    # Activities by type
    if username:
        cursor.execute('''
            SELECT action_type, COUNT(*) as count 
            FROM activity_logs 
            WHERE username = ?
            GROUP BY action_type 
            ORDER BY count DESC
        ''', (username,))
    else:
        cursor.execute('''
            SELECT action_type, COUNT(*) as count 
            FROM activity_logs 
            GROUP BY action_type 
            ORDER BY count DESC
        ''')
    stats['activities_by_type'] = dict(cursor.fetchall())
    
    # Most viewed clubs
    if username:
        cursor.execute('''
            SELECT club, COUNT(*) as count 
            FROM activity_logs 
            WHERE club IS NOT NULL AND username = ?
            GROUP BY club 
            ORDER BY count DESC 
            LIMIT 10
        ''', (username,))
    else:
        cursor.execute('''
            SELECT club, COUNT(*) as count 
            FROM activity_logs 
            WHERE club IS NOT NULL 
            GROUP BY club 
            ORDER BY count DESC 
            LIMIT 10
        ''')
    stats['top_clubs'] = dict(cursor.fetchall())
    
    # Most viewed players
    if username:
        cursor.execute('''
            SELECT player, COUNT(*) as count 
            FROM activity_logs 
            WHERE player IS NOT NULL AND username = ?
            GROUP BY player 
            ORDER BY count DESC 
            LIMIT 10
        ''', (username,))
    else:
        cursor.execute('''
            SELECT player, COUNT(*) as count 
            FROM activity_logs 
            WHERE player IS NOT NULL 
            GROUP BY player 
            ORDER BY count DESC 
            LIMIT 10
        ''')
    stats['top_players'] = dict(cursor.fetchall())
    
    # Recent searches
    if username:
        cursor.execute('''
            SELECT search_query, timestamp 
            FROM activity_logs 
            WHERE search_query IS NOT NULL AND username = ?
            ORDER BY timestamp DESC 
            LIMIT 20
        ''', (username,))
    else:
        cursor.execute('''
            SELECT search_query, timestamp 
            FROM activity_logs 
            WHERE search_query IS NOT NULL 
            ORDER BY timestamp DESC 
            LIMIT 20
        ''')
    stats['recent_searches'] = [(row[0], row[1]) for row in cursor.fetchall()]
    
    # Activity over time (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    if username:
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM activity_logs 
            WHERE timestamp >= ? AND username = ?
            GROUP BY DATE(timestamp) 
            ORDER BY date DESC
        ''', (thirty_days_ago.isoformat(), username))
    else:
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM activity_logs 
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp) 
            ORDER BY date DESC
        ''', (thirty_days_ago.isoformat(),))
    stats['daily_activity'] = dict(cursor.fetchall())
    
    # Most active users (if not filtering by username)
    if not username:
        cursor.execute('''
            SELECT username, full_name, COUNT(*) as count 
            FROM activity_logs 
            GROUP BY username 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        stats['most_active_users'] = [
            {'username': row[0], 'full_name': row[1], 'count': row[2]}
            for row in cursor.fetchall()
        ]
    
    conn.close()
    return stats

def get_active_users_today() -> List[Dict[str, Any]]:
    """Get list of users who were active today"""
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().date()
    cursor.execute('''
        SELECT DISTINCT username, full_name, MAX(timestamp) as last_activity
        FROM activity_logs 
        WHERE DATE(timestamp) = ?
        GROUP BY username
        ORDER BY last_activity DESC
    ''', (today.isoformat(),))
    
    users = [
        {
            'username': row[0],
            'full_name': row[1],
            'last_activity': row[2]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return users

# ---------------------------------------------------------
# Database Maintenance
# ---------------------------------------------------------

def cleanup_old_logs():
    """Remove logs older than retention period"""
    if not ENABLE_ACTIVITY_TRACKING:
        return
    
    try:
        conn = sqlite3.connect(ACTIVITY_DB_PATH)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        
        cursor.execute('''
            DELETE FROM activity_logs 
            WHERE timestamp < ?
        ''', (cutoff_date.isoformat(),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count
    except Exception as e:
        print(f"Error cleaning up logs: {e}")
        return 0

def export_activity_logs(filepath: str, username: str = None):
    """Export activity logs to CSV"""
    import csv
    
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    cursor = conn.cursor()
    
    if username:
        cursor.execute('SELECT * FROM activity_logs WHERE username = ? ORDER BY timestamp DESC', (username,))
    else:
        cursor.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC')
    
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    conn.close()
    return len(rows)

# ---------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------


def log_login(username: str, full_name: str, session_id: str, ip_address: str = "Unknown"):
    """Log user login with IP address"""
    log_activity(
        username=username,
        full_name=full_name,
        action_type="login",
        session_id=session_id,
        ip_address=ip_address  # ✅ Add this parameter
    )
    
def log_logout(username: str, full_name: str, session_id: str = None):
    """Log user logout"""
    log_activity(username, 'logout', full_name=full_name, session_id=session_id)

def log_search(username: str, full_name: str, query: str, session_id: str = None):
    """Log search query"""
    log_activity(
        username, 
        'search_query', 
        full_name=full_name,
        search_query=query,
        session_id=session_id
    )

def log_view(
    username: str,
    full_name: str,
    view_type: str,
    league: str = None,
    competition: str = None,
    club: str = None,
    player: str = None,
    session_id: str = None
):
    """Log a view action"""
    log_activity(
        username,
        f'view_{view_type}',
        full_name=full_name,
        league=league,
        competition=competition,
        club=club,
        player=player,
        session_id=session_id
    )
