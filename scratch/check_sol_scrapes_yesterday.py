from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    
    print("SOL scrapes on June 1st, 2026:")
    cursor.execute("""
        SELECT timestamp, close, timeframe
        FROM scrapes
        WHERE name = 'SOL'
        AND timestamp BETWEEN '2026-06-01T12:00:00' AND '2026-06-02T04:00:00'
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(f"  Time (UTC): {r[0]} | Price: {r[1]} | TF: {r[2]}")
