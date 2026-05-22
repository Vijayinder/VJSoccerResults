import sqlite3, json, os

DB = r"C:\dribl_python\dribl_agent\data\soccer_data.db"
conn = sqlite3.connect(DB)

print(f"DB file size: {os.path.getsize(DB)/(1024*1024):.1f} MB\n")

print("=== ALL COLUMN SIZES ===")
for table, col in [
    ("players","profile_json"), ("players","matches_json"),
    ("staff","profile_json"),   ("staff","matches_json"),
    ("results","raw_json"),     ("fixtures","raw_json"),
    ("match_centre","raw_json"),("lineups","raw_json"),
    ("kv_store","value"),
]:
    r = conn.execute(f"SELECT COUNT(*), SUM(LENGTH({col})) FROM {table}").fetchone()
    mb = (r[1] or 0) / (1024*1024)
    print(f"  {table}.{col}: {r[0]} rows = {mb:.1f} MB")

print("\n=== FIXTURE DATE RANGE ===")
r = conn.execute("SELECT MIN(date_aest), MAX(date_aest), COUNT(*) FROM fixtures").fetchone()
print(f"  {r[2]} fixtures from {r[0]} to {r[1]}")

print("\n=== LINEUP CHECK ===")
row = conn.execute("SELECT raw_json FROM lineups LIMIT 1").fetchone()
if row:
    d = json.loads(row[0])
    hl = d.get("home_lineup", [])
    if isinstance(hl, list) and hl:
        print(f"  Player has {len(hl[0].keys())} fields: {sorted(hl[0].keys())}")
    elif isinstance(hl, dict):
        print(f"  ❌ Still a dict — slim_lineup bug not fixed")

print("\n=== MATCH_CENTRE CHECK ===")
row = conn.execute("SELECT raw_json FROM match_centre LIMIT 1").fetchone()
if row:
    d = json.loads(row[0])
    attrs = d.get("matchcentre",{}).get("data",{}).get("attributes",{})
    print(f"  {len(attrs)} attributes: {sorted(attrs.keys())}")

conn.close()