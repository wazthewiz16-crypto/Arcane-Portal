"""
Verification test for Arcane Trade Radar Visuals and R-multiple Upgrades
"""
import sys
import os
from pathlib import Path

# Add project root working directory to path
sys.path.insert(0, os.getcwd())

import unittest
from unittest.mock import MagicMock, patch
import tempfile

from detection.datastore import MangoDataStore
from integrations.discord_notifier import DiscordNotifier
from trade_radar import run_trade_radar

def safe_print(text):
    try:
        encoded = str(text).encode(sys.stdout.encoding or 'utf-8', errors='replace')
        print(encoded.decode(sys.stdout.encoding or 'utf-8'))
    except Exception:
        print("[Print Error: Unprintable characters]")

class TestRadarVisuals(unittest.TestCase):
    def setUp(self):
        self.notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/mock")
        
    def test_r_drift_and_rr_calculations_long(self):
        safe_print("\n--- Test 1: LONG R-Drift and R:R calculations ---")
        # LONG signal
        # Entry: 100, Stop Loss: 97 (Risk = 3, Risk % = 3.0%)
        # Take Profit: 106 (Original R:R = 6 / 3 = 2.0:1)
        sig = {
            'asset_name': 'BTC',
            'signal_type': 'SWING_LONG',
            'entry_price': 100.0,
            'stop_loss': 97.0,
            'take_profit': 106.0,
            'rr_ratio': 2.0,
            'confidence': 85.0
        }
        
        # Scenario A: Pullback to 98.8 (pnl = -1.2%)
        cur_price = 98.8
        pnl_pct = (cur_price - sig['entry_price']) / sig['entry_price'] * 100
        self.assertAlmostEqual(pnl_pct, -1.2)
        
        original_risk = abs(sig['entry_price'] - sig['stop_loss'])
        original_reward = abs(sig['take_profit'] - sig['entry_price'])
        original_rr = original_reward / original_risk
        self.assertAlmostEqual(original_rr, 2.0)
        
        # Enhanced R:R calculation
        risk_denom = cur_price - sig['stop_loss']
        reward_num = sig['take_profit'] - cur_price
        enhanced_rr = reward_num / risk_denom
        self.assertAlmostEqual(enhanced_rr, 4.0) # 7.2 / 1.8 = 4.0
        
        # R-Multiple Drift
        risk_pct = original_risk / sig['entry_price']
        r_drift = pnl_pct / (risk_pct * 100)
        self.assertAlmostEqual(r_drift, -0.4) # -1.2 / 3 = -0.4R
        
        safe_print(f"LONG Pullback - PnL: {pnl_pct:.2f}%, R-Drift: {r_drift:.2f}R, Enhanced R:R: {enhanced_rr:.2f}:1")
        
    def test_r_drift_and_rr_calculations_short(self):
        safe_print("\n--- Test 2: SHORT R-Drift and R:R calculations ---")
        # SHORT signal
        # Entry: 100, Stop Loss: 103 (Risk = 3, Risk % = 3.0%)
        # Take Profit: 94 (Original R:R = 6 / 3 = 2.0:1)
        sig = {
            'asset_name': 'BTC',
            'signal_type': 'SWING_SHORT',
            'entry_price': 100.0,
            'stop_loss': 103.0,
            'take_profit': 94.0,
            'rr_ratio': 2.0,
            'confidence': 85.0
        }
        
        # Scenario A: Pullback to 101.2 (pnl = -1.2%)
        cur_price = 101.2
        pnl_pct = (sig['entry_price'] - cur_price) / sig['entry_price'] * 100
        self.assertAlmostEqual(pnl_pct, -1.2)
        
        original_risk = abs(sig['entry_price'] - sig['stop_loss'])
        original_reward = abs(sig['take_profit'] - sig['entry_price'])
        original_rr = original_reward / original_risk
        self.assertAlmostEqual(original_rr, 2.0)
        
        # Enhanced R:R calculation
        risk_denom = sig['stop_loss'] - cur_price
        reward_num = cur_price - sig['take_profit']
        enhanced_rr = reward_num / risk_denom
        self.assertAlmostEqual(enhanced_rr, 4.0) # 7.2 / 1.8 = 4.0
        
        # R-Multiple Drift
        risk_pct = original_risk / sig['entry_price']
        r_drift = pnl_pct / (risk_pct * 100)
        self.assertAlmostEqual(r_drift, -0.4) # -1.2 / 3 = -0.4R
        
        safe_print(f"SHORT Pullback - PnL: {pnl_pct:.2f}%, R-Drift: {r_drift:.2f}R, Enhanced R:R: {enhanced_rr:.2f}:1")
        
    @patch('integrations.discord_notifier.requests.post')
    def test_discord_notifier_with_file(self, mock_post):
        safe_print("\n--- Test 3: Discord Notifier with File ---")
        mock_post.return_value.status_code = 204
        
        # Create a temp file to simulate screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
            temp.write(b"fake image data bytes")
            temp_path = temp.name
            
        try:
            content = "Testing Arcane Trade Radar visually"
            success = self.notifier.send_message_with_file(content, temp_path)
            self.assertTrue(success)
            self.assertTrue(mock_post.called)
            
            # Verify payload_json and file in args
            args, kwargs = mock_post.call_args
            self.assertIn('data', kwargs)
            self.assertIn('payload_json', kwargs['data'])
            self.assertIn('files', kwargs)
            self.assertIn('file', kwargs['files'])
            
            safe_print("Discord notifier send_message_with_file mock verified successfully.")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    @patch('detection.datastore.MangoDataStore.get_active_signals')
    @patch('detection.datastore.MangoDataStore.get_latest_for_all_assets')
    @patch('detection.datastore.MangoDataStore.get_screenshot')
    @patch('integrations.discord_notifier.DiscordNotifier.send_message_with_file')
    def test_end_to_end_radar_run(self, mock_send_with_file, mock_get_screenshot, mock_get_latest, mock_get_active):
        safe_print("\n--- Test 4: End-to-End Radar execution (with visuals) ---")
        
        # Mock active signals
        mock_get_active.return_value = [
            {
                'asset_name': 'BTC',
                'signal_type': 'SWING_LONG',
                'entry_price': 100.0,
                'stop_loss': 97.0,
                'take_profit': 106.0,
                'rr_ratio': 2.0,
                'confidence': 85.0,
                'htf': '4h',
                'ltf': '1h',
                'tier': 'A+'
            }
        ]
        
        # Mock latest scraped prices (pullback to 99.0)
        mock_get_latest.return_value = [
            {
                'name': 'BTC',
                'close': 99.0
            }
        ]
        
        # Mock screenshot from DB
        mock_get_screenshot.return_value = {
            'image_data': b'mocked_png_binary_data',
            'updated_at': '2026-05-29T18:00:00'
        }
        
        # Run
        mock_send_with_file.return_value = True
        
        # Run the radar
        run_trade_radar()
            
        self.assertTrue(mock_get_screenshot.called)
        self.assertTrue(mock_send_with_file.called)
        
        # Ensure temporary file is cleaned up (doesn't leak in project folder)
        project_dir = Path(__file__).parent.parent
        png_files = list(project_dir.glob("temp_radar_*.png"))
        self.assertEqual(len(png_files), 0, f"Temporary file leaked: {png_files}")
        
        safe_print("End-to-End Radar flow (with screenshot attachment + temp cleanup) verified successfully.")

if __name__ == "__main__":
    unittest.main()
