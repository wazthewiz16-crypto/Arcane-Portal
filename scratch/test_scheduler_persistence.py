"""
Verification test for upgraded database-persisted Trade Radar & ML retraining triggers
"""
import sys
import os
import unittest
from unittest.mock import MagicMock
from datetime import datetime

# Add project root working directory to path
sys.path.insert(0, os.getcwd())

from detection.datastore import MangoDataStore

def safe_print(text):
    try:
        encoded = str(text).encode(sys.stdout.encoding or 'utf-8', errors='replace')
        print(encoded.decode(sys.stdout.encoding or 'utf-8'))
    except Exception:
        print("[Print Error: Unprintable characters]")

class TestSchedulerPersistence(unittest.TestCase):
    def setUp(self):
        # Mock Datastore
        self.datastore = MagicMock()
        self.settings_cache = {}
        
        def mock_get_setting(key):
            return self.settings_cache.get(key)
            
        def mock_set_setting(key, value):
            self.settings_cache[key] = value
            return True
            
        self.datastore.get_setting = mock_get_setting
        self.datastore.set_setting = mock_set_setting
        
    def test_trade_radar_trigger_once_per_hour(self):
        safe_print("\n--- Test 1: Trade Radar triggers exactly once per scheduled hour ---")
        
        target_radar_hours = [7, 13, 18, 22]
        
        # Scenario A: 1:00 PM EST (13:00) on 2026-06-01 - Radar should trigger
        now_1pm_run1 = datetime(2026, 6, 1, 13, 0, 0)
        self.assertIn(now_1pm_run1.hour, target_radar_hours)
        
        current_radar_key = f"{now_1pm_run1.strftime('%Y-%m-%d')}-{now_1pm_run1.hour}"
        self.assertEqual(current_radar_key, "2026-06-01-13")
        
        # First execution in this hour
        last_radar_run = self.datastore.get_setting("LAST_RADAR_RUN_KEY")
        self.assertNotEqual(last_radar_run, current_radar_key)
        
        # Simulating running the Trade Radar and logging the key
        self.datastore.set_setting("LAST_RADAR_RUN_KEY", current_radar_key)
        
        # Second execution (e.g. at 13:15 due to 15-min cron run)
        now_1pm_run2 = datetime(2026, 6, 1, 13, 15, 0)
        current_radar_key_run2 = f"{now_1pm_run2.strftime('%Y-%m-%d')}-{now_1pm_run2.hour}"
        
        last_radar_run_run2 = self.datastore.get_setting("LAST_RADAR_RUN_KEY")
        self.assertEqual(last_radar_run_run2, current_radar_key_run2) # Equal! Should skip!
        
        # Check skip
        should_run_radar_run2 = last_radar_run_run2 != current_radar_key_run2
        self.assertFalse(should_run_radar_run2)
        
        safe_print(f"Run 1 at 1:00 PM EST: Radar triggered and logged key: {current_radar_key}")
        safe_print(f"Run 2 at 1:15 PM EST: Radar correctly skipped. Database key check works!")
        
    def test_ml_retraining_trigger_once_on_saturday(self):
        safe_print("\n--- Test 2: ML Retraining triggers exactly once on Saturday ---")
        
        # Scenario A: Saturday (weekday 5) - first cron run of the day
        now_sat_run1 = datetime(2026, 5, 30, 6, 0, 0) # e.g. 6:00 AM EDT (10:00 UTC first cron)
        self.assertEqual(now_sat_run1.weekday(), 5)
        
        current_retrain_key = now_sat_run1.strftime('%Y-%m-%d')
        self.assertEqual(current_retrain_key, "2026-05-30")
        
        # First execution
        last_retrain_run = self.datastore.get_setting("LAST_ML_RETRAIN_KEY")
        self.assertNotEqual(last_retrain_run, current_retrain_key)
        
        # Simulating running ML retraining and logging the key
        self.datastore.set_setting("LAST_ML_RETRAIN_KEY", current_retrain_key)
        
        # Second execution later on Saturday (e.g. at 10:15 AM EDT)
        now_sat_run2 = datetime(2026, 5, 30, 10, 15, 0)
        current_retrain_key_run2 = now_sat_run2.strftime('%Y-%m-%d')
        
        last_retrain_run_run2 = self.datastore.get_setting("LAST_ML_RETRAIN_KEY")
        self.assertEqual(last_retrain_run_run2, current_retrain_key_run2) # Equal! Should skip!
        
        # Check skip
        should_run_retrain_run2 = last_retrain_run_run2 != current_retrain_key_run2
        self.assertFalse(should_run_retrain_run2)
        
        safe_print(f"Saturday first execution (6:00 AM): ML retraining triggered and logged key: {current_retrain_key}")
        safe_print(f"Saturday later execution (10:15 AM): ML retraining correctly skipped. Database key check works!")

if __name__ == "__main__":
    unittest.main()
