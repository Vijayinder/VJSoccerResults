#!/usr/bin/env python3
"""
User Management Tool for Dribl Football Intelligence
"""

import sys
from config import (
    add_user, remove_user, change_password, reset_password,
    load_users, initialize_config
)

def print_menu():
    """Print main menu"""
    print("\n" + "="*60)
    print("🔐 Dribl User Management Tool")
    print("="*60)
    print("\n1. List all users")
    print("2. Add new user")
    print("3. Remove user")
    print("4. Reset user password (admin)")
    print("5. Initialize default users")
    print("6. Exit")
    print("\n" + "-"*60)

def list_users():
    """List all users"""
    users = load_users()
    
    print("\n" + "="*60)
    print("👥 Current Users")
    print("="*60)
    print(f"\n{'Username':<15} {'Full Name':<25} {'Role':<10}")
    print("-"*60)
    
    for username, data in users.items():
        full_name = data.get('full_name', username)
        role = data.get('role', 'user')
        role_icon = "🛡️" if role == "admin" else "👤"
        print(f"{username:<15} {full_name:<25} {role_icon} {role:<10}")
    
    print("\nTotal users: " + str(len(users)))

def add_user_interactive():
    """Add user interactively"""
    print("\n" + "="*60)
    print("➕ Add New User")
    print("="*60)
    
    username = input("\nEnter username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return
    
    password = input("Enter password: ").strip()
    if not password:
        print("❌ Password cannot be empty")
        return
    
    full_name = input("Enter full name (optional): ").strip()
    
    role = input("Enter role (user/admin) [user]: ").strip().lower()
    if role not in ['user', 'admin']:
        role = 'user'
    
    success, message = add_user(username, password, role, full_name)
    
    if success:
        print(f"\n✅ {message}")
        print(f"\nUser '{username}' created successfully!")
        print(f"  Full Name: {full_name or username}")
        print(f"  Role: {role}")
    else:
        print(f"\n❌ {message}")

def remove_user_interactive():
    """Remove user interactively"""
    print("\n" + "="*60)
    print("➖ Remove User")
    print("="*60)
    
    list_users()
    
    username = input("\nEnter username to remove: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return
    
    confirm = input(f"Are you sure you want to remove '{username}'? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return
    
    success, message = remove_user(username)
    
    if success:
        print(f"\n✅ {message}")
    else:
        print(f"\n❌ {message}")

def reset_password_interactive():
    """Reset password interactively (admin only)"""
    print("\n" + "="*60)
    print("🔑 Reset User Password (Admin)")
    print("="*60)
    
    list_users()
    
    admin_username = input("\nEnter admin username: ").strip()
    if not admin_username:
        print("❌ Admin username cannot be empty")
        return
    
    target_username = input("Enter username to reset password for: ").strip()
    if not target_username:
        print("❌ Target username cannot be empty")
        return
    
    new_password = input("Enter new password: ").strip()
    if not new_password:
        print("❌ Password cannot be empty")
        return
    
    success, message = reset_password(target_username, new_password, admin_username)
    
    if success:
        print(f"\n✅ {message}")
    else:
        print(f"\n❌ {message}")

def init_users_interactive():
    """Initialize default users"""
    print("\n" + "="*60)
    print("🔄 Initialize Default Users")
    print("="*60)
    
    print("\nThis will create/overwrite the following default users:")
    print("  - admin (password: admin123)")
    print("  - coach (password: coach123)")
    print("  - parent (password: parent123)")
    
    confirm = input("\nProceed? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return
    
    initialize_config()
    print("\n✅ Default users initialized successfully!")

def main():
    """Main function"""
    while True:
        print_menu()
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '1':
            list_users()
        elif choice == '2':
            add_user_interactive()
        elif choice == '3':
            remove_user_interactive()
        elif choice == '4':
            reset_password_interactive()
        elif choice == '5':
            init_users_interactive()
        elif choice == '6':
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
