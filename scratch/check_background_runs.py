from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check scrapes saved in the last 48 hours grouped by hour
    print("Scrapes saved per hour (UTC) over last 48 hours:")
    cursor.execute("""
        SELECT date_trunc('hour', timestamp::timestamp) as hr, COUNT(*), MIN(timestamp), MAX(timestamp)
        FROM scrapes
        WHERE timestamp::timestamp >= (NOW() - INTERVAL '48 hours')
        GROUP BY hr
        ORDER BY hr DESC
    """)
    for r in cursor.fetchall():
        print(f"  Hour: {r[0]} | Scrapes count: {r[1]} | Min: {r[2]} | Max: {r[3]}")
