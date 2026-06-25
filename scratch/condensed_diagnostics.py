import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector

def format_val(val):
    if val is None: return "None"
    return f"${val:.4f}" if val < 10 else f"${val:.2f}"

def main():
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    latest_data = datastore.get_latest_for_all_assets()
    assets_data = {}
    for row in latest_data:
        name = row['name']
        if name not in assets_data:
            assets_data[name] = {}
        assets_data[name][row['timeframe']] = row
        
    crypto_watchlist = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR"]
    
    print("=== CONDENSED SIGNAL BLOCKER ANALYSIS ===")
    daily_regime = datastore.get_setting("DAILY_REGIME_DECISION", "TRENDING")
    print(f"Daily Regime: {daily_regime}\n")
    
    for name in crypto_watchlist:
        if name not in assets_data:
            print(f"{name}: No data")
            continue
            
        timeframes = assets_data[name]
        tfs_str = []
        for tf in ['4d', '1d', '4h', '1h', '15m']:
            d = timeframes.get(tf)
            if d:
                dir_ = detector._get_htf_direction(d)
                tfs_str.append(f"{tf}:{dir_ or 'NEUTRAL'}")
        
        print(f"[{name}] {', '.join(tfs_str)}")
        
        # SWING check (1d/4h)
        daily_data = timeframes.get('1d')
        h4_data = timeframes.get('4h')
        if daily_data and h4_data:
            htf_dir = detector._get_htf_direction(daily_data)
            ltf_dir = detector._get_htf_direction(h4_data)
            if not htf_dir or htf_dir == 'NEUTRAL':
                print(f"  SWING: Blocked (1d Neutral)")
            else:
                weekly_data = timeframes.get('4d')
                weekly_dir = detector._get_htf_direction(weekly_data) if weekly_data else None
                if weekly_dir and weekly_dir != 'NEUTRAL' and weekly_dir != htf_dir:
                    print(f"  SWING: Blocked (weekly trend mismatch: {weekly_dir})")
                elif ltf_dir != htf_dir:
                    print(f"  SWING: Blocked (4h ribbon {ltf_dir} != 1d {htf_dir})")
                else:
                    ltf_entry = detector._check_ltf_entry(h4_data, htf_dir)
                    if not ltf_entry['valid']:
                        print(f"  SWING: Blocked (LTF Entry: {ltf_entry['reason']})")
                    else:
                        print(f"  SWING: PASS (Candidate {htf_dir})")
        else:
            print("  SWING: Blocked (Missing 1d/4h)")
            
        # SCALP check (4h/15m or 1h/15m)
        m15_data = timeframes.get('15m')
        for htf_tf, htf_data in [('4h', h4_data), ('1h', timeframes.get('1h'))]:
            if htf_data and m15_data:
                htf_dir = detector._get_htf_direction(htf_data)
                ltf_dir = detector._get_htf_direction(m15_data)
                if not htf_dir or htf_dir == 'NEUTRAL':
                    print(f"  SCALP {htf_tf}/15m: Blocked ({htf_tf} Neutral)")
                elif ltf_dir != htf_dir:
                    print(f"  SCALP {htf_tf}/15m: Blocked (15m ribbon {ltf_dir} != {htf_tf} {htf_dir})")
                else:
                    ltf_entry = detector._check_ltf_entry(m15_data, htf_dir, is_scalp=True)
                    if not ltf_entry['valid']:
                        print(f"  SCALP {htf_tf}/15m: Blocked (15m Entry: {ltf_entry['reason']})")
                    else:
                        print(f"  SCALP {htf_tf}/15m: PASS (Candidate {htf_dir})")
            else:
                print(f"  SCALP {htf_tf}/15m: Blocked (Missing data)")

if __name__ == "__main__":
    main()
