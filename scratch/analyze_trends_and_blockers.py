import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector

def format_val(val):
    if val is None:
        return "None"
    return f"${val:,.4f}" if val < 10 else f"${val:,.2f}"

def analyze():
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    # Fetch latest data for all assets
    latest_data = datastore.get_latest_for_all_assets()
    
    # Group by asset name
    assets_data = {}
    for row in latest_data:
        name = row['name']
        if name not in assets_data:
            assets_data[name] = {}
        assets_data[name][row['timeframe']] = row
        
    crypto_watchlist = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR"]
    
    print("==================================================")
    print("  CRYPTO WATCHLIST TRENDS & SIGNAL DIAGNOSTICS")
    print("==================================================")
    
    daily_regime = datastore.get_setting("DAILY_REGIME_DECISION", "TRENDING")
    print(f"Daily Trading Regime Decision: {daily_regime}")
    print("--------------------------------------------------")
    
    for name in crypto_watchlist:
        if name not in assets_data:
            print(f"\n[Asset] {name}: No scrape data found in database.")
            continue
            
        timeframes = assets_data[name]
        print(f"\n[Asset] {name}")
        
        # Display trend direction for key timeframes
        tfs = ['4d', '1d', '4h', '1h', '15m']
        trend_strs = []
        for tf in tfs:
            data = timeframes.get(tf)
            if data:
                direction = detector._get_htf_direction(data)
                close = data.get('close')
                d1 = data.get('mango_d1')
                d2 = data.get('mango_d2')
                trend_strs.append(f"{tf}: {direction} (Close: {format_val(close)}, Ribbon: {format_val(min(d1,d2))} - {format_val(max(d1,d2))})")
            else:
                trend_strs.append(f"{tf}: MISSING")
        
        for ts in trend_strs:
            print(f"  {ts}")
            
        print("  --- Diagnostic Checks ---")
        
        # 1. Swing Diagnostics (Daily/4H Swing is the primary crypto combo)
        # We check Daily/4H (HTF = '1d', LTF = '4h')
        daily_data = timeframes.get('1d')
        h4_data = timeframes.get('4h')
        w_data = timeframes.get('4d')
        
        if daily_regime == "RANGING_SCALPS_ONLY":
            print("  [SWING] Blocked globally: DAILY_REGIME_DECISION is RANGING_SCALPS_ONLY")
        elif not daily_data or not h4_data:
            print("  [SWING] Blocked: Missing 1d or 4h data")
        else:
            # Let's perform swing analysis manually step by step
            htf_direction = detector._get_htf_direction(daily_data)
            daily_dir = htf_direction
            weekly_dir = detector._get_htf_direction(w_data) if w_data else None
            ltf_direction = detector._get_htf_direction(h4_data)
            
            if not htf_direction or htf_direction == 'NEUTRAL':
                print(f"  [SWING] Blocked: HTF (1d) trend is NEUTRAL (price inside 1d ribbon).")
            else:
                # Macro trend checks
                fighting_weekly = False
                if weekly_dir and weekly_dir != 'NEUTRAL' and weekly_dir != htf_direction:
                    fighting_weekly = True
                    
                ltf_agreement = ltf_direction == htf_direction
                
                ltf_entry = detector._check_ltf_entry(h4_data, htf_direction)
                
                print(f"  [SWING] Candidate direction: {htf_direction}")
                if fighting_weekly:
                    print(f"    - Macro filter: BLOCKED (Fighting weekly/4d trend: {weekly_dir})")
                else:
                    print(f"    - Macro filter: PASS")
                    
                if not ltf_agreement:
                    print(f"    - LTF (4h) Ribbon Agreement: BLOCKED (LTF is {ltf_direction}, HTF is {htf_direction})")
                else:
                    print(f"    - LTF (4h) Ribbon Agreement: PASS")
                    
                if not ltf_entry['valid']:
                    # Explain why not valid
                    close = h4_data.get('close')
                    entry_up = h4_data.get('entry_up')
                    entry_down = h4_data.get('entry_down')
                    high = h4_data.get('high')
                    low = h4_data.get('low')
                    
                    reason = ltf_entry['reason']
                    if htf_direction == 'SHORT':
                        if close < entry_down:
                            pct_below = (entry_down - close) / entry_down
                            reason = f"Price is {pct_below:.1%} below the entry zone floor (${entry_down:.4f}) without pullback bounce (High: ${high:.4f})"
                        else:
                            reason = f"Price (${close:.4f}) is above entry ceiling (${entry_up:.4f})"
                    else:  # LONG
                        if close > entry_up:
                            pct_above = (close - entry_up) / entry_up
                            reason = f"Price is {pct_above:.1%} above the entry zone ceiling (${entry_up:.4f}) without pullback bounce (Low: ${low:.4f})"
                        else:
                            reason = f"Price (${close:.4f}) is below entry floor (${entry_down:.4f})"
                    
                    print(f"    - LTF Entry Validation: BLOCKED ({reason})")
                else:
                    print(f"    - LTF Entry Validation: PASS ({ltf_entry['reason']})")
                    
        # 2. Scalp Diagnostics
        # We check 4h/15m scalp (primary combo) or 1h/15m scalp (tighter)
        h4_data = timeframes.get('4h')
        h1_data = timeframes.get('1h')
        m15_data = timeframes.get('15m')
        
        for htf_tf, htf_data in [('4h', h4_data), ('1h', h1_data)]:
            if not htf_data or not m15_data:
                print(f"  [SCALP {htf_tf}/15m] Blocked: Missing data")
                continue
                
            htf_direction = detector._get_htf_direction(htf_data)
            if not htf_direction or htf_direction == 'NEUTRAL':
                print(f"  [SCALP {htf_tf}/15m] Blocked: HTF ({htf_tf}) trend is NEUTRAL (price inside ribbon).")
                continue
                
            # Macro trend checks
            daily_data = timeframes.get('1d')
            fighting_daily = False
            if daily_data:
                daily_dir = detector._get_htf_direction(daily_data)
                if daily_dir and daily_dir != 'NEUTRAL' and daily_dir != htf_direction:
                    fighting_daily = True
                    
            weekly_data = timeframes.get('4d')
            fighting_weekly = False
            if weekly_data:
                weekly_dir = detector._get_htf_direction(weekly_data)
                if htf_direction == 'LONG' and weekly_dir == 'SHORT':
                    fighting_weekly = True
                if htf_direction == 'SHORT' and weekly_dir == 'LONG':
                    fighting_weekly = True
                    
            ltf_ribbon_dir = detector._get_htf_direction(m15_data)
            ltf_agreement = ltf_ribbon_dir == htf_direction
            
            # Scalps use is_scalp=True in _check_ltf_entry
            ltf_entry = detector._check_ltf_entry(m15_data, htf_direction, is_scalp=True)
            
            print(f"  [SCALP {htf_tf}/15m] Candidate direction: {htf_direction}")
            if fighting_daily:
                print(f"    - Daily filter: BLOCKED (Fighting Daily trend: {daily_dir})")
            elif fighting_weekly:
                print(f"    - Weekly/4D filter: BLOCKED (Fighting Weekly trend: {weekly_dir})")
            else:
                print(f"    - Macro filters: PASS")
                
            if not ltf_agreement:
                print(f"    - LTF (15m) Ribbon Agreement: BLOCKED (LTF is {ltf_ribbon_dir}, HTF is {htf_direction})")
            else:
                print(f"    - LTF (15m) Ribbon Agreement: PASS")
                
            if not ltf_entry['valid']:
                close = m15_data.get('close')
                entry_up = m15_data.get('entry_up')
                entry_down = m15_data.get('entry_down')
                reason = ltf_entry['reason']
                if htf_direction == 'SHORT' and close < entry_down:
                    pct_below = (entry_down - close) / entry_down
                    reason = f"Price is {pct_below:.1%} below the entry zone floor (${entry_down:.4f}) without pullback (Scalps require strict in-zone close)"
                print(f"    - LTF Entry Validation: BLOCKED ({reason})")
            else:
                print(f"    - LTF Entry Validation: PASS ({ltf_entry['reason']})")

if __name__ == "__main__":
    analyze()
