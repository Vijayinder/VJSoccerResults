import subprocess
import datetime
import os

def auto_update():
    # Change to your repo directory
    os.chdir(r"c:\dribl_python\dribl_agent")
    
    # Update app.py with timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open("app.py", "a", encoding="utf-8") as f:
        f.write(f"\n# Auto-updated: {timestamp}\n")
    
    # Git commands
    subprocess.run(["git", "add", "."])
    
    commit_msg = f"Auto update: {datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    subprocess.run(["git", "commit", "-m", commit_msg])
    subprocess.run(["git", "push", "origin", "main"])
    
    print(f"✅ Updated at {timestamp}")

if __name__ == "__main__":
    auto_update()