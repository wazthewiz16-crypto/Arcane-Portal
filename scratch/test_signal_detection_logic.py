from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector
from config.assets import get_active_assets

ds = MangoDataStore()
detector = MangoSignalDetector(ds)

# Disable the database setting override so we check all potential signals
current_swing = float(ds.get_setting("MIN_CONFIDENCE_SWING", 65))
current_scalp = float(ds.get_setting("MIN_CONFIDENCE_SCALP", 70))
print(f"Current database thresholds -> Swing: {current_swing} | Scalp: {current_scalp}")

# Let's temporarily lower the thresholds to see if we get signals
print("\nTesting signal detection with lower threshold (65% Swing / 70% Scalp):")
assets = get_active_assets()

for asset in assets:
    asset_name = asset['name']
    # Check if we can find any signal for this asset
    # Temporarily patch datastore get_setting for this instance
    original_get_setting = ds.get_setting
    def patched_get_setting(key, default_value=None):
        if key == "MIN_CONFIDENCE_SWING":
            return 65.0
        if key == "MIN_CONFIDENCE_SCALP":
            return 70.0
        return original_get_setting(key, default_value)
    
    ds.get_setting = patched_get_setting
    
    signals = detector.detect_signals_for_asset(asset_name)
    if signals:
        print(f"  Asset: {asset_name} -> Detected {len(signals)} signals!")
        for sig in signals:
            print(f"    Type: {sig['signal_type']} | Conf: {sig['confidence']:.2f}% | Entry: {sig['entry_price']}")
            
    # Restore original method
    ds.get_setting = original_get_setting
