from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector
from config.assets import get_active_assets

ds = MangoDataStore()
detector = MangoSignalDetector(ds)

# Let's override _check_ltf_entry temporarily to log details
original_check = detector._check_ltf_entry

def patched_check(ltf_data, direction, is_scalp=False):
    res = original_check(ltf_data, direction, is_scalp)
    if not res['valid']:
        print(f"      [LTF Entry Check Fail] TF: {ltf_data['timeframe']} | Price: {ltf_data.get('close')} | Zone: {ltf_data.get('entry_down')} - {ltf_data.get('entry_up')} | Reason: {res['reason']}")
    return res

detector._check_ltf_entry = patched_check

assets = get_active_assets()
for asset in assets:
    asset_name = asset['name']
    latest_data = ds.get_latest_for_asset(asset_name)
    timeframes = {row['timeframe']: row for row in latest_data}
    
    print(f"\nAsset: {asset_name}")
    # Run Swing Combo
    print("  Checking Swings (4d -> 1d):")
    detector._detect_swing_signal(asset_name, timeframes)
    
    # Run Scalps (1h -> 15m)
    print("  Checking Scalps (1h -> 15m):")
    detector._detect_scalp_signal(asset_name, timeframes)
