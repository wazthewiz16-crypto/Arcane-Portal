"""Run scraper and generate signals - Manual execution"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.tradingview import TradingViewScraper
from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector
from integrations.discord_notifier import DiscordNotifier
from config.assets import get_active_assets
from utils.logger import setup_logger
import asyncio

logger = setup_logger(__name__)

async def run_scraper_and_detect():
    """Run scraper, detect signals, and send Discord alerts"""
    
    print("=" * 60)
    print("ARCANE PORTAL V2 - MANUAL SIGNAL GENERATION")
    print("=" * 60)
    
    # Initialize components
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    notifier = DiscordNotifier()
    
    # Step 1: Run scraper
    print("\n[STEP 1] Running TradingView scraper...")
    print("This will take a few minutes to scrape all assets and timeframes...")
    
    scraper = TradingViewScraper()
    assets = get_active_assets()
    
    # Smart scheduling (can be disabled via environment variable)
    use_smart_scheduling = os.getenv('USE_SMART_SCHEDULING', 'true').lower() == 'true'
    
    try:
        results = await scraper.scrape_all_assets(assets, use_smart_scheduling=use_smart_scheduling)
        
        if results:
            print(f"✅ Scraped {len(results)} data points")
            
            # Save to database
            datastore.save_scrapes(results)
            print(f"✅ Saved to database")
            
            # Save screenshots to DB for cross-process access
            count = 0
            for r in results:
                if 'screenshot_bytes' in r:
                    datastore.save_screenshot(r['name'], r['timeframe'], r['screenshot_bytes'])
                    count += 1
            if count > 0:
                print(f"📸 Saved {count} screenshots to DB")
        else:
            if use_smart_scheduling:
                print("⏭️  No timeframes needed scraping at this time")
            else:
                print("❌ No data scraped. Check your tv_state.json file.")
            return
            
    except Exception as e:
        print(f"❌ Scraper error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Update existing signal statuses
    print("\n[STEP 2] Updating existing signal statuses...")
    
    try:
        datastore.update_signal_statuses()
        print("✅ Signal statuses updated")
    except Exception as e:
        print(f"⚠️  Error updating statuses: {e}")
    
    # Step 3: Detect new signals
    print("\n[STEP 3] Detecting trading signals...")
    
    try:
        signals = detector.get_all_signals()
        
        if signals:
            print(f"✅ Found {len(signals)} signals!")
            
            # Display signals
            for i, signal in enumerate(signals, 1):
                print(f"\n  Signal {i}:")
                print(f"    Asset: {signal['asset_name']}")
                print(f"    Type: {signal['signal_type']}")
                print(f"    Confidence: {signal['confidence']:.0f}%")
                print(f"    Entry: ${signal['entry_price']:,.2f}")
                print(f"    TP: ${signal['take_profit']:,.2f}")
                print(f"    SL: ${signal['stop_loss']:,.2f}")
                print(f"    RR: {signal['rr_ratio']:.1f}:1")
        else:
            print("ℹ️  No signals detected (no setups meet confidence thresholds)")
            print("   - Swing signals need 60%+ confidence")
            print("   - Scalp signals need 75%+ confidence")
            return
            
    except Exception as e:
        print(f"❌ Signal detection error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Save signals and send Discord alerts
    print("\n[STEP 4] Saving signals and sending Discord alerts...")
    
    try:
        # Get active signals to prevent duplicates
        active_signals = datastore.get_active_signals()
        active_map = {(s['asset_name'], s['signal_type']) for s in active_signals}
        
        for signal in signals:
            # Check if signal is already active
            if (signal['asset_name'], signal['signal_type']) in active_map:
                print(f"  ℹ️  Signal already ACTIVE: {signal['asset_name']} {signal['signal_type']} - Skipping alert")
                continue
            
            # Save to database (will be new since we checked active_map)
            signal_id = datastore.save_signal(signal)
            print(f"  ✅ Saved NEW signal {signal_id}: {signal['asset_name']} {signal['signal_type']}")
            
            # Helper to copy screenshot
            import shutil
            ltf = signal['ltf']
            name = signal['asset_name']
            # Source: data/screenshots/BTC_1h.png
            src_path = os.path.join("data", "screenshots", f"{name}_{ltf}.png")
            # Dest: data/screenshots/signals/123.png
            dest_dir = os.path.join("data", "screenshots", "signals")
            os.makedirs(dest_dir, exist_ok=True)
            
            if os.path.exists(src_path):
                dest_path = os.path.join(dest_dir, f"{signal_id}.png")
                try:
                    shutil.copy2(src_path, dest_path)
                    signal['image_path'] = dest_path # Pass to notifier
                    print(f"  📸 Attached screenshot for signal {signal_id}")
                    
                    # Save to DB for cross-process access (Dashboard)
                    try:
                        with open(dest_path, "rb") as f:
                             datastore.save_signal_image(signal_id, f.read())
                    except Exception as e:
                        print(f"  ⚠️  Failed to save signal image to DB: {e}")
                        
                except Exception as e:
                    print(f"  ⚠️  Failed to copy screenshot: {e}")
            
            # Send Discord alert
            if notifier.send_signal_alert(signal):
                datastore.mark_signal_alerted(signal_id)
                print(f"  ✅ Discord alert sent for {signal['asset_name']}")
            else:
                print(f"  ⚠️  Discord alert failed for {signal['asset_name']}")
        
        print(f"\n✅ All done! {len(signals)} signals saved and alerted")
        
    except Exception as e:
        print(f"❌ Error saving/alerting: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("COMPLETE! Check your dashboard and Discord for signals")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_scraper_and_detect())
