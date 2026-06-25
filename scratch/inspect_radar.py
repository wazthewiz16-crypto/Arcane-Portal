import sys
import os
from dotenv import load_dotenv

# Load env variables
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore

datastore = MangoDataStore()

print("DATABASE_URL:", os.getenv("DATABASE_URL"))

with datastore.get_connection() as conn:
    cursor = conn.cursor()
    
    # 1. Total signals
    cursor.execute("SELECT COUNT(*) FROM signals")
    total_signals = cursor.fetchone()[0]
    print(f"Total signals in database: {total_signals}")
    
    # 2. Count by status
    cursor.execute("SELECT status, COUNT(*) FROM signals GROUP BY status")
    statuses = cursor.fetchall()
    print("Signals by status:")
    for status, count in statuses:
        print(f"  {status}: {count}")
        
    # 3. Active signals list
    cursor.execute("SELECT id, asset_name, signal_type, entry_price, entry_time, status FROM signals WHERE status = 'ACTIVE' ORDER BY entry_time DESC")
    active_rows = cursor.fetchall()
    print(f"\nActive signals in DB (direct query): {len(active_rows)}")
    for r in active_rows:
        print(f"  ID: {r[0]} | Asset: {r[1]} | Type: {r[2]} | Entry Price: {r[3]} | Time: {r[4]}")

# 4. Through API
active_signals = datastore.get_active_signals()
print(f"\nActive signals via datastore.get_active_signals(): {len(active_signals)}")

# 5. Check if they have prices
latest_scrapes = datastore.get_latest_for_all_assets()
print(f"\nLatest scrapes: {len(latest_scrapes)}")
current_prices = {}
for scrape in latest_scrapes:
    current_prices[scrape['name'].strip().upper()] = float(scrape['close'])
print("Current prices sample (first 5):")
for k, v in list(current_prices.items())[:5]:
    print(f"  {k}: {v}")
