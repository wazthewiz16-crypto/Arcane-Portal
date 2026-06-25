from dotenv import load_dotenv
load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")

import sys
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore
ds = MangoDataStore()

with ds.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signals WHERE id IN (216, 217)")
    rows = cursor.fetchall()
    colnames = [desc[0] for desc in cursor.description]
    
    for r in rows:
        print(f"\n==========================================")
        print(f"Signal ID: {r[colnames.index('id')]} - {r[colnames.index('asset_name')]} {r[colnames.index('signal_type')]}")
        print(f"==========================================")
        for col, val in zip(colnames, r):
            if col not in ['id', 'asset_name', 'signal_type']:
                print(f"  {col}: {val}")
