import sys
import os
from dotenv import load_dotenv

load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore

datastore = MangoDataStore()

with datastore.get_connection() as conn:
    cursor = conn.cursor()
    
    # 1. Check latest scrape overall
    cursor.execute("SELECT MAX(timestamp) FROM scrapes")
    max_timestamp = cursor.fetchone()[0]
    print(f"Latest scrape timestamp overall (UTC): {max_timestamp}")
    
    # 2. Latest scrapes by timeframe
    cursor.execute("""
        SELECT timeframe, COUNT(*), MAX(timestamp) 
        FROM scrapes 
        GROUP BY timeframe 
        ORDER BY MAX(timestamp) DESC
    """)
    rows = cursor.fetchall()
    print("\nLatest scrapes by timeframe:")
    for timeframe, count, max_time in rows:
        print(f"  Timeframe: {timeframe:>3} | Count: {count:>5} | Latest Time (UTC): {max_time}")
        
    # 3. Latest scrapes for a few assets
    cursor.execute("""
        SELECT name, timeframe, timestamp, close 
        FROM scrapes 
        ORDER BY timestamp DESC 
        LIMIT 10
    """)
    latest_rows = cursor.fetchall()
    print("\n10 Latest individual scrapes in DB:")
    for r in latest_rows:
        print(f"  Asset: {r[0]} | TF: {r[1]} | UTC Time: {r[2]} | Close: {r[3]}")
