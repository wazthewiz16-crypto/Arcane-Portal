import sys
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore

datastore = MangoDataStore()

def simulate_radar_at(target_time_est):
    print(f"\n==================================================")
    print(f"Simulating Radar at {target_time_est.strftime('%Y-%m-%d %I:%M %p EST')}")
    print(f"==================================================")
    
    # Target time in UTC
    target_time_utc = target_time_est.astimezone(pytz.utc)
    
    # 1. Fetch active signals at that time.
    # A signal was active if entry_time <= target_time <= updated_at (and status was TP_HIT/SL_HIT/BREAKEVEN/ACTIVE/EXPIRED afterwards)
    # or if target_time >= entry_time and the signal was not yet updated or updated after target_time.
    with datastore.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, asset_name, signal_type, entry_price, stop_loss, take_profit, entry_time, status, updated_at
            FROM signals
            WHERE entry_time <= %s
        """, (target_time_est.isoformat(),))
        all_signals = cursor.fetchall()
        
    active_signals = []
    for sig in all_signals:
        entry_time_str = sig[6]
        updated_at_str = sig[8]
        status = sig[7]
        
        # Convert entry_time (with timezone) to offset-aware datetime
        entry_time = datetime.fromisoformat(entry_time_str)
        if entry_time.tzinfo is None:
            entry_time = pytz.timezone('America/New_York').localize(entry_time)
            
        # Convert updated_at (UTC string) to offset-aware datetime
        if updated_at_str:
            updated_at = datetime.fromisoformat(updated_at_str)
            if updated_at.tzinfo is None:
                updated_at = pytz.utc.localize(updated_at)
        else:
            updated_at = None
            
        is_active = False
        if entry_time <= target_time_est:
            if not updated_at or updated_at > target_time_utc:
                is_active = True
            elif status == 'ACTIVE':
                is_active = True
                
        if is_active:
            active_signals.append({
                'id': sig[0],
                'asset_name': sig[1],
                'signal_type': sig[2],
                'entry_price': sig[3],
                'stop_loss': sig[4],
                'take_profit': sig[5],
                'entry_time': entry_time,
                'status': status,
                'updated_at': updated_at
            })
            
    print(f"Active signals at this time: {len(active_signals)}")
    for sig in active_signals:
        print(f"  ID: {sig['id']} | Asset: {sig['asset_name']} | Type: {sig['signal_type']} | Entry: {sig['entry_price']} | SL: {sig['stop_loss']} | TP: {sig['take_profit']}")
        
        # Try to find a scrape for this asset closest to the target time (within 1 hour)
        with datastore.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch scrapes within 1 hour of the target time
            start_window = (target_time_utc - timedelta(hours=1)).isoformat()
            end_window = (target_time_utc + timedelta(hours=1)).isoformat()
            cursor.execute("""
                SELECT timestamp, close FROM scrapes
                WHERE name = %s
                AND timestamp BETWEEN %s AND %s
                ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp::timestamp - %s::timestamp))) ASC
                LIMIT 1
            """, (sig['asset_name'], start_window, end_window, target_time_utc.isoformat()))
            row = cursor.fetchone()
            
        if not row:
            print("    -> No close scrapes found!")
            continue
            
        scrape_time, cur_price = row
        cur_price = float(cur_price)
        print(f"    Found scrape at {scrape_time} (UTC): Price = {cur_price}")
        
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
                
            print(f"    Calculated PnL%: {pnl_pct:.2f}% | Distance to SL: {distance_to_sl:.2f}%")
            
            is_prime_pnl = -2.0 <= pnl_pct <= +1.5
            is_prime_sl = distance_to_sl > 0.3
            print(f"    Is Prime PnL (-2.0 <= PnL <= +1.5)? {is_prime_pnl}")
            print(f"    Is Distance to SL > 0.3? {is_prime_sl}")
            
        except Exception as e:
            print(f"    Error: {e}")

# Simulate at 6 PM EST (June 1)
est = pytz.timezone('America/New_York')
simulate_radar_at(datetime(2026, 6, 1, 18, 0, tzinfo=est))

# Simulate at 10 PM EST (June 1)
simulate_radar_at(datetime(2026, 6, 1, 22, 0, tzinfo=est))

# Simulate at 7 AM EST (June 2)
simulate_radar_at(datetime(2026, 6, 2, 7, 0, tzinfo=est))
