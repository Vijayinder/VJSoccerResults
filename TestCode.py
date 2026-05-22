import sqlite3
import json
from fast_agent import get_lineup_by_id

def run_test():
    print("🔍 Testing connection to soccer_data.db...")
    conn = sqlite3.connect("soccer_data.db")
    cur = conn.cursor()
    
    # 1. Grab a valid match_hash_id that actually exists in your new table
    sample_row = cur.execute("SELECT match_hash_id FROM lineups LIMIT 1").fetchone()
    conn.close()
    
    if not sample_row:
        print("❌ Error: The lineups table appears to be empty!")
        return
        
    target_match_id = sample_row[0]
    print(f"🎯 Found sample match_hash_id to test: {target_match_id}")
    print("-" * 50)
    
    # 2. Call your updated fast_agent function
    print("🏃‍♂️ Executing get_lineup_by_id()...")
    result = get_lineup_by_id(target_match_id)
    
    if result is None:
        print("❌ Error: get_lineup_by_id returned None!")
        return
        
    # 3. Validate the payload structure
    print("✅ Success! Data retrieved.")
    print(f"Match ID: {result.get('match_hash_id')}")
    
    home_count = len(result.get("home_lineup", {}).get("data", []))
    away_count = len(result.get("away_lineup", {}).get("data", []))
    print(f"🏠 Home Players Found: {home_count}")
    print(f"🚌 Away Players Found: {away_count}")
    
    # 4. Print a sample player to confirm nested structures (cards/goals) decoded nicely
    if home_count > 0:
        sample_player = result["home_lineup"]["data"][0]
        print("-" * 50)
        print("👤 Sample Player Object Structure:")
        print(json.dumps(sample_player, indent=2))

if __name__ == "__main__":
    run_test()