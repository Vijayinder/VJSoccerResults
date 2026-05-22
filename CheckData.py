# save as check_db.py and run it from your Current\ folder
import sqlite3, os

db = r"C:\dribl_python\dribl_agent\data\soccer_data.db"
print("Exists:", os.path.exists(db))

if os.path.exists(db):
    conn = sqlite3.connect(db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("Tables:", [t[0] for t in tables])
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"  {t[0]}: {count} rows")
    conn.close()
else:
    print("DB not found — need to run build_database.py first")