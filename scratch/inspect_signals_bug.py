import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import pytz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from detection.datastore import MangoDataStore
datastore = MangoDataStore()

def inspect():
    with datastore.get_connection() as conn:
        rows = datastore._fetch_query(conn, "SELECT id, created_at, status FROM signals ORDER BY id DESC LIMIT 5")
        if not rows:
            print("No signals found in the database.")
            return
            
        for r in rows:
            created_at = r['created_at']
            print(f"ID: {r['id']} | type(created_at): {type(created_at)} | Value: {created_at} | Status: {r['status']}")
            
            # Test the parsing logic from analyze_signals.py
            try:
                if isinstance(created_at, str):
                    sig_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    # If it's already a datetime, this is what should happen
                    print("  Info: created_at is already a datetime object!")
                    sig_time = created_at
                print(f"  Parsed successfully: {sig_time}")
            except Exception as e:
                print(f"  Error parsing: {e}")

if __name__ == "__main__":
    inspect()
