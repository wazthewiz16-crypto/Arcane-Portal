import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    print("--- Detailed Signal History since June 1st, 2026 ---")
    with datastore.get_connection() as conn:
        rows = datastore._fetch_query(conn, """
            SELECT id, asset_name, signal_type, entry_price, stop_loss, take_profit, status, created_at, updated_at
            FROM signals
            WHERE created_at >= '2026-06-01T00:00:00'
            ORDER BY created_at ASC
        """)
        for r in rows:
            print(f"ID: {r['id']}")
            print(f"  Asset: {r['asset_name']}")
            print(f"  Type: {r['signal_type']}")
            print(f"  Entry: {r['entry_price']}")
            print(f"  SL: {r['stop_loss']}")
            print(f"  TP: {r['take_profit']}")
            print(f"  Status: {r['status']}")
            print(f"  Created: {r['created_at']}")
            print(f"  Updated: {r['updated_at']}")
            print("-" * 40)

if __name__ == "__main__":
    main()
