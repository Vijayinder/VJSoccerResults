# player_config.py - Player-Based Authentication System
# ================================================
# Users select their player profile instead of username/password
# Admin users can still login with credentials
# ================================================

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import streamlit as st

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_SELECTIONS_DB = os.path.join(BASE_DIR, "player_selections.db")

# Try to import Streamlit (only available when app is running)
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

# ---------------------------------------------------------
# Database Setup
# ---------------------------------------------------------

def init_player_selections_db():
    """Initialize the player selections database"""
    conn = sqlite3.connect(PLAYER_SELECTIONS_DB)
    cursor = conn.cursor()
    
    # Create table for tracking player selections
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            player_name TEXT NOT NULL,
            player_id TEXT,
            club_name TEXT NOT NULL,
            age_group TEXT NOT NULL,
            role TEXT NOT NULL,
            first_selected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            access_count INTEGER DEFAULT 1
        )
    ''')
    
    # Create index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_session_id 
        ON player_selections(session_id)
    ''')
    
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# Player Selection Functions
# ---------------------------------------------------------

def get_players_and_coaches_list(data_dir: str = None) -> List[Dict]:
    """
    Load all players and coaches from the data files
    Returns a list of dicts with player/coach info
    """
    if data_dir is None:
        data_dir = os.path.join(BASE_DIR, "data")
    
    people = []
    
    # Load players
    players_file = os.path.join(data_dir, "players_summary.json")
    if os.path.exists(players_file):
        with open(players_file, 'r', encoding='utf-8') as f:
            players_data = json.load(f)
            for player in players_data.get("players", []):
                # Handle both single team and multiple teams
                teams = player.get("teams", [])
                if not teams:
                    team_name = player.get("team_name", "")
                    teams = [team_name] if team_name else []
                
                for team in teams:
                    # Extract club and age group from team name
                    # Format: "Club Name U16" or just "Club Name"
                    parts = team.rsplit(' ', 1)
                    if len(parts) == 2 and parts[1].startswith('U'):
                        club_name = parts[0]
                        age_group = parts[1]
                    else:
                        club_name = team
                        age_group = ""
                    
                    people.append({
                        "name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                        "first_name": player.get('first_name', ''),
                        "last_name": player.get('last_name', ''),
                        "club": club_name,
                        "age_group": age_group,
                        "role": "Player",
                        "jersey": player.get('jersey', ''),
                        "player_id": f"player_{player.get('first_name', '')}_{player.get('last_name', '')}".lower().replace(' ', '_')
                    })
    
    # Load coaches/staff
    staff_file = os.path.join(data_dir, "staff_summary.json")
    if os.path.exists(staff_file):
        with open(staff_file, 'r', encoding='utf-8') as f:
            staff_data = json.load(f)
            for staff in staff_data.get("staff", []):
                # Handle both single team and multiple teams
                teams = staff.get("teams", [])
                if not teams:
                    team_name = staff.get("team_name", "")
                    teams = [team_name] if team_name else []
                
                roles = staff.get("roles", [])
                role = roles[0] if roles else staff.get("role", "Coach")
                
                for team in teams:
                    # Extract club and age group from team name
                    parts = team.rsplit(' ', 1)
                    if len(parts) == 2 and parts[1].startswith('U'):
                        club_name = parts[0]
                        age_group = parts[1]
                    else:
                        club_name = team
                        age_group = ""
                    
                    people.append({
                        "name": f"{staff.get('first_name', '')} {staff.get('last_name', '')}".strip(),
                        "first_name": staff.get('first_name', ''),
                        "last_name": staff.get('last_name', ''),
                        "club": club_name,
                        "age_group": age_group,
                        "role": role,
                        "jersey": "",
                        "player_id": f"staff_{staff.get('first_name', '')}_{staff.get('last_name', '')}".lower().replace(' ', '_')
                    })
    
    # Sort by name
    people.sort(key=lambda x: x["name"])
    
    return people

def format_player_display(person: Dict) -> str:
    """
    Format player/coach display for dropdown
    Format: "Name from Club (Age Group) - Role"
    Example: "John Smith from Heidelberg United FC (U16) - Player"
    """
    name = person["name"]
    club = person["club"]
    age_group = person.get("age_group", "")
    role = person.get("role", "Player")
    
    # Build display string
    display = f"{name} from {club}"
    if age_group:
        display += f" ({age_group})"
    if role != "Player":
        display += f" - {role}"
    
    return display

def save_player_selection(session_id: str, person: Dict) -> bool:
    """
    Save or update player selection in database
    Returns True if successful
    """
    try:
        conn = sqlite3.connect(PLAYER_SELECTIONS_DB)
        cursor = conn.cursor()
        
        # Check if session already exists
        cursor.execute(
            'SELECT id, access_count FROM player_selections WHERE session_id = ?',
            (session_id,)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            cursor.execute('''
                UPDATE player_selections 
                SET player_name = ?, player_id = ?, club_name = ?, 
                    age_group = ?, role = ?, last_accessed = ?, access_count = ?
                WHERE session_id = ?
            ''', (
                person["name"],
                person["player_id"],
                person["club"],
                person.get("age_group", ""),
                person["role"],
                datetime.now(),
                existing[1] + 1,
                session_id
            ))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO player_selections 
                (session_id, player_name, player_id, club_name, age_group, role)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                person["name"],
                person["player_id"],
                person["club"],
                person.get("age_group", ""),
                person["role"]
            ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving player selection: {e}")
        return False

def get_player_selection(session_id: str) -> Optional[Dict]:
    """
    Get saved player selection for a session
    Returns player info dict or None
    """
    try:
        conn = sqlite3.connect(PLAYER_SELECTIONS_DB)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT player_name, player_id, club_name, age_group, role, 
                   first_selected, last_accessed, access_count
            FROM player_selections 
            WHERE session_id = ?
        ''', (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "name": row[0],
                "player_id": row[1],
                "club": row[2],
                "age_group": row[3],
                "role": row[4],
                "first_selected": row[5],
                "last_accessed": row[6],
                "access_count": row[7]
            }
        return None
    except Exception as e:
        print(f"Error getting player selection: {e}")
        return None

def clear_player_selection(session_id: str) -> bool:
    """Clear saved player selection for a session"""
    try:
        conn = sqlite3.connect(PLAYER_SELECTIONS_DB)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM player_selections WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing player selection: {e}")
        return False

# ---------------------------------------------------------
# Admin Authentication Functions
# ---------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_admin_credentials() -> Dict:
    """
    Get admin credentials from Streamlit secrets or environment variables
    Priority: Streamlit Secrets > Environment Variables > Defaults (local dev only)
    """
    admins = {}
    
    # Try Streamlit secrets first (for deployed apps)
    if HAS_STREAMLIT:
        try:
            # Check if admin section exists in secrets
            if "admin" in st.secrets:
                admin_secrets = st.secrets["admin"]
                
                # Support multiple admin users in secrets
                # Format in secrets.toml:
                # [admin]
                # username = "admin"
                # password = "your_secure_password"
                # full_name = "Administrator"
                # 
                # OR for multiple admins:
                # [admin.user1]
                # username = "admin"
                # password = "password1"
                # full_name = "Admin One"
                # [admin.user2]
                # username = "coach_admin"
                # password = "password2"
                # full_name = "Coach Admin"
                
                if "username" in admin_secrets:
                    # Single admin format
                    username = admin_secrets["username"]
                    password = admin_secrets["password"]
                    full_name = admin_secrets.get("full_name", username)
                    
                    admins[username] = {
                        "password_hash": hash_password(password),
                        "full_name": full_name
                    }
                else:
                    # Multiple admins format
                    for key in admin_secrets.keys():
                        if isinstance(admin_secrets[key], dict):
                            admin_data = admin_secrets[key]
                            username = admin_data.get("username", key)
                            password = admin_data.get("password", "")
                            full_name = admin_data.get("full_name", username)
                            
                            if password:
                                admins[username] = {
                                    "password_hash": hash_password(password),
                                    "full_name": full_name
                                }
                
                if admins:
                    return admins
        except (KeyError, FileNotFoundError, AttributeError):
            pass
    
    # Try environment variables
    # Format: ADMIN_USERNAME_<name>=username, ADMIN_PASSWORD_<name>=password
    admin_env_vars = {}
    for key in os.environ.keys():
        if key.startswith("ADMIN_USERNAME_"):
            name = key.replace("ADMIN_USERNAME_", "")
            username = os.environ[key]
            password = os.environ.get(f"ADMIN_PASSWORD_{name}", "")
            full_name = os.environ.get(f"ADMIN_FULLNAME_{name}", username)
            
            if password:
                admin_env_vars[username] = {
                    "password_hash": hash_password(password),
                    "full_name": full_name
                }
    
    if admin_env_vars:
        return admin_env_vars
    
    # Default credentials for local development ONLY
    # These should NEVER be used in production
    print("⚠️  WARNING: Using default admin credentials. Set admin credentials in Streamlit secrets!")
    return {
        "admin": {
            "password_hash": hash_password("admin123"),
            "full_name": "Administrator (DEFAULT - CHANGE ME!)"
        }
    }

def verify_admin(username: str, password: str) -> Optional[Dict]:
    """
    Verify admin credentials from Streamlit secrets or environment variables
    Returns admin info if successful, None otherwise
    """
    admins = get_admin_credentials()
    
    if username in admins:
        admin_data = admins[username]
        if hash_password(password) == admin_data["password_hash"]:
            return {
                "username": username,
                "full_name": admin_data.get("full_name", username),
                "role": "admin"
            }
    
    return None

def list_admin_users() -> List[str]:
    """Get list of admin usernames (for display purposes)"""
    admins = get_admin_credentials()
    return list(admins.keys())

# ---------------------------------------------------------
# Statistics Functions
# ---------------------------------------------------------

def get_player_selection_stats() -> Dict:
    """Get statistics about player selections"""
    try:
        conn = sqlite3.connect(PLAYER_SELECTIONS_DB)
        cursor = conn.cursor()
        
        # Total unique players
        cursor.execute('SELECT COUNT(DISTINCT session_id) FROM player_selections')
        total_users = cursor.fetchone()[0]
        
        # Most popular clubs
        cursor.execute('''
            SELECT club_name, COUNT(*) as count 
            FROM player_selections 
            GROUP BY club_name 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        popular_clubs = cursor.fetchall()
        
        # Most popular age groups
        cursor.execute('''
            SELECT age_group, COUNT(*) as count 
            FROM player_selections 
            WHERE age_group != '' 
            GROUP BY age_group 
            ORDER BY count DESC
        ''')
        popular_age_groups = cursor.fetchall()
        
        # Recent selections (last 24 hours)
        cursor.execute('''
            SELECT COUNT(*) 
            FROM player_selections 
            WHERE last_accessed > datetime('now', '-1 day')
        ''')
        recent_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_users": total_users,
            "popular_clubs": popular_clubs,
            "popular_age_groups": popular_age_groups,
            "recent_users": recent_count
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {
            "total_users": 0,
            "popular_clubs": [],
            "popular_age_groups": [],
            "recent_users": 0
        }

# ---------------------------------------------------------
# Initialize on import
# ---------------------------------------------------------
init_player_selections_db()
