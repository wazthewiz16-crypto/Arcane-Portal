from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
import json

ds = MangoDataStore()
val = ds.get_setting("PROD_ENV_DEBUG")

print("PROD_ENV_DEBUG in database:")
if val:
    try:
        data = json.loads(val)
        for k, v in data.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"  Raw value: {val} (error parsing: {e})")
else:
    print("  Key not found.")
