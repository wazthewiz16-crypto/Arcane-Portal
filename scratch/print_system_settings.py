import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore

def main():
    datastore = MangoDataStore()
    print("--- Current Database Settings ---")
    with datastore.get_connection() as conn:
        rows = datastore._fetch_query(conn, "SELECT key, value FROM system_settings ORDER BY key")
        for r in rows:
            print(f"{r['key']}: {r['value']}")

if __name__ == "__main__":
    main()
