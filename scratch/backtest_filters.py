import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector

def main():
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    print("=== TESTING PRODUCTION DETECTOR ON LATEST STATE ===")
    
    # Verify database settings are read correctly
    print("Settings in DB:")
    for key in ["ALLOW_SWING_WEEKLY_MISMATCH", "ALLOW_SCALP_DAILY_MISMATCH", "ALLOW_SCALP_WEEKLY_MISMATCH", "STRICT_SCALP_LTF_ALIGNMENT"]:
        print(f"  {key}: {datastore.get_setting(key)}")
        
    latest_data = datastore.get_latest_for_all_assets()
    assets_data = {}
    for row in latest_data:
        name = row['name']
        if name not in assets_data:
            assets_data[name] = {}
        assets_data[name][row['timeframe']] = row
        
    signals = []
    for name, timeframes in assets_data.items():
        # Swing signals
        sig = detector._detect_swing_signal(name, timeframes)
        if sig:
            signals.append(sig)
        # Scalp signals
        sig = detector._detect_scalp_signal(name, timeframes)
        if sig:
            signals.append(sig)
            
    print(f"\nDetected {len(signals)} signal(s):")
    for sig in signals:
        print(f"  {sig['asset_name']} | {sig['signal_type']} | Entry: {sig['entry_price']} | Conf: {sig['confidence']:.1f}%")

if __name__ == "__main__":
    main()
