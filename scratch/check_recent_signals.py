import sys
import os
from dotenv import load_dotenv

load_dotenv(r"c:\Users\wasif\Documents\Arcane Portal\.env")
sys.path.append(r"c:\Users\wasif\Documents\Arcane Portal")

from detection.datastore import MangoDataStore

datastore = MangoDataStore()

with datastore.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, asset_name, signal_type, entry_price, entry_time, status, updated_at 
        FROM signals 
        WHERE entry_time >= '2026-05-25'
        ORDER BY entry_time DESC
    """)
    rows = cursor.fetchall()
    
    print("Recent Signals since May 25th, 2026:")
    for r in rows:
        print(f"  ID: {r[0]} | Asset: {r[1]:<6} | Type: {r[2]:<12} | Entry: {r[3]:<8} | Time: {r[4]} | Status: {r[5]:<10} | Updated: {r[6]}")
