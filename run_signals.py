"""Run scraper and generate signals - Manual execution"""
import sys
import os
import io

# Force UTF-8 encoding for standard output and error to avoid UnicodeEncodeErrors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from scraper.tradingview import TradingViewScraper
from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector
from integrations.discord_notifier import DiscordNotifier
from config.assets import get_active_assets
from utils.logger import setup_logger
import asyncio
import json

logger = setup_logger(__name__)

async def run_scraper_and_detect():
    """Run scraper, detect signals, and send Discord alerts"""
    
    # Initialize components
    datastore = MangoDataStore()
    
    # Debug: Save production env variables to DB
    try:
        debug_env = {
            "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL", "NOT_FOUND")[:40] + "...",
            "DATABASE_URL": os.getenv("DATABASE_URL", "NOT_FOUND")[:45] + "...",
            "MANGO_CONFLUENCE_ENABLED": os.getenv("MANGO_CONFLUENCE_ENABLED", "NOT_FOUND"),
            "USE_SMART_SCHEDULING": os.getenv("USE_SMART_SCHEDULING", "NOT_FOUND"),
        }
        datastore.set_setting("PROD_ENV_DEBUG", json.dumps(debug_env))
    except Exception as e:
        print(f"Debug env save failed: {e}")
    
    print("=" * 60)
    print("ARCANE PORTAL V2 - MANUAL SIGNAL GENERATION")
    print("=" * 60)
    
    # --- WEEKEND FREQUENCY OPTIMIZATION ---
    from datetime import datetime
    import pytz
    
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    is_weekend = now.weekday() >= 5  # 5 = Saturday, 6 = Sunday
    
    # Railway CRON runs every 15 mins (e.g., :00, :15, :30, :45)
    # To reduce weekend costs, we skip the :15 and :45 runs, running only every 30 mins
    if is_weekend and (10 <= now.minute <= 20 or 40 <= now.minute <= 50):
        print("💤 WEEKEND MODE: Skipping the :15 / :45 execution to reduce compute costs.")
        print("Will resume scraping at the next hour or half-hour mark.")
        return
    # --------------------------------------
    
    # Initialize remaining components
    detector = MangoSignalDetector(datastore)
    notifier = DiscordNotifier()
    
    # --- Mango Research Premium Dashboard Scraper (1-hour rate-limit cache update) ---
    # Quiet hours: 11 PM – 5 AM EST — no scraping or signals during sleep hours
    _mango_quiet = 23 <= now.hour or now.hour < 5
    try:
        from scraper.mango_dashboard import MangoDashboardScraper
        from datetime import datetime
        mango_scraper = MangoDashboardScraper()
        
        if _mango_quiet:
            print("[MANGO DASHBOARD] 💤 Quiet hours (11 PM–5 AM EST) — dashboard scrape skipped.")
        elif mango_scraper.is_enabled():
            print("\n[MANGO DASHBOARD] Confluence verification is ENABLED.")
            last_update_str = datastore.get_setting("MANGO_DASHBOARD_LAST_UPDATE")
            should_scrape = True
            
            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str)
                    elapsed_hours = (datetime.utcnow() - last_update).total_seconds() / 3600.0
                    if elapsed_hours < 1.0:
                        print(f"[MANGO DASHBOARD] Using cached data (updated {elapsed_hours:.2f} hours ago — rate limit 1 hour).")
                        should_scrape = False
                except Exception as e:
                    print(f"[MANGO DASHBOARD] Error parsing last update timestamp: {e}")
                    
            if should_scrape:
                print("[MANGO DASHBOARD] Updating premium dashboard cache (1-hour scheduler window triggered)...")
                success = await mango_scraper.scrape_dashboard()
                if success:
                    datastore.set_setting("MANGO_DASHBOARD_LAST_UPDATE", datetime.utcnow().isoformat())
                    print("[MANGO DASHBOARD] Cache successfully refreshed!")
                else:
                    print("[MANGO DASHBOARD] Scraper run failed. Using existing cache if available.")
        else:
            print("\n[MANGO DASHBOARD] Confluence verification is disabled (MANGO_CONFLUENCE_ENABLED != True).")
    except Exception as e:
        print(f"[MANGO DASHBOARD] Initialization or scraping error: {e}")
    # ---------------------------------------------------------------------------------

    # --- Mango-Native Signal Detection (runs after every dashboard scrape/cache load) ---
    # Same quiet hours enforced: no signals 11 PM – 5 AM EST
    try:
        from scraper.mango_dashboard import MangoDashboardScraper as _MS
        _ms = _MS()
        if _mango_quiet:
            print("[MANGO NATIVE] 💤 Quiet hours (11 PM–5 AM EST) — native signal detection skipped.")
        elif _ms.is_enabled():
            print("\n[MANGO NATIVE] Running dashboard-native signal detector...")
            from detection.mango_native_signals import MangoNativeSignalDetector
            native_detector = MangoNativeSignalDetector(datastore)
            native_signals  = native_detector.detect()

            if native_signals:
                print(f"[MANGO NATIVE] {len(native_signals)} native signal(s) detected!")
                for sig in native_signals:
                    try:
                        notifier.send_signal_alert(sig)
                        print(f"  🥭 Sent Mango-native signal: {sig['asset_name']} {sig['signal_type']}")
                    except Exception as e:
                        print(f"  ⚠️  Failed to send Mango-native Discord alert: {e}")
            else:
                print("[MANGO NATIVE] No new badge flips — no native signals this cycle.")
        else:
            print("[MANGO NATIVE] Skipped (MANGO_CONFLUENCE_ENABLED not True).")
    except Exception as e:
        print(f"[MANGO NATIVE] Error during native signal detection: {e}")
        import traceback
        traceback.print_exc()
    # ---------------------------------------------------------------------------------

    
    # Step 1: Run scraper
    # Step 1: Initialize
    # Update existing statuses first (with whatever data we have)
    print("\n[STEP 1] Updating existing signal statuses...")
    try:
        datastore.update_signal_statuses()
        print("[OK] Signal statuses monitored")
    except Exception as e:
        err_msg = f"⚠️ [STEP 1] Error updating signal statuses: {e}"
        print(err_msg, file=sys.stderr)
        try:
            notifier.send_error_alert(err_msg)
        except Exception as de:
            print(f"Failed to send Discord error alert: {de}", file=sys.stderr)

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
                    ltf_bytes = None
                    if scrape_match and 'screenshot_bytes' in scrape_match:
                         ltf_bytes = scrape_match['screenshot_bytes']
                         # Save to Signal Images table
                         datastore.save_signal_image(signal_id, scrape_match['screenshot_bytes'])
                    else:
                         # Fallback: LTF may not be in this scrape cycle (e.g. 1d only scraped twice daily)
                         db_screenshot = datastore.get_screenshot(asset_name, ltf)
                         if db_screenshot and db_screenshot.get('image_data'):
                             ltf_bytes = db_screenshot['image_data']
                             print(f"    📸 LTF ({ltf}) not in current batch — using DB screenshot")
                         else:
                             print(f"    ⚠️  No LTF screenshot available for {asset_name} {ltf}")

                    if ltf_bytes:
                         # Write LTF screenshot to temp file for Discord
                         with tempfile.NamedTemporaryFile(suffix=f"_{ltf}.png", delete=False) as tmp:
                             tmp.write(ltf_bytes)
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
        
    # Step 3: Trade Radar (Runs 4 times a day)
    # The cron starts explicitly on the 10th/15th minute mark.
    # To be extremely robust against cloud container spin-up latencies or cron delays,
    # we use a persistent database check to guarantee the Trade Radar runs exactly once during the target hour.
    target_radar_hours = [7, 13, 18, 22]
    if now.hour in target_radar_hours:
        current_radar_key = f"{now.strftime('%Y-%m-%d')}-{now.hour}"
        last_radar_run = datastore.get_setting("LAST_RADAR_RUN_KEY")
        
        if last_radar_run != current_radar_key:
            print(f"\n[STEP 3] Running Trade Radar (scheduled hour: {now.hour}:00 EST)...")
            try:
                from trade_radar import run_trade_radar
                # Set database lock key only if the trade radar actually successfully posts to Discord
                did_post = run_trade_radar()
                if did_post:
                    datastore.set_setting("LAST_RADAR_RUN_KEY", current_radar_key)
                    print(f"[OK] Trade Radar run successfully logged for key: {current_radar_key}")
                else:
                    print(f"[INFO] Trade Radar executed but did not post. Lock key NOT set, will retry this hour.")
            except Exception as e:
                import traceback
                err_msg = f"⚠️ [STEP 3] Error running Trade Radar: {e}\n\n{traceback.format_exc()}"
                print(err_msg, file=sys.stderr)
                try:
                    notifier.send_error_alert(err_msg[:1900])
                except Exception as de:
                    print(f"Failed to send Discord error alert: {de}", file=sys.stderr)
            
    # Step 4: Weekly ML Model Retraining
    # Run every Saturday (weekday 5) on the very first cron run of the day
    # (TradFi markets closed, lowest system usage).
    # We use a persistent database check to guarantee it runs exactly once on Saturday,
    # making it immune to cloud container latency or Daylight Saving Time offsets.
    if now.weekday() == 5:
        current_retrain_key = now.strftime('%Y-%m-%d')
        last_retrain_run = datastore.get_setting("LAST_ML_RETRAIN_KEY")
        
        if last_retrain_run != current_retrain_key:
            print(f"\n[STEP 4] Initiating Weekly ML Model Retraining (Saturday first run: {now.strftime('%I:%M %p EST')})...")
            try:
                from ml_regime import fetch_and_prepare_data, generate_features, train_model
                df = fetch_and_prepare_data()
                feats = generate_features(df)
                if not feats.empty:
                    train_model(feats)
                    datastore.set_setting("LAST_ML_RETRAIN_KEY", current_retrain_key)
                    print(f"[OK] Weekly ML retraining completed successfully and logged for key: {current_retrain_key}")
                else:
                    print("[WARN] Not enough data to retrain ML model yet.")
            except Exception as e:
                import traceback
                err_msg = f"⚠️ [STEP 4] Error during ML retrain: {e}\n\n{traceback.format_exc()}"
                print(err_msg, file=sys.stderr)
                try:
                    notifier.send_error_alert(err_msg[:1900])
                except Exception as de:
                    print(f"Failed to send Discord error alert: {de}", file=sys.stderr)

    print(f"\n✅ Streaming Complete! {total_signals} new signals generated.")
    
    print("\n" + "=" * 60)
    print("COMPLETE! Check your dashboard and Discord for signals")
    print("=" * 60)

if __name__ == "__main__":
    try:
        # Wrap the entire process in a 60-minute timeout to prevent headless Playwright 
        # deadlocks in the Railway Docker container which causes silent cron failures.
        asyncio.run(asyncio.wait_for(run_scraper_and_detect(), timeout=3600))
    except asyncio.TimeoutError:
        msg = "❌ CRITICAL: Scraper run timed out after 60 minutes! Probable Playwright deadlock."
        print(msg, file=sys.stderr)
        try:
            from integrations.discord_notifier import DiscordNotifier
            DiscordNotifier().send_error_alert(msg)
        except Exception as de:
            print(f"Failed to send Discord error alert: {de}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        import traceback
        err_msg = f"❌ CRITICAL ERROR: Scraper run failed with exception:\n{str(e)}\n\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        try:
            from integrations.discord_notifier import DiscordNotifier
            DiscordNotifier().send_error_alert(err_msg[:1900])
        except Exception as de:
            print(f"Failed to send Discord error alert: {de}", file=sys.stderr)
        sys.exit(1)
