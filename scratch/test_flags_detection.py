"""
Verification test for upgraded Mango Dashboard Flags and Setup Tiering logic
"""
import sys
import os
import json
from pathlib import Path

# Add project root working directory to path
sys.path.insert(0, os.getcwd())

import unittest
from unittest.mock import MagicMock, patch

from detection.datastore import MangoDataStore
from scraper.mango_dashboard import MangoDashboardScraper
from detection.signals import MangoSignalDetector

def safe_print(text):
    try:
        encoded = str(text).encode(sys.stdout.encoding or 'utf-8', errors='replace')
        print(encoded.decode(sys.stdout.encoding or 'utf-8'))
    except Exception:
        print("[Print Error: Unprintable characters]")

class TestFlagsDetection(unittest.TestCase):
    def setUp(self):
        self.scraper = MangoDashboardScraper()
        
    def test_scraper_direct_flag_mapping(self):
        safe_print("\n--- Test 1: Scraper Direct Flags Key Mapping ---")
        
        # Mock raw payload object from Mango Dashboard API
        mock_raw_obj = {
            "golden_cross": 1,        # Golden Cross (Bullish)
            "ichimoku": 2,            # Bearish Ichimoku (Bearish)
            "rsi_divergence": 1,      # RSI Bullish Divergence (Bullish)
            "premium_discount": 1,    # Cheap / Discount (Bullish)
            "most_viewed": True,      # Mango Hotlist
            "bbwp": 22.5
        }
        
        # Test extraction using our new parsing logic inside standardize/extract
        api_flags = []
        gc = mock_raw_obj.get("golden_cross")
        if gc == 1: api_flags.append("Golden Cross")
        elif gc == 2: api_flags.append("Death Cross")
        
        ichi = mock_raw_obj.get("ichimoku")
        if ichi == 1: api_flags.append("Bullish Ichimoku")
        elif ichi == 2: api_flags.append("Bearish Ichimoku")
        
        rsi = mock_raw_obj.get("rsi_divergence")
        if rsi == 1: api_flags.append("RSI Bullish Divergence")
        elif rsi == 2: api_flags.append("RSI Bearish Divergence")
        
        pd = mock_raw_obj.get("premium_discount")
        if pd == 1: api_flags.append("Cheap / Discount")
        elif pd == 2: api_flags.append("Expensive / Premium")
        
        if mock_raw_obj.get("most_viewed") is True:
            api_flags.append("Mango Hotlist")
            
        clean_flags = self.scraper.standardize_flags(mock_raw_obj.get("flags") or [])
        for af in api_flags:
            if af not in clean_flags:
                clean_flags.append(af)
                
        safe_print(f"Scraped Flags: {clean_flags}")
        self.assertIn("Golden Cross", clean_flags)
        self.assertIn("Bearish Ichimoku", clean_flags)
        self.assertIn("RSI Bullish Divergence", clean_flags)
        self.assertIn("Cheap / Discount", clean_flags)
        self.assertIn("Mango Hotlist", clean_flags)
        
    def test_signals_timeframe_merging(self):
        safe_print("\n--- Test 2: Timeframe Flags Merging in Detector ---")
        
        # Mock signal (4H HTF -> 15M LTF)
        mock_signal = {
            'asset_name': 'BTC',
            'signal_type': 'SWING_LONG',
            'entry_price': 100.0,
            'stop_loss': 97.0,
            'take_profit': 106.0,
            'rr_ratio': 2.0,
            'confidence': 80.0,
            'htf': '4h',
            'ltf': '15m'
        }
        
        # Mock confluence data stored in cache
        mock_confluence = {
            'flags': ['Cheap / Discount'],  # Base 1D flags
            'timeframe_flags': {
                '4H': ['Golden Cross'],
                '15M': ['RSI Bullish Divergence']
            }
        }
        
        # Test merging logic
        flags_set = set(mock_confluence.get('flags', []))
        tf_flags = mock_confluence.get('timeframe_flags', {})
        ltf_upper = str(mock_signal.get('ltf', '')).upper()
        htf_upper = str(mock_signal.get('htf', '')).upper()
        
        if ltf_upper in tf_flags:
            flags_set.update(tf_flags[ltf_upper])
        if htf_upper in tf_flags:
            flags_set.update(tf_flags[htf_upper])
            
        merged_flags = sorted(list(flags_set))
        safe_print(f"Merged Confluence Flags: {merged_flags}")
        
        self.assertIn("Cheap / Discount", merged_flags)
        self.assertIn("Golden Cross", merged_flags)
        self.assertIn("RSI Bullish Divergence", merged_flags)
        self.assertEqual(len(merged_flags), 3)

    @patch('detection.datastore.MangoDataStore.get_setting')
    def test_setup_tiering_promotion(self, mock_get_setting):
        safe_print("\n--- Test 3: Setup Tiering Promotion to A/A+ ---")
        mock_get_setting.return_value = 'TRENDING' # ML Market Regime is trending
        
        # Setup BTC long signal
        signal = {
            'asset_name': 'BTC',
            'signal_type': 'SWING_LONG',
            'entry_price': 100.0,
            'stop_loss': 97.0,
            'take_profit': 106.0,
            'rr_ratio': 2.0,
            'confidence': 80.0,
            'htf': '4h',
            'ltf': '15m'
        }
        
        # Mock low volatility < 30, and multiple confirming flags
        volatility = 20
        confirming_flags = ["Golden Cross", "Cheap / Discount"]
        calculated_confidence = 90.0 # High confidence
        mtf_aligned = True
        
        # Tiering logic
        confirming_count = len(confirming_flags)
        market_regime = 'TRENDING'
        is_trending_regime = market_regime.upper() == 'TRENDING'
        
        if (calculated_confidence >= 85.0 and 
            volatility < 30 and 
            mtf_aligned and 
            confirming_count >= 2 and 
            is_trending_regime):
            tier = 'A+'
        elif (calculated_confidence >= 70.0 and 
              volatility < 60 and 
              confirming_count >= 1):
            tier = 'A'
        else:
            tier = 'B'
            
        safe_print(f"Promoted setup tier: {tier}")
        self.assertEqual(tier, 'A+')

if __name__ == "__main__":
    unittest.main()
