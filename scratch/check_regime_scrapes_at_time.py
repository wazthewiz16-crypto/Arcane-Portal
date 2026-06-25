import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from detection.datastore import MangoDataStore
datastore = MangoDataStore()

def check_history():
    with datastore.get_connection() as conn:
        # Check scrapes from today (June 5) between 12:45 UTC and 13:15 UTC
        start_time = "2026-06-05T12:45:00"
        end_time = "2026-06-05T13:15:00"
        
        rows = datastore._fetch_query(conn, """
            SELECT name, timeframe, timestamp, close, entry_up, entry_down
            FROM scrapes
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start_time, end_time))
        
        print(f"Total scrapes between 12:45 UTC and 13:15 UTC: {len(rows)}")
        for r in rows[:30]:
            print(f"  Asset: {r['name']:<10} TF: {r['timeframe']:<5} TS: {r['timestamp']:<26} Close: {r['close']}")

if __name__ == "__main__":
    check_history()
