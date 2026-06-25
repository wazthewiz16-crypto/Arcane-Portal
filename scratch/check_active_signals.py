import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    active = datastore.get_active_signals()
    print("--- Active Signals in DB ---")
    if not active:
        print("No active signals.")
    for sig in active:
        print(f"ID: {sig.get('id')} | Asset: {sig.get('asset_name')} | Type: {sig.get('signal_type')} | Entry: {sig.get('entry_price')} | Status: {sig.get('status')} | Created: {sig.get('created_at')}")

if __name__ == "__main__":
    main()
