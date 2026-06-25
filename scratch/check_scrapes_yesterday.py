from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    
    # 6 PM EST yesterday = 22:00 UTC yesterday (June 1st)
    print("Checking scrapes between 21:50 UTC and 23:10 UTC on June 1st:")
    cursor.execute("""
        SELECT timeframe, COUNT(*), MIN(timestamp), MAX(timestamp)
        FROM scrapes
        WHERE timestamp BETWEEN '2026-06-01T21:50:00' AND '2026-06-01T23:10:00'
        GROUP BY timeframe
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(f"  Timeframe: {r[0]} | Count: {r[1]} | Min: {r[2]} | Max: {r[3]}")
