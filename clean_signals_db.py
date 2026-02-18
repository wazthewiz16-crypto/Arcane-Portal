"""
Utility script to clean/reset the signals database
Use this to purge old signals before starting fresh tracking
"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file BEFORE importing datastore (which checks DATABASE_URL at import time)
from dotenv import load_dotenv
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from datetime import datetime

def clean_signals_database():
    """Delete all signals from the database"""
    datastore = MangoDataStore()
    
    print("=" * 60)
    print("SIGNAL DATABASE CLEANUP")
    print("=" * 60)
    
    # Get current signal count using direct SQL
    with datastore.get_connection() as conn:
        cursor = datastore._execute_query(conn, "SELECT COUNT(*) FROM signals")
        count = cursor.fetchone()[0]
    
    print(f"\nCurrent signals in database: {count}")
    
    if count == 0:
        print("✅ Database is already clean!")
        return
    
    # Confirm deletion
    print(f"\n⚠️  WARNING: This will delete ALL {count} signals from the database!")
    confirmation = input("Type 'DELETE' to confirm: ")
    
    if confirmation != "DELETE":
        print("❌ Cancelled. No signals were deleted.")
        return
    
    # Delete all signals
    print("\n🗑️  Deleting signals...")
    
    with datastore.get_connection() as conn:
        datastore._execute_query(conn, "DELETE FROM signals")
        
        # Also delete signal images
        try:
            datastore._execute_query(conn, "DELETE FROM signal_images")
            print("  ✅ Deleted signal images")
        except:
            pass  # Table might not exist
        
        conn.commit()
    
    # Verify deletion
    with datastore.get_connection() as conn:
        cursor = datastore._execute_query(conn, "SELECT COUNT(*) FROM signals")
        final_count = cursor.fetchone()[0]
    
    print(f"\n✅ Cleanup complete!")
    print(f"   Signals deleted: {count}")
    print(f"   Remaining signals: {final_count}")
    print("\n" + "=" * 60)
    print(f"Database reset at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    clean_signals_database()
