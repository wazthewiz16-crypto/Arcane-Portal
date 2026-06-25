import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    print("Setting MANGO_VOLATILITY_THRESHOLD to 85.0...")
    datastore.set_setting("MANGO_VOLATILITY_THRESHOLD", "85.0")
    
    val = datastore.get_setting("MANGO_VOLATILITY_THRESHOLD")
    print(f"Verified MANGO_VOLATILITY_THRESHOLD in database: {val}")

if __name__ == "__main__":
    main()
