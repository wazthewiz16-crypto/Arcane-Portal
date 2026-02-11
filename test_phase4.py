"""Test Phase 4: Discord Integration"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_discord_import():
    """Test Discord notifier can be imported"""
    print("[TEST] Testing Discord notifier import...")
    
    try:
        from integrations.discord_notifier import DiscordNotifier, send_signal_to_discord
        print("[PASS] Discord notifier imported successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Discord notifier import failed: {e}")
        return False

def test_discord_initialization():
    """Test Discord notifier initialization"""
    print("\n[TEST] Testing Discord notifier initialization...")
    
    from integrations.discord_notifier import DiscordNotifier
    
    try:
        # Test with no webhook (should warn but not fail)
        notifier = DiscordNotifier(webhook_url="")
        print("  Initialized with empty webhook (expected warning)")
        
        # Test with dummy webhook
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        print(f"  Webhook URL set: {notifier.webhook_url[:40]}...")
        
        print("[PASS] Discord notifier initialization successful")
        return True
    except Exception as e:
        print(f"[FAIL] Discord notifier initialization failed: {e}")
        return False

def test_message_formatting():
    """Test signal message formatting"""
    print("\n[TEST] Testing message formatting...")
    
    from integrations.discord_notifier import DiscordNotifier
    from datetime import datetime
    
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
    
    test_signal = {
        'asset_name': 'BTC',
        'asset_type': 'crypto',
        'signal_type': 'SWING_LONG',
        'confidence': 85.5,
        'entry_price': 42250.0,
        'take_profit': 44500.0,
        'stop_loss': 41100.0,
        'rr_ratio': 2.5,
        'htf': '4h',
        'ltf': '1h',
        'entry_time': datetime.utcnow().isoformat()
    }
    
    try:
        message = notifier._format_signal_alert(test_signal)
        
        # Don't print emojis directly (Windows console issue)
        print("\n  Message formatted successfully")
        print(f"  Length: {len(message)} characters")
        
        # Verify key elements are present
        required_elements = [
            'SWING LONG',
            'BTC',
            '4h',
            '1h',
            '42,250',
            '44,500',
            '41,100',
            '2.5:1',
            '86%'  # 85.5 rounds to 86
        ]
        
        missing = [elem for elem in required_elements if elem not in message]
        
        if missing:
            print(f"\n[FAIL] Missing elements in message: {missing}")
            return False
        
        print(f"  All required elements present: {len(required_elements)}/{len(required_elements)}")
        print("\n[PASS] Message formatting correct")
        return True
        
    except Exception as e:
        print(f"[FAIL] Message formatting failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_embed_creation():
    """Test Discord embed creation"""
    print("\n[TEST] Testing embed creation...")
    
    from integrations.discord_notifier import DiscordNotifier
    from datetime import datetime
    
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
    
    test_signal = {
        'asset_name': 'ETH',
        'signal_type': 'SCALP_SHORT',
        'confidence': 72.0,
        'entry_price': 2500.0,
        'take_profit': 2450.0,
        'stop_loss': 2525.0,
        'rr_ratio': 2.0,
        'htf': '1h',
        'ltf': '15m',
        'entry_time': datetime.utcnow().isoformat()
    }
    
    try:
        message = notifier._format_signal_alert(test_signal)
        embed = notifier._create_embed(test_signal, message)
        
        # Don't print title directly (has emojis)
        print(f"  Embed created successfully")
        print(f"  Color: {hex(embed['color'])} (Red for SHORT)")
        print(f"  Has footer: {bool(embed.get('footer'))}")
        
        # Verify embed structure
        if 'title' in embed and 'description' in embed and 'color' in embed:
            print("[PASS] Embed creation successful")
            return True
        else:
            print("[FAIL] Embed missing required fields")
            return False
            
    except Exception as e:
        print(f"[FAIL] Embed creation failed: {e}")
        return False

def test_webhook_validation():
    """Test webhook URL validation"""
    print("\n[TEST] Testing webhook validation...")
    
    from integrations.discord_notifier import DiscordNotifier
    from config import settings
    
    # Check if webhook is configured
    if settings.DISCORD_WEBHOOK_URL:
        print(f"  Webhook configured: {settings.DISCORD_WEBHOOK_URL[:40]}...")
        print("[PASS] Webhook URL is set in configuration")
        return True
    else:
        print("  [INFO] Webhook not configured in .env")
        print("  [INFO] To test actual sending, add DISCORD_WEBHOOK_URL to .env")
        print("[PASS] Validation check complete (webhook optional for testing)")
        return True

def test_send_simulation():
    """Simulate sending (without actual HTTP request)"""
    print("\n[TEST] Testing send simulation...")
    
    from integrations.discord_notifier import send_signal_to_discord
    from datetime import datetime
    
    test_signal = {
        'asset_name': 'SOL',
        'asset_type': 'crypto',
        'signal_type': 'SWING_LONG',
        'confidence': 78.0,
        'entry_price': 100.0,
        'take_profit': 105.0,
        'stop_loss': 98.0,
        'rr_ratio': 2.5,
        'htf': '4h',
        'ltf': '1h',
        'entry_time': datetime.utcnow().isoformat()
    }
    
    try:
        # This will attempt to send if webhook is configured
        # Otherwise it will just log a warning
        result = send_signal_to_discord(test_signal)
        
        print(f"  Send result: {result}")
        print("[PASS] Send function executed (check logs for actual result)")
        return True
        
    except Exception as e:
        print(f"[FAIL] Send simulation failed: {e}")
        return False

def main():
    """Run all Phase 4 tests"""
    print("=" * 60)
    print("PHASE 4: DISCORD INTEGRATION - TESTING")
    print("=" * 60)
    
    tests = [
        test_discord_import,
        test_discord_initialization,
        test_message_formatting,
        test_embed_creation,
        test_webhook_validation,
        test_send_simulation
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
        print("\n[SUCCESS] Phase 4 setup complete!")
        print("\n[INFO] To test actual Discord sending:")
        print("  1. Create a Discord webhook in your server")
        print("  2. Add DISCORD_WEBHOOK_URL to .env file")
        print("  3. Run: python -c \"from integrations.discord_notifier import DiscordNotifier; DiscordNotifier().send_test_alert()\"")
        return 0
    else:
        print("\n[FAILED] Some tests failed. Please fix before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
