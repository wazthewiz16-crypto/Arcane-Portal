import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.daily_regime import execute_daily_regime_check

def main():
    datastore = MangoDataStore()
    print("Running execute_daily_regime_check (afternoon verification)...")
    res = execute_daily_regime_check(datastore, is_afternoon=True)
    
    print("\n--- Afternoon Regime Results Keys & Values ---")
    for k, v in res.items():
        if k in ('session_gainers', 'session_losers'):
            print(f"{k}:")
            for item in v:
                print(f"  - {item}")
        else:
            print(f"{k}: {v}")

if __name__ == "__main__":
    main()
