#!/usr/bin/env python3
"""
Admin Management Guide
======================
Admin credentials are managed through Streamlit Secrets, not local files.

For Streamlit Cloud:
--------------------
1. Go to your app at https://share.streamlit.io
2. Click on the app settings (gear icon)
3. Go to "Secrets" section
4. Add your admin credentials:

[admin]
username = "admin"
password = "your_secure_password_here"
full_name = "Administrator"

For multiple admins:
[admin.user1]
username = "admin"
password = "password1"
full_name = "Admin One"

[admin.user2]
username = "coach_admin"
password = "password2"
full_name = "Coach Admin"


For Local Development:
-----------------------
Create .streamlit/secrets.toml in your project directory:

mkdir -p .streamlit
cat > .streamlit/secrets.toml << 'EOF'
[admin]
username = "admin"
password = "admin123"
full_name = "Local Admin"
EOF

IMPORTANT: Add .streamlit/secrets.toml to .gitignore!
echo ".streamlit/secrets.toml" >> .gitignore


For Environment Variables (Alternative):
-----------------------------------------
Set these environment variables:

export ADMIN_USERNAME_1="admin"
export ADMIN_PASSWORD_1="your_password"
export ADMIN_FULLNAME_1="Administrator"

# For multiple admins:
export ADMIN_USERNAME_2="coach_admin"
export ADMIN_PASSWORD_2="coach_password"
export ADMIN_FULLNAME_2="Coach Admin"


Testing Admin Login:
--------------------
Run this script to test your admin credentials:
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_admin_login():
    """Test admin login with current configuration"""
    try:
        from player_config import verify_admin, get_admin_credentials
        
        print("\n" + "="*60)
        print("ADMIN CREDENTIALS TEST")
        print("="*60)
        
        # Get all configured admins
        admins = get_admin_credentials()
        
        print(f"\n✅ Found {len(admins)} admin user(s):")
        for username in admins.keys():
            full_name = admins[username].get('full_name', username)
            print(f"   • {username} ({full_name})")
        
        # Test login
        print("\n" + "-"*60)
        print("TEST LOGIN")
        print("-"*60)
        
        if not admins:
            print("❌ No admin users configured!")
            print("\nPlease set up admin credentials in Streamlit secrets or environment variables.")
            return
        
        # Test first admin
        first_admin = list(admins.keys())[0]
        print(f"\nTo test login, enter password for '{first_admin}':")
        print("(or press Ctrl+C to skip)")
        
        try:
            import getpass
            password = getpass.getpass("Password: ")
            
            result = verify_admin(first_admin, password)
            
            if result:
                print(f"\n✅ SUCCESS! Logged in as: {result['full_name']}")
                print(f"   Username: {result['username']}")
                print(f"   Role: {result['role']}")
            else:
                print("\n❌ FAILED! Invalid password")
        except KeyboardInterrupt:
            print("\n\nTest skipped.")
        
        print("\n" + "="*60)
        print("CONFIGURATION SOURCE")
        print("="*60)
        
        # Check where credentials are coming from
        try:
            import streamlit as st
            if "admin" in st.secrets:
                print("\n✅ Using Streamlit Secrets")
                print("   Location: .streamlit/secrets.toml or Streamlit Cloud")
        except:
            print("\n⚠️  Streamlit secrets not available")
        
        # Check environment variables
        env_admins = [k for k in os.environ.keys() if k.startswith("ADMIN_USERNAME_")]
        if env_admins:
            print(f"\n✅ Using Environment Variables")
            print(f"   Found {len(env_admins)} admin(s) in environment")
        
        if not env_admins:
            try:
                import streamlit as st
                if "admin" not in st.secrets:
                    print("\n⚠️  WARNING: Using default credentials!")
                    print("   This is ONLY for local development.")
                    print("   Please set admin credentials in production!")
            except:
                print("\n⚠️  WARNING: Using default credentials!")
                print("   Please set admin credentials in Streamlit secrets or environment variables!")
        
        print("\n" + "="*60)
        
    except ImportError as e:
        print(f"❌ Error importing player_config: {e}")
        print("\nMake sure player_config.py is in the same directory.")
    except Exception as e:
        print(f"❌ Error: {e}")

def show_setup_guide():
    """Show setup guide"""
    print(__doc__)
    print("\n" + "="*60)
    print("QUICK SETUP GUIDE")
    print("="*60)
    print("\nFor Streamlit Cloud:")
    print("  1. Go to your app settings")
    print("  2. Add admin credentials in Secrets section")
    print("  3. Deploy your app")
    print("\nFor Local Development:")
    print("  1. Create .streamlit/secrets.toml")
    print("  2. Add admin credentials (see format above)")
    print("  3. Add to .gitignore")
    print("  4. Run: streamlit run app_new.py")
    print("\n" + "="*60 + "\n")

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            test_admin_login()
        elif command == "help":
            show_setup_guide()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  test  - Test admin login")
            print("  help  - Show setup guide")
    else:
        # Default: show test
        test_admin_login()

if __name__ == "__main__":
    main()

