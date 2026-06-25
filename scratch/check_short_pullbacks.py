import sys
from pathlib import Path
from dotenv import load_dotenv
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    print("Fetching latest scrapes for crypto assets...")
    
    crypto_watchlist = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR"]
    
    with datastore.get_connection() as conn:
        rows = datastore._fetch_query(conn, """
            SELECT DISTINCT ON (name, timeframe)
                name, timeframe, close, open, high, low,
                mango_d1, mango_d2, entry_up, entry_down, trend, timestamp
            FROM scrapes
            WHERE timeframe IN ('4h', '1h')
            ORDER BY name, timeframe, timestamp DESC
        """)
        
    print("\n--- Current Price vs. Entry Zone Analysis ---")
    
    # Group by asset
    assets_data = {}
    for r in rows:
        name = r['name']
        if name.upper() not in crypto_watchlist:
            continue
        tf = r['timeframe']
        if name not in assets_data:
            assets_data[name] = {}
        assets_data[name][tf] = r

    for name in crypto_watchlist:
        if name not in assets_data:
            print(f"{name}: No scrapes found in DB.")
            continue
        
        print(f"\n[Asset] {name}:")
        for tf in ('4h', '1h'):
            data = assets_data[name].get(tf)
            if not data:
                print(f"  {tf}: No data")
                continue
                
            close = data['close']
            d1 = data['mango_d1']
            d2 = data['mango_d2']
            entry_up = data['entry_up']
            entry_down = data['entry_down']
            trend = data['trend'] or 'NEUTRAL'
            ts = data['timestamp']
            
            if close is None or d1 is None or d2 is None:
                print(f"  {tf}: Close={close}, Ribbon missing")
                continue
                
            close = float(close)
            d1 = float(d1)
            d2 = float(d2)
            
            # Determine ribbon zone
            ribbon_top = max(d1, d2)
            ribbon_bottom = min(d1, d2)
            
            # State description
            status = ""
            if close < ribbon_bottom:
                dist_pct = (ribbon_bottom - close) / close
                status = f"BELOW ribbon (Price is {dist_pct:.1%} below the entry zone floor)"
            elif close > ribbon_top:
                dist_pct = (close - ribbon_top) / ribbon_top
                status = f"ABOVE ribbon (Price is {dist_pct:.1%} above ribbon)"
            else:
                status = "INSIDE ribbon (Pullback Entry Zone active!)"
                
            print(f"  {tf} ({trend}) - Close: ${close:,.4f} | Ribbon: ${ribbon_bottom:,.4f} - ${ribbon_top:,.4f} | State: {status}")

if __name__ == "__main__":
    main()
