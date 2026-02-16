"""Test script to verify time window utility works correctly"""
from utils.time_window import is_within_operating_hours, get_operating_hours_info

def test_time_window():
    """Test the time window checker"""
    
    print("=" * 60)
    print("TIME WINDOW TEST")
    print("=" * 60)
    
    info = get_operating_hours_info()
    
    print(f"\n[TIME] Current Time: {info['current_time_est']}")
    print(f"[HOURS] Operating Hours: {info['operating_hours']}")
    print(f"[STATUS] Status: {info['status']}")
    print(f"[INFO] {info['next_change']}")
    
    if info['is_operating']:
        print("\n[OK] SYSTEM IS ACTIVE - Scraper will run")
    else:
        print("\n[SLEEP] SYSTEM IS SLEEPING - Scraper will skip execution")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_time_window()
