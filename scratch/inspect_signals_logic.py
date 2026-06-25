from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector

ds = MangoDataStore()
detector = MangoSignalDetector(ds)

asset_name = 'BTC'
latest_data = ds.get_latest_for_asset(asset_name)
print(f"Latest data for {asset_name}: {len(latest_data)} rows")

timeframes = {}
for row in latest_data:
    timeframes[row['timeframe']] = row
    print(f"  TF: {row['timeframe']} | Close: {row['close']} | Trend: {row.get('trend')} | D1: {row.get('mango_d1')} | D2: {row.get('mango_d2')} | Up: {row.get('entry_up')} | Down: {row.get('entry_down')}")

# Try to detect swing
print("\nTracing _get_htf_direction for each timeframe:")
for tf, data in timeframes.items():
    dir_val = detector._get_htf_direction(data)
    print(f"  TF: {tf} -> HTF Direction: {dir_val}")

print("\nTracing _detect_swing_signal:")
sig = detector._detect_swing_signal(asset_name, timeframes)
if sig:
    print(f"  Detected swing: {sig}")
else:
    print("  No swing detected.")
