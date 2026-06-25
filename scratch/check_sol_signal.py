from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signals WHERE id = 211")
    row = cursor.fetchone()
    # Get column names
    colnames = [desc[0] for desc in cursor.description]
    for col, val in zip(colnames, row):
        print(f"{col}: {val}")
