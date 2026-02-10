# config.py - SECURE User Authentication and Settings Configuration
# ================================================
# This version uses Streamlit secrets or environment variables
# Safe for public GitHub repositories
# ================================================

import hashlib
import json
import os
import sys

# ---------------------------------------------------------
# Try to import Streamlit (only available when app is running)
# ---------------------------------------------------------
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def get_secret_password(username: str) -> str:
    """
    Get password from secrets (Streamlit Cloud or local .streamlit/secrets.toml)
    Falls back to environment variables if Streamlit not available
    """
    # Try Streamlit secrets first (for deployed apps)
    if HAS_STREAMLIT:
        try:
            return st.secrets["passwords"][username]
        except (KeyError, FileNotFoundError):
            pass
    
    # Try environment variables
    env_var = f"DRIBL_PASSWORD_{username.upper()}"
    if env_var in os.environ:
        return os.environ[env_var]
    
    # Default passwords (ONLY for initial setup - will be changed)
    defaults = {
        "admin": "admin123",
        "coach": "coach123",
        "parent": "parent123"
    }
    
    return defaults.get(username, "changeme123")

def get_setting(key: str, default):
    """Get setting from secrets or environment variables"""
    if HAS_STREAMLIT:
        try:
            return st.secrets["settings"][key]
        except (KeyError, FileNotFoundError):
            pass
    
    env_var = f"DRIBL_{key.upper()}"
    if env_var in os.environ:
        value = os.environ[env_var]
        # Convert string to appropriate type
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes')
        elif isinstance(default, int):
            return int(value)
        return value
    
    return default

# ---------------------------------------------------------
# User Authentication Settings
# ---------------------------------------------------------

# Path to users configuration file (stored locally, NOT in Git)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_CONFIG_PATH = os.path.join(BASE_DIR, "users_config.json")

# ---------------------------------------------------------
# Build default users from secrets/env vars
# ---------------------------------------------------------

def build_default_users():
    """Build default users using passwords from secrets/env vars"""
    return {
        "admin": {
            "password_hash": hash_password(get_secret_password("admin")),
            "role": "admin",
            "full_name": "Administrator"
        },
        "coach": {
            "password_hash": hash_password(get_secret_password("coach")),
            "role": "user",
            "full_name": "Coach"
        },
        "parent": {
            "password_hash": hash_password(get_secret_password("parent")),
            "role": "user",
            "full_name": "Parent"
        }
    }

# ---------------------------------------------------------
# User Management Functions
# ---------------------------------------------------------

def load_users():
    """Load users from config file or build from secrets"""
    if os.path.exists(USERS_CONFIG_PATH):
        try:
            with open(USERS_CONFIG_PATH, 'r') as f:
                return json.load(f)
        except:
            pass
    
    # If no config file, build from secrets
    return build_default_users()

def save_users(users):
    """Save users to config file"""
    with open(USERS_CONFIG_PATH, 'w') as f:
        json.dump(users, f, indent=2)

def hash_password(password: str) -> str:
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == password_hash

def authenticate_user(username: str, password: str) -> dict:
    """
    Authenticate a user
    Returns user info if successful, None otherwise
    """
    users = load_users()
    
    if username in users:
        user_data = users[username]
        if verify_password(password, user_data['password_hash']):
            return {
                'username': username,
                'role': user_data.get('role', 'user'),
                'full_name': user_data.get('full_name', username)
            }
    
    return None

def add_user(username: str, password: str, role: str = "user", full_name: str = ""):
    """Add a new user (CLI only - not available in web UI)"""
    users = load_users()
    
    if username in users:
        return False, "Username already exists"
    
    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "full_name": full_name or username
    }
    
    save_users(users)
    return True, "User added successfully"

def remove_user(username: str):
    """Remove a user (CLI only)"""
    users = load_users()
    
    if username not in users:
        return False, "User not found"
    
    if username == "admin":
        return False, "Cannot remove admin user"
    
    del users[username]
    save_users(users)
    return True, "User removed successfully"

def change_password(username: str, old_password: str, new_password: str):
    """Change user password (CLI only)"""
    users = load_users()
    
    if username not in users:
        return False, "User not found"
    
    if not verify_password(old_password, users[username]['password_hash']):
        return False, "Incorrect old password"
    
    users[username]['password_hash'] = hash_password(new_password)
    save_users(users)
    return True, "Password changed successfully"

def reset_password(username: str, new_password: str, admin_username: str):
    """Admin function to reset user password (CLI only)"""
    users = load_users()
    
    # Verify admin role
    if admin_username not in users or users[admin_username].get('role') != 'admin':
        return False, "Admin privileges required"
    
    if username not in users:
        return False, "User not found"
    
    users[username]['password_hash'] = hash_password(new_password)
    save_users(users)
    return True, f"Password reset for {username}"

# ---------------------------------------------------------
# Activity Tracking Settings (from secrets/env vars)
# ---------------------------------------------------------

# Database path for activity logs
ACTIVITY_DB_PATH = os.path.join(BASE_DIR, "activity_logs.db")

# Settings with fallbacks
ENABLE_ACTIVITY_TRACKING = get_setting("enable_activity_tracking", True)
LOG_RETENTION_DAYS = get_setting("log_retention_days", 90)
SESSION_TIMEOUT_MINUTES = get_setting("session_timeout", 60)
ENABLE_GUEST_ACCESS = get_setting("enable_guest_access", False)
GUEST_USERNAME = "guest"

# ---------------------------------------------------------
# Initialize default users file if it doesn't exist
# ---------------------------------------------------------

def initialize_config():
    """Initialize configuration files if they don't exist"""
    if not os.path.exists(USERS_CONFIG_PATH):
        users = build_default_users()
        save_users(users)
        print(f"✅ Created users configuration at: {USERS_CONFIG_PATH}")
        print("\n⚠️  SECURITY NOTICE:")
        print("   Default passwords are loaded from:")
        print("   1. Streamlit secrets (.streamlit/secrets.toml)")
        print("   2. Environment variables (DRIBL_PASSWORD_ADMIN, etc.)")
        print("   3. Hardcoded defaults (admin123, coach123, parent123)")
        print("\n   For production, set passwords in Streamlit Cloud secrets!")
        print("   Or use: python manage_users.py to change passwords locally")
    else:
        print(f"✅ Users configuration exists: {USERS_CONFIG_PATH}")

# ---------------------------------------------------------
# Print security status
# ---------------------------------------------------------

def print_security_status():
    """Print current security configuration status"""
    print("\n" + "="*60)
    print("🔐 SECURITY CONFIGURATION STATUS")
    print("="*60)
    
    if HAS_STREAMLIT:
        try:
            st.secrets["passwords"]["admin"]
            print("✅ Streamlit secrets detected")
        except:
            print("⚠️  No Streamlit secrets found")
    else:
        print("ℹ️  Streamlit not available (CLI mode)")
    
    # Check environment variables
    env_vars = [k for k in os.environ.keys() if k.startswith("DRIBL_PASSWORD_")]
    if env_vars:
        print(f"✅ Environment variables set: {len(env_vars)} passwords")
    else:
        print("⚠️  No environment variables set")
    
    # Check users config file
    if os.path.exists(USERS_CONFIG_PATH):
        users = load_users()
        print(f"✅ Users config file exists: {len(users)} users")
    else:
        print("⚠️  No users config file (will use defaults)")
    
    print("\n📝 RECOMMENDATIONS:")
    if not HAS_STREAMLIT and not env_vars and not os.path.exists(USERS_CONFIG_PATH):
        print("   1. For Streamlit Cloud: Set passwords in app secrets")
        print("   2. For local dev: Copy secrets_template.toml to .streamlit/secrets.toml")
        print("   3. For CLI: Run 'python manage_users.py' to set passwords")
    else:
        print("   ✅ Configuration looks good!")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    # Initialize config when run directly
    initialize_config()
    print_security_status()
