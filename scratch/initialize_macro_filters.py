import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    
    settings = {
        "ALLOW_SWING_WEEKLY_MISMATCH": "True",
        "ALLOW_SCALP_DAILY_MISMATCH": "True",
        "ALLOW_SCALP_WEEKLY_MISMATCH": "True",
        "STRICT_SCALP_LTF_ALIGNMENT": "False"
    }
    
    print("Initializing macro filters configuration in database...")
    for key, val in settings.items():
        datastore.set_setting(key, val)
        verified = datastore.get_setting(key)
        print(f"  {key} set to: {verified}")
        
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    main()
