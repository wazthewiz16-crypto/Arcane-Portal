import sys
import os
from dotenv import load_dotenv

load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore

datastore = MangoDataStore()

active_signals = datastore.get_active_signals()
print(f"Active Signals: {len(active_signals)}")

latest_scrapes = datastore.get_latest_for_all_assets()
current_prices = {}
for scrape in latest_scrapes:
    current_prices[scrape['name'].strip().upper()] = float(scrape['close'])

for sig in active_signals:
    print(f"\nEvaluating Signal ID: {sig['id']}")
    print(f"  Asset: {sig['asset_name']}")
    print(f"  Type: {sig['signal_type']}")
    print(f"  Entry: {sig['entry_price']}")
    print(f"  SL: {sig['stop_loss']}")
    print(f"  TP: {sig['take_profit']}")
    
    asset_key = sig['asset_name'].strip().upper()
    cur_price = current_prices.get(asset_key)
    print(f"  Current Price: {cur_price}")
    
    if not cur_price:
        print("  -> Refused: Current price is missing")
        continue
    if not sig.get('entry_price') or not sig.get('stop_loss') or not sig.get('take_profit'):
        print("  -> Refused: entry_price, stop_loss, or take_profit is missing")
        continue
        
    try:
        entry_p = float(sig['entry_price'])
        stop_l = float(sig['stop_loss'])
        take_p = float(sig['take_profit'])
        
        if 'LONG' in sig['signal_type']:
            pnl_pct = (cur_price - entry_p) / entry_p * 100
            distance_to_sl = (cur_price - stop_l) / cur_price * 100
        else:
            pnl_pct = (entry_p - cur_price) / entry_p * 100
            distance_to_sl = (stop_l - cur_price) / cur_price * 100
            
        print(f"  Calculated PnL%: {pnl_pct:.2f}%")
        print(f"  Calculated Distance to SL: {distance_to_sl:.2f}%")
        
        # Prime trade check
        # -2.0 <= PnL <= +1.5 and distance_to_sl > 0.3
        is_prime_pnl = -2.0 <= pnl_pct <= +1.5
        is_prime_sl = distance_to_sl > 0.3
        
        print(f"  Is Prime PnL (-2.0 <= PnL <= +1.5)? {is_prime_pnl}")
        print(f"  Is Distance to SL > 0.3? {is_prime_sl}")
        
    except Exception as e:
        print(f"  Error: {e}")
