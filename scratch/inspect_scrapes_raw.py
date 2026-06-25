from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scrapes ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    colnames = [desc[0] for desc in cursor.description]
    for col, val in zip(colnames, row):
        print(f"  {col}: {val} (type: {type(val).__name__})")
