# config.py - User Authentication and Settings Configuration

import hashlib
import json
import os

# ---------------------------------------------------------
# User Authentication Settings
# ---------------------------------------------------------

# Default admin credentials (CHANGE THESE!)
DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "full_name": "Administrator"
    },
    "coach": {
        "password_hash": hashlib.sha256("coach123".encode()).hexdigest(),
        "role": "user",
        "full_name": "Coach"
    },
    "parent": {
        "password_hash": hashlib.sha256("parent123".encode()).hexdigest(),
        "role": "user",
        "full_name": "Parent"
    }
}

# Path to users configuration file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_CONFIG_PATH = os.path.join(BASE_DIR, "users_config.json")

# ---------------------------------------------------------
# User Management Functions
# ---------------------------------------------------------

def load_users():
    """Load users from config file or return defaults"""
    if os.path.exists(USERS_CONFIG_PATH):
        try:
            with open(USERS_CONFIG_PATH, 'r') as f:
                return json.load(f)
        except:
            return DEFAULT_USERS
    return DEFAULT_USERS

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
    """Add a new user"""
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
    """Remove a user"""
    users = load_users()
    
    if username not in users:
        return False, "User not found"
    
    if username == "admin":
        return False, "Cannot remove admin user"
    
    del users[username]
    save_users(users)
    return True, "User removed successfully"

def change_password(username: str, old_password: str, new_password: str):
    """Change user password"""
    users = load_users()
    
    if username not in users:
        return False, "User not found"
    
    if not verify_password(old_password, users[username]['password_hash']):
        return False, "Incorrect old password"
    
    users[username]['password_hash'] = hash_password(new_password)
    save_users(users)
    return True, "Password changed successfully"

def reset_password(username: str, new_password: str, admin_username: str):
    """Admin function to reset user password"""
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
# Activity Tracking Settings
# ---------------------------------------------------------

# Database path for activity logs
ACTIVITY_DB_PATH = os.path.join(BASE_DIR, "activity_logs.db")

# Enable/disable activity tracking
ENABLE_ACTIVITY_TRACKING = True

# Retention period for logs (in days)
LOG_RETENTION_DAYS = 90

# ---------------------------------------------------------
# App Settings
# ---------------------------------------------------------

# Session timeout (in minutes)
SESSION_TIMEOUT_MINUTES = 60

# Enable guest access (view-only without login)
ENABLE_GUEST_ACCESS = False

# Guest username for tracking
GUEST_USERNAME = "guest"

# ---------------------------------------------------------
# Initialize default users file if it doesn't exist
# ---------------------------------------------------------

def initialize_config():
    """Initialize configuration files if they don't exist"""
    if not os.path.exists(USERS_CONFIG_PATH):
        save_users(DEFAULT_USERS)
        print(f"✅ Created default users configuration at: {USERS_CONFIG_PATH}")
        print("\n⚠️  DEFAULT CREDENTIALS (CHANGE THESE!):")
        print("   Admin: admin / admin123")
        print("   Coach: coach / coach123")
        print("   Parent: parent / parent123")

if __name__ == "__main__":
    # Initialize config when run directly
    initialize_config()
