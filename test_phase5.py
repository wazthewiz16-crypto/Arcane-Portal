"""Test Phase 5: Streamlit Dashboard"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_dashboard_import():
    """Test dashboard can be imported"""
    print("[TEST] Testing dashboard import...")
    
    try:
        # Import the dashboard module
        import dashboard.app as app
        print("[PASS] Dashboard imported successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Dashboard import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dashboard_functions():
    """Test dashboard helper functions exist"""
    print("\n[TEST] Testing dashboard functions...")
    
    try:
        import dashboard.app as app
        
        required_functions = [
            'render_header',
            'render_active_signals',
            'render_signal_history',
            'render_asset_monitor',
            'render_system_health',
            'render_signal_card',
            'main'
        ]
        
        missing = []
        for func_name in required_functions:
            if not hasattr(app, func_name):
                missing.append(func_name)
        
        if missing:
            print(f"[FAIL] Missing functions: {missing}")
            return False
        
        print(f"[PASS] All {len(required_functions)} required functions present")
        return True
        
    except Exception as e:
        print(f"[FAIL] Function check failed: {e}")
        return False

def test_streamlit_installed():
    """Test Streamlit is installed"""
    print("\n[TEST] Testing Streamlit installation...")
    
    try:
        import streamlit as st
        print(f"[PASS] Streamlit {st.__version__} installed")
        return True
    except ImportError:
        print("[FAIL] Streamlit not installed")
        print("  Run: pip install -r requirements.txt")
        return False

def test_pandas_installed():
    """Test pandas is installed"""
    print("\n[TEST] Testing pandas installation...")
    
    try:
        import pandas as pd
        print(f"[PASS] pandas {pd.__version__} installed")
        return True
    except ImportError:
        print("[FAIL] pandas not installed")
        print("  Run: pip install -r requirements.txt")
        return False

def test_dashboard_config():
    """Test dashboard page configuration"""
    print("\n[TEST] Testing dashboard configuration...")
    
    try:
        # Check if streamlit config is valid
        # We can't actually run st.set_page_config outside of streamlit
        # but we can verify the code is syntactically correct
        
        with open('dashboard/app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_elements = [
            'st.set_page_config',
            'page_title="Arcane Portal V2"',
            'layout="wide"',
            'st.markdown',  # Custom CSS
            'st.header',
            'st.tabs'
        ]
        
        missing = [elem for elem in required_elements if elem not in content]
        
        if missing:
            print(f"[FAIL] Missing dashboard elements: {missing}")
            return False
        
        print("[PASS] Dashboard configuration valid")
        return True
        
    except Exception as e:
        print(f"[FAIL] Configuration check failed: {e}")
        return False

def main():
    """Run all Phase 5 tests"""
    print("=" * 60)
    print("PHASE 5: STREAMLIT DASHBOARD - TESTING")
    print("=" * 60)
    
    tests = [
        test_streamlit_installed,
        test_pandas_installed,
        test_dashboard_import,
        test_dashboard_functions,
        test_dashboard_config
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
        print("\n[SUCCESS] Phase 5 setup complete!")
        print("\n[INFO] To run the dashboard:")
        print("  streamlit run dashboard/app.py")
        print("\n[INFO] The dashboard will be available at:")
        print("  http://localhost:8501")
        return 0
    else:
        print("\n[FAILED] Some tests failed. Please fix before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
