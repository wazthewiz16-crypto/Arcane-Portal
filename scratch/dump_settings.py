import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    target_keys = [
        "DAILY_REGIME_DECISION",
        "DAILY_REGIME_MORNING_PRED",
        "MARKET_REGIME",
        "CIRCUIT_BREAKER_ACTIVE",
        "BREAKOUT_CAPTURE_PCT"
    ]
    print("--- Target Database Settings ---")
    with datastore.get_connection() as conn:
        for key in target_keys:
            val = datastore.get_setting(key)
            print(f"{key}: {val}")

if __name__ == "__main__":
    main()
