from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check last 10 signals
    print("Last 10 signals:")
    cursor.execute("""
        SELECT id, asset_name, signal_type, entry_time, status, alerted_discord, created_at, updated_at
        FROM signals
        ORDER BY id DESC
        LIMIT 10
    """)
    for r in cursor.fetchall():
        print(f"  ID: {r[0]} | Asset: {r[1]} | Type: {r[2]} | Time: {r[3]} | Status: {r[4]} | DiscordAlert: {r[5]} | Created: {r[6]} | Updated: {r[7]}")
        
    # Check if there are other tables like logs or system_settings
    print("\nSystem settings related to timing/retries:")
    cursor.execute("SELECT key, value, updated_at FROM system_settings")
    for r in cursor.fetchall():
        if 'LAST' in r[0] or 'TIME' in r[0] or 'ACTIVE' in r[0]:
            print(f"  {r[0]}: {r[1]} | Updated: {r[2]}")
