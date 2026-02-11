"""Test Phase 2: Core Infrastructure Setup"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all new modules can be imported"""
    print("[TEST] Testing imports...")
    
    try:
        from config import settings
        print("[PASS] config.settings imported")
    except Exception as e:
        print(f"[FAIL] config.settings failed: {e}")
        return False
    
    try:
        from utils.logger import setup_logger
        print("[PASS] utils.logger imported")
    except Exception as e:
        print(f"[FAIL] utils.logger failed: {e}")
        return False
    
    try:
        from config.assets import get_active_assets
        assets = get_active_assets()
        print(f"[PASS] config.assets imported - {len(assets)} assets loaded")
    except Exception as e:
        print(f"[FAIL] config.assets failed: {e}")
        return False
    
    return True

def test_asset_types():
    """Test that all assets have type field"""
    print("\n[TEST] Testing asset types...")
    
    from config.assets import get_active_assets
    assets = get_active_assets()
    
    crypto_count = sum(1 for a in assets if a.get('type') == 'crypto')
    tradfi_count = sum(1 for a in assets if a.get('type') == 'tradfi')
    
    print(f"  Crypto assets: {crypto_count}")
    print(f"  TradFi assets: {tradfi_count}")
    
    missing_type = [a['name'] for a in assets if 'type' not in a]
    if missing_type:
        print(f"[FAIL] Assets missing type field: {missing_type}")
        return False
    
    print("[PASS] All assets have type field")
    return True

def test_config_values():
    """Test configuration values"""
    print("\n[TEST] Testing configuration...")
    
    from config import settings
    
    print(f"  MIN_CONFIDENCE_SWING: {settings.MIN_CONFIDENCE_SWING}")
    print(f"  MIN_CONFIDENCE_SCALP: {settings.MIN_CONFIDENCE_SCALP}")
    print(f"  HEADLESS_BROWSER: {settings.HEADLESS_BROWSER}")
    print(f"  TV_STATE_FILE exists: {settings.TV_STATE_FILE.exists()}")
    
    if settings.MIN_CONFIDENCE_SWING != 40:
        print(f"[FAIL] Expected MIN_CONFIDENCE_SWING=40, got {settings.MIN_CONFIDENCE_SWING}")
        return False
    
    if settings.MIN_CONFIDENCE_SCALP != 65:
        print(f"[FAIL] Expected MIN_CONFIDENCE_SCALP=65, got {settings.MIN_CONFIDENCE_SCALP}")
        return False
    
    print("[PASS] Configuration values correct")
    return True

def test_logger():
    """Test logger setup"""
    print("\n[TEST] Testing logger...")
    
    from utils.logger import setup_logger
    
    logger = setup_logger("test_logger")
    logger.info("Test log message")
    
    print("[PASS] Logger working")
    return True

def main():
    """Run all Phase 2 tests"""
    print("=" * 60)
    print("PHASE 2: CORE INFRASTRUCTURE - TESTING")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_asset_types,
        test_config_values,
        test_logger
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"[FAIL] Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n[SUCCESS] Phase 2 setup complete! Ready for Phase 3.")
        return 0
    else:
        print("\n[FAILED] Some tests failed. Please fix before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

