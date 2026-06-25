from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, updated_at FROM system_settings WHERE key = 'LAST_RADAR_RUN_KEY'")
    row = cursor.fetchone()
    print("LAST_RADAR_RUN_KEY:", row)
    
    cursor.execute("SELECT key, value, updated_at FROM system_settings WHERE key = 'LAST_ML_RETRAIN_KEY'")
    row = cursor.fetchone()
    print("LAST_ML_RETRAIN_KEY:", row)
