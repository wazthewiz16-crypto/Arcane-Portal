"""
Check cached Mango Dashboard flags in SQLite for core assets
"""
import sys
import os
import json
from pathlib import Path

# Add project root working directory to path
sys.path.insert(0, os.getcwd())

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    
    db_data = datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
    if not db_data:
        print("No cached data found in the database settings.")
        return
        
    try:
        data = json.loads(db_data)
        updated_at = data.get("updated_at", "N/A")
        print(f"Cache Updated At: {updated_at}")
        
        assets = data.get("assets", {})
        
        CORE_ASSETS = ["BTC", "ETH", "SOL", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR", "SPY", "QQQ"]
        
        print("\n--- Core Asset Flags Breakdowns ---")
        for sym in CORE_ASSETS:
            details = assets.get(sym)
            if not details:
                # Try with mapping (e.g. SPX -> SPY)
                print(f"Asset: {sym} | NOT FOUND in Cache")
                continue
                
            base_flags = details.get("flags", [])
            tf_flags = details.get("timeframe_flags", {})
            trend = details.get("trend", "NEUTRAL")
            
            print(f"Asset: {sym} | Trend: {trend}")
            print(f"  • Base (1D) Flags: {base_flags}")
            if tf_flags:
                print(f"  • Timeframe-Specific Flags:")
                for tf, flags in sorted(tf_flags.items()):
                    print(f"    - {tf}: {flags}")
            else:
                print(f"  • No Timeframe-Specific Flags cached.")
    except Exception as e:
        print(f"Error reading cache data: {e}")

if __name__ == "__main__":
    main()
