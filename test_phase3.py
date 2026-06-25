"""Test Phase 3: Signal Detection System"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_database_schema():
    """Test that signals table was created"""
    print("[TEST] Testing database schema...")
    
    from detection.datastore import MangoDataStore
    
    datastore = MangoDataStore()
    
    # Try to query signals table
    try:
        signals = datastore.get_active_signals()
        print(f"[PASS] Signals table exists - {len(signals)} active signals")
    except Exception as e:
        print(f"[FAIL] Signals table error: {e}")
        return False
    
    return True

def test_signal_enum():
    """Test SignalType enum"""
    print("\n[TEST] Testing SignalType enum...")
    
    from detection.signals import SignalType
    
    expected_types = ['SWING_LONG', 'SWING_SHORT', 'SCALP_LONG', 'SCALP_SHORT']
    actual_types = [st.value for st in SignalType]
    
    if set(expected_types) == set(actual_types):
        print(f"[PASS] All signal types present: {actual_types}")
        return True
    else:
        print(f"[FAIL] Signal types mismatch. Expected: {expected_types}, Got: {actual_types}")
        return False

def test_signal_detector_init():
    """Test signal detector initialization"""
    print("\n[TEST] Testing signal detector initialization...")
    
    from detection.datastore import MangoDataStore
    from detection.signals import MangoSignalDetector
    
    try:
        datastore = MangoDataStore()
        detector = MangoSignalDetector(datastore)
        
        # Verify that datastore attribute is correctly set
        if detector.datastore == datastore:
            print("[PASS] Signal detector initialized with datastore successfully")
            return True
        else:
            print("[FAIL] Incorrect datastore assigned")
            return False
            
    except Exception as e:
        print(f"[FAIL] Signal detector initialization failed: {e}")
        return False

def test_tp_sl_calculation():
    """Test TP/SL calculation logic"""
    print("\n[TEST] Testing TP/SL calculation...")
    
    from detection.datastore import MangoDataStore
    from detection.signals import MangoSignalDetector
    
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    # Test LONG signal (using BTC settings with swing_rr=2.0 and 2.5% min risk)
    tp_sl_long = detector._calculate_tp_sl(
        entry_price=100.0,
        direction='LONG',
        entry_zone_low=97.0,
        entry_zone_high=103.0,
        candle_low=97.0,
        candle_high=103.0,
        timeframe='4h',
        is_scalp=False,
        asset_name='BTC',
        buffer_pct=0.0
    )
    
    print(f"  LONG - Entry: 100, SL: {tp_sl_long['stop_loss']}, TP: {tp_sl_long['take_profit']}, RR: {tp_sl_long['rr_ratio']}")
    
    # Verify LONG logic (SL = 97.0 which is wider than 97.5 min risk, RR = 2.0)
    if tp_sl_long['stop_loss'] == 97.0 and tp_sl_long['rr_ratio'] == 2.0:
        print("[PASS] LONG TP/SL calculation correct")
    else:
        print(f"[FAIL] LONG TP/SL incorrect. Expected SL=97.0, RR=2.0")
        return False
    
    # Test SHORT signal
    tp_sl_short = detector._calculate_tp_sl(
        entry_price=100.0,
        direction='SHORT',
        entry_zone_low=97.0,
        entry_zone_high=103.0,
        candle_low=97.0,
        candle_high=103.0,
        timeframe='4h',
        is_scalp=False,
        asset_name='BTC',
        buffer_pct=0.0
    )
    
    print(f"  SHORT - Entry: 100, SL: {tp_sl_short['stop_loss']}, TP: {tp_sl_short['take_profit']}, RR: {tp_sl_short['rr_ratio']}")
    
    # Verify SHORT logic (SL = 103.0 which is wider than 102.5 min risk, RR = 2.0)
    if tp_sl_short['stop_loss'] == 103.0 and tp_sl_short['rr_ratio'] == 2.0:
        print("[PASS] SHORT TP/SL calculation correct")
        return True
    else:
        print(f"[FAIL] SHORT TP/SL incorrect. Expected SL=103.0, RR=2.0")
        return False

def test_save_signal():
    """Test saving a signal to database"""
    print("\n[TEST] Testing signal save to database...")
    
    from detection.datastore import MangoDataStore
    from datetime import datetime
    
    datastore = MangoDataStore()
    
    # Clean up any existing BTC test signals to prevent cooldown/deduplication failure
    with datastore.get_connection() as conn:
        datastore._execute_query(conn, "DELETE FROM signals WHERE asset_name = 'BTC'")
    
    test_signal = {
        'asset_name': 'BTC',
        'asset_type': 'crypto',
        'signal_type': 'SWING_LONG',
        'confidence': 75.5,
        'entry_price': 42250.0,
        'take_profit': 44500.0,
        'stop_loss': 41100.0,
        'rr_ratio': 2.5,
        'entry_zone_low': 42150.0,
        'entry_zone_high': 42350.0,
        'htf': '4h',
        'ltf': '1h',
        'entry_time': datetime.utcnow().isoformat(),
        'status': 'ACTIVE'
    }
    
    try:
        signal_id = datastore.save_signal(test_signal)
        print(f"  Saved signal with ID: {signal_id}")
        
        # Verify it was saved
        active_signals = datastore.get_active_signals()
        if len(active_signals) > 0 and active_signals[0]['asset_name'] == 'BTC':
            print("[PASS] Signal saved and retrieved successfully")
            
            # Clean up test signal
            datastore.close_signal(signal_id)
            return True
        else:
            print("[FAIL] Signal not found after save")
            return False
            
    except Exception as e:
        print(f"[FAIL] Signal save failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all Phase 3 tests"""
    print("=" * 60)
    print("PHASE 3: SIGNAL DETECTION SYSTEM - TESTING")
    print("=" * 60)
    
    tests = [
        test_database_schema,
        test_signal_enum,
        test_signal_detector_init,
        test_tp_sl_calculation,
        test_save_signal
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"[FAIL] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n[SUCCESS] Phase 3 setup complete! Ready for Phase 4.")
        return 0
    else:
        print("\n[FAILED] Some tests failed. Please fix before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
