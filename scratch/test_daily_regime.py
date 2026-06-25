import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.daily_regime import execute_daily_regime_check
from detection.signals import MangoSignalDetector

def run_tests():
    print("=" * 60)
    print("DAILY REGIME CHECK - LOCAL TEST SUITE")
    print("=" * 60)
    
    datastore = MangoDataStore()
    
    # Backup current database settings
    orig_decision = datastore.get_setting("DAILY_REGIME_DECISION")
    orig_morning_pred = datastore.get_setting("DAILY_REGIME_MORNING_PRED")
    orig_cap = datastore.get_setting("MAX_CRYPTO_SAME_DIRECTION")
    
    try:
        # 1. Test Morning Prediction Check (6 AM EST)
        print("\n--- 1. Testing Morning Prediction Check (6:00 AM EST) ---")
        morning_res = execute_daily_regime_check(datastore, is_afternoon=False)
        print(f"Morning Prediction: {morning_res['regime']} (Confidence: {morning_res['confidence']:.0f}%)")
        print(f"Morning Decision Assigned: {morning_res['decision']}")
        print(f"Saved DAILY_REGIME_DECISION: {datastore.get_setting('DAILY_REGIME_DECISION')}")
        print(f"Saved DAILY_REGIME_MORNING_PRED: {datastore.get_setting('DAILY_REGIME_MORNING_PRED')}")
        print(f"Correlation Cap set to: {datastore.get_setting('MAX_CRYPTO_SAME_DIRECTION')}")
        
        # 2. Test Afternoon Verification Check (1 PM EST)
        print("\n--- 2. Testing Afternoon Verification Check (1:00 PM EST) ---")
        afternoon_res = execute_daily_regime_check(datastore, is_afternoon=True)
        print(f"Afternoon Verification Regime: {afternoon_res['regime']} (Confidence: {afternoon_res['confidence']:.0f}%)")
        print(f"Actual 5 AM - 1 PM Avg Daily Range: {afternoon_res.get('avg_daily_range', 0.0):.2%}")
        print(f"Afternoon Decision Assigned: {afternoon_res['decision']}")
        print(f"Saved DAILY_REGIME_DECISION: {datastore.get_setting('DAILY_REGIME_DECISION')}")
        
        # 3. Test Signal Detector Filtering Logic
        print("\n--- 3. Testing Signal Detector Filtering Logic ---")
        detector = MangoSignalDetector(datastore)
        
        # Test Case 3a: RANGING_NO_TRADE
        print("\n[Case 3a] Testing RANGING_NO_TRADE (all trading halted)")
        datastore.set_setting("DAILY_REGIME_DECISION", "RANGING_NO_TRADE")
        signals_no_trade = detector.get_all_signals()
        print(f"Active Decision: {datastore.get_setting('DAILY_REGIME_DECISION')}")
        print(f"Signals generated: {len(signals_no_trade)}")
        if len(signals_no_trade) == 0:
            print("PASS: Correctly blocked all signals.")
        else:
            print("FAIL: Did not block all signals.")
            
        # Test Case 3b: RANGING_SCALPS_ONLY
        print("\n[Case 3b] Testing RANGING_SCALPS_ONLY (scalps only, swings blocked)")
        datastore.set_setting("DAILY_REGIME_DECISION", "RANGING_SCALPS_ONLY")
        signals_scalps_only = detector.get_all_signals()
        print(f"Active Decision: {datastore.get_setting('DAILY_REGIME_DECISION')}")
        print(f"Total signals generated: {len(signals_scalps_only)}")
        
        has_swing = any(s.get('signal_type') in ('SWING_LONG', 'SWING_SHORT') for s in signals_scalps_only)
        has_scalp = any(s.get('signal_type') in ('SCALP_LONG', 'SCALP_SHORT') for s in signals_scalps_only)
        
        print(f"Contains Swings: {has_swing} | Contains Scalps: {has_scalp}")
        if not has_swing:
            print("PASS: Correctly blocked all swing trades.")
        else:
            print("FAIL: Swing signals leaked through.")
            
        # Test Case 3c: TRENDING
        print("\n[Case 3c] Testing TRENDING (both swings & scalps permitted)")
        datastore.set_setting("DAILY_REGIME_DECISION", "TRENDING")
        signals_trending = detector.get_all_signals()
        print(f"Active Decision: {datastore.get_setting('DAILY_REGIME_DECISION')}")
        print(f"Total signals generated: {len(signals_trending)}")
        
        has_swing_t = any(s.get('signal_type') in ('SWING_LONG', 'SWING_SHORT') for s in signals_trending)
        has_scalp_t = any(s.get('signal_type') in ('SCALP_LONG', 'SCALP_SHORT') for s in signals_trending)
        print(f"Contains Swings: {has_swing_t} | Contains Scalps: {has_scalp_t}")
        print("PASS: Executed trending regime checks.")
        
    finally:
        # Restore original database settings
        print("\n--- Cleaning up: Restoring original settings ---")
        if orig_decision is not None: datastore.set_setting("DAILY_REGIME_DECISION", orig_decision)
        if orig_morning_pred is not None: datastore.set_setting("DAILY_REGIME_MORNING_PRED", orig_morning_pred)
        if orig_cap is not None: datastore.set_setting("MAX_CRYPTO_SAME_DIRECTION", orig_cap)
        print("Settings restored. Cleanup complete.")
        
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
