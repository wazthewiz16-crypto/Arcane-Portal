import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    print("--- Scraping & Signals Gap Analysis (June 7 - June 14) ---")
    
    with datastore.get_connection() as conn:
        # Check if scrapes exist during this period
        scrape_count = datastore._fetch_query(conn, """
            SELECT timeframe, COUNT(*) as cnt, MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
            FROM scrapes
            WHERE timestamp >= '2026-06-07T00:00:00' AND timestamp <= '2026-06-14T23:59:59'
            GROUP BY timeframe
            ORDER BY cnt DESC
        """)
        
        print("\nScrapes Count by Timeframe in the gap week:")
        for sc in scrape_count:
            print(f"  TF: {sc['timeframe']} | Count: {sc['cnt']} | Range: {sc['min_ts']} to {sc['max_ts']}")
            
        # Check settings changes or daily decisions during this period
        settings_history = datastore._fetch_query(conn, """
            SELECT key, value, updated_at
            FROM system_settings
            WHERE key IN ('DAILY_REGIME_DECISION', 'MARKET_REGIME')
        """)
        print("\nCurrent settings:")
        for sh in settings_history:
            print(f"  {sh['key']}: {sh['value']} (Updated: {sh['updated_at']})")
            
        # Check if any signal candidates were benched or failed in `detect_signals_for_asset`
        # We can look at the overall signal count per day
        signals_by_day = datastore._fetch_query(conn, """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM signals
            WHERE created_at >= '2026-06-01T00:00:00'
            GROUP BY DATE(created_at)
            ORDER BY day
        """)
        print("\nSignals generated per day since June 1st:")
        for s in signals_by_day:
            print(f"  Day: {s['day']} | Signals: {s['cnt']}")

if __name__ == "__main__":
    main()
