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
    # Step 1: Initialize
    # Update existing statuses first (with whatever data we have)
    print("\n[STEP 1] Updating existing signal statuses...")
    try:
        datastore.update_signal_statuses()
        print("✅ Signal statuses monitored")
    except Exception as e:
        print(f"⚠️  Error updating statuses: {e}")

    # Step 2: Run Scraper & Detect in Stream
    print("\n[STEP 2] Running TradingView scraper (Streaming Mode)...")
    print("Processing assets one by one for faster alerts...")
    
    scraper = TradingViewScraper()
    assets = get_active_assets()
    
    use_smart_scheduling = os.getenv('USE_SMART_SCHEDULING', 'true').lower() == 'true'
    
    total_scraped = 0
    total_signals = 0
    
    try:
        async for asset_scrapes in scraper.stream_assets(assets, use_smart_scheduling=use_smart_scheduling):
            if not asset_scrapes: continue
            
            asset_name = asset_scrapes[0]['name']
            count = len(asset_scrapes)
            total_scraped += count
            print(f"  📝 Saving {count} scrapes for {asset_name}...")
            
            # 1. Save to DB
            datastore.save_scrapes(asset_scrapes)
            
            # 2. Save Screenshots
            for r in asset_scrapes:
                if 'screenshot_bytes' in r:
                    datastore.save_screenshot(r['name'], r['timeframe'], r['screenshot_bytes'])
            
            # 3. Update Status (Check TP/SL for this asset immediately)
            # We run global update but only this asset has new prices
            datastore.update_signal_statuses()
            
            # 4. Detect New Signals for THIS asset
            signals = detector.detect_signals_for_asset(asset_name)
            
            if signals:
                print(f"  🚨 Found {len(signals)} NEW signals for {asset_name}!")
                total_signals += len(signals)
                
                # Check active & Alert
                active_signals = datastore.get_active_signals()
                # Block by asset+direction (not exact type) to prevent correlated signals
                # e.g., if BTC SWING_LONG is active, block BTC SCALP_LONG too
                active_directions = set()
                for s in active_signals:
                    direction = 'LONG' if 'LONG' in s['signal_type'] else 'SHORT'
                    active_directions.add((s['asset_name'], direction))
                
                for signal in signals:
                    sig_direction = 'LONG' if 'LONG' in signal['signal_type'] else 'SHORT'
                    
                    # 1. Correlated signal blocker: one signal per asset per direction
                    if (signal['asset_name'], sig_direction) in active_directions:
                        print(f"    ℹ️  Blocked (correlated): {signal['asset_name']} already has active {sig_direction}")
                        continue
                    
                    # 2. Cooldown after SL hit: 2 hour max cooldown
                    from datetime import datetime, timedelta
                    import pytz
                    est = pytz.timezone('America/New_York')
                    now = datetime.now(est)
                    cooldown_cutoff = (now - timedelta(hours=2)).isoformat()
                    
                    with datastore.get_connection() as conn:
                        recent_sl = datastore._fetch_query(conn, """
                            SELECT COUNT(*) as cnt FROM signals
                            WHERE asset_name = %s 
                              AND signal_type LIKE %s
                              AND status = 'SL_HIT'
                              AND updated_at >= %s
                        """, (signal['asset_name'], f'%{sig_direction}%', cooldown_cutoff))
                    
                    if recent_sl and int(recent_sl[0].get('cnt', 0)) > 0:
                        print(f"    ⏳ Cooldown: {signal['asset_name']} {sig_direction} hit SL within last 2h")
                        continue
                        
                    # Save Signal
                    signal_id = datastore.save_signal(signal)
                    print(f"    ✅ Saved signal {signal_id}")
                    
                    # Handle Screenshot (Copy from Scraper storage to Signal storage)
                    # Scraper saved to DB. Signal needs separate copy?
                    # Signal Card uses `get_signal_image(signal_id)`.
                    # Scraper stored in `screenshots` table (latest).
                    # We should COPY bytes from current scrape -> signal_images table.
                    
                    import tempfile
                    
                    # Find matching scrape result for LTF (entry chart)
                    ltf = signal['ltf']
                    scrape_match = next((r for r in asset_scrapes if r['timeframe'] == ltf), None)
                    if scrape_match and 'screenshot_bytes' in scrape_match:
                         # Save to Signal Images
                         datastore.save_signal_image(signal_id, scrape_match['screenshot_bytes'])
                         # Write LTF screenshot to temp file for Discord
                         with tempfile.NamedTemporaryFile(suffix=f"_{ltf}.png", delete=False) as tmp:
                             tmp.write(scrape_match['screenshot_bytes'])
                             signal['image_path'] = tmp.name
                         print(f"    📸 Attached LTF screenshot ({ltf})")
                    
                    # Find matching scrape result for HTF (context chart)
                    htf = signal['htf']
                    htf_scrape_match = next((r for r in asset_scrapes if r['timeframe'] == htf), None)
                    htf_bytes = None
                    if htf_scrape_match and 'screenshot_bytes' in htf_scrape_match:
                         htf_bytes = htf_scrape_match['screenshot_bytes']
                    else:
                         # Fallback: HTF may not be in this scrape cycle, check DB
                         db_screenshot = datastore.get_screenshot(asset_name, htf)
                         if db_screenshot and db_screenshot.get('image_data'):
                             htf_bytes = db_screenshot['image_data']
                    
                    if htf_bytes:
                         with tempfile.NamedTemporaryFile(suffix=f"_{htf}.png", delete=False) as tmp:
                             tmp.write(htf_bytes)
                             signal['htf_image_path'] = tmp.name
                         print(f"    📸 Attached HTF screenshot ({htf})")

                    # Alert
                    if notifier.send_signal_alert(signal):
                        datastore.mark_signal_alerted(signal_id)
                        print(f"    🚀 Sent Discord Alert")
                        
                        # Cleanup temp files
                        for path_key in ['image_path', 'htf_image_path']:
                            path = signal.get(path_key)
                            if path and os.path.exists(path):
                                try: os.remove(path)
                                except: pass
            else:
                # print(f"  ✓ No new signals for {asset_name}")
                pass
                
        if total_scraped == 0:
            if use_smart_scheduling:
                 print("⏭️  No timeframes needed scraping.")
            else:
                 print("❌ No data scraped.")

    except Exception as e:
        print(f"❌ Stream error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n✅ Streaming Complete! {total_signals} new signals generated.")
    
    print("\n" + "=" * 60)
    print("COMPLETE! Check your dashboard and Discord for signals")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_scraper_and_detect())
