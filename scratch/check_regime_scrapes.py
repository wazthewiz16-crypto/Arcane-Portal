import os
import sys
import json
from datetime import datetime, timedelta

import os
import sys
from dotenv import load_dotenv

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from detection.datastore import MangoDataStore

datastore = MangoDataStore()

def check_scrapes():
    lookback_hours = 4
    with datastore.get_connection() as conn:
        # Check database time vs system time
        db_now = datastore._fetch_query(conn, "SELECT NOW() as now, timezone('UTC', NOW()) as utc_now, current_setting('TimeZone') as tz")[0]
        print(f"PostgreSQL NOW(): {db_now['now']}")
        print(f"PostgreSQL UTC NOW(): {db_now['utc_now']}")
        print(f"PostgreSQL Session TimeZone: {db_now['tz']}")
        print(f"Python datetime.utcnow(): {datetime.utcnow()}")
        
        # Run the regime query
        rows = datastore._fetch_query(conn, """
            SELECT DISTINCT ON (name, timeframe)
                name, timeframe, timestamp, close, entry_up, entry_down,
                TO_TIMESTAMP(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS') as parsed_ts
            FROM scrapes
            WHERE TO_TIMESTAMP(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS')
                  > NOW() - INTERVAL '%s hours'
              AND timeframe IN ('15m', '1h', '4h')
            ORDER BY name, timeframe, timestamp DESC
        """ % lookback_hours)
        
        print(f"\nFound {len(rows)} latest scrapes within last {lookback_hours} hours:")
        for r in rows[:15]:
            print(f"  Asset: {r['name']:<10} TF: {r['timeframe']:<5} TS in DB: {r['timestamp']:<26} Parsed TS: {r['parsed_ts']}")
            
        # Count distinct assets
        assets = set(r['name'] for r in rows)
        print(f"\nDistinct assets: {len(assets)} -> {assets}")

if __name__ == "__main__":
    check_scrapes()
